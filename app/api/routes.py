"""
API Routes for Price Savvy Scraper
As per PRD endpoints:
- GET /search - Product search with pagination and sorting
- GET /compare - Product comparison
- GET /products/{id} - Product detail
- GET /products?url={url} - Product by URL
"""

from flask import jsonify, request
from app.api import api_bp
from app.services.scraper_service import ScraperService
from app.utils.validators import validate_url, validate_product_id
from app.utils.rate_limiter import rate_limit
from app.utils.normalizer import normalize_product, merge_duplicates, compare_products
from app.utils.cache import get_cache
from app.database import get_db
import logging

logger = logging.getLogger(__name__)


@api_bp.route("/search", methods=["GET"])
@rate_limit
def search_products():
    """
    Search for products across multiple e-commerce sites.

    Query Parameters:
        q (required): Search query
        page (optional): Page number, default 1
        per_page (optional): Results per page, default 20
        sort (optional): Sort by 'price' or 'rating', default 'price'
        order (optional): Sort order 'asc' or 'desc', default 'asc'

    Returns:
        JSON with normalized product summaries and pagination metadata.
    """
    # Get query parameters
    query = request.args.get("q", "").strip()

    if not query:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Bad Request",
                    "message": "Search query (q) is required",
                }
            ),
            400,
        )

    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Bad Request",
                    "message": "Page and per_page must be integers",
                }
            ),
            400,
        )

    # Validate pagination
    page = max(1, page)
    per_page = max(1, min(100, per_page))  # Limit to 100 per page

    sort_by = request.args.get("sort", "price")
    sort_order = request.args.get("order", "asc")

    # Validate sort parameters
    if sort_by not in ("price", "rating"):
        sort_by = "price"
    if sort_order not in ("asc", "desc"):
        sort_order = "asc"

    # Check cache first
    cache = get_cache()
    cache_key = f"search:{query}:{page}:{per_page}:{sort_by}:{sort_order}"
    cached_result = cache.get(cache_key)

    if cached_result:
        logger.info(f"Cache hit for search: {query}")
        return jsonify({"success": True, "data": cached_result, "cached": True}), 200

    try:
        # Perform concurrent scraping from multiple sources
        scraper_service = ScraperService()
        raw_results = scraper_service.search_products(query)

        # Normalize all results
        normalized_products = []
        for result in raw_results:
            if result.get("success") and result.get("products"):
                source = result.get("source", "unknown")
                for product in result["products"]:
                    normalized = normalize_product(product, source)
                    normalized_products.append(normalized)

        # Merge duplicates using fuzzy matching
        deduplicated = merge_duplicates(normalized_products)

        # Store in database
        db = get_db()
        for product in deduplicated:
            try:
                product_id = db.upsert_product(product)
                product["id"] = product_id
            except Exception as e:
                logger.error(f"Failed to store product: {e}")

        # Sort results
        reverse = sort_order == "desc"
        if sort_by == "price":
            deduplicated.sort(
                key=lambda p: p.get("best_price") or p.get("price") or 0,
                reverse=reverse,
            )
        elif sort_by == "rating":
            deduplicated.sort(key=lambda p: p.get("rating") or 0, reverse=reverse)

        # Paginate
        total = len(deduplicated)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_products = deduplicated[start_idx:end_idx]

        result = {
            "products": paginated_products,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page if total > 0 else 0,
                "has_next": end_idx < total,
                "has_prev": page > 1,
            },
            "query": query,
            "sort": {"by": sort_by, "order": sort_order},
        }

        # Cache the result
        cache.set(cache_key, result)

        return jsonify({"success": True, "data": result, "cached": False}), 200

    except Exception as e:
        logger.error(f"Search error: {e}")

        # Try to return cached/database results as fallback
        db = get_db()
        db_results = db.search_products(query, page, per_page, sort_by, sort_order)

        if db_results.get("products"):
            return (
                jsonify(
                    {
                        "success": True,
                        "data": db_results,
                        "partial": True,
                        "message": "Returning cached results due to scraping error",
                    }
                ),
                200,
            )

        return (
            jsonify(
                {"success": False, "error": "Internal Server Error", "message": str(e)}
            ),
            500,
        )


@api_bp.route("/compare", methods=["GET"])
@rate_limit
def compare_products_endpoint():
    """
    Compare multiple products by their IDs.

    Query Parameters:
        ids (required): Comma-separated product IDs

    Returns:
        JSON with aligned product fields and best-by metrics.
    """
    ids_param = request.args.get("ids", "")

    if not ids_param:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Bad Request",
                    "message": "Product IDs (ids) are required",
                }
            ),
            400,
        )

    try:
        # Parse comma-separated IDs
        product_ids = [int(id.strip()) for id in ids_param.split(",") if id.strip()]
    except ValueError:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Bad Request",
                    "message": "Invalid product ID format. IDs must be integers.",
                }
            ),
            400,
        )

    if not product_ids:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Bad Request",
                    "message": "At least one product ID is required",
                }
            ),
            400,
        )

    if len(product_ids) > 10:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Bad Request",
                    "message": "Maximum 10 products can be compared at once",
                }
            ),
            400,
        )

    try:
        db = get_db()
        products = db.get_products_by_ids(product_ids)

        if not products:
            return (
                jsonify(
                    {
                        "success": True,
                        "data": {"products": [], "best": {}, "count": 0},
                        "message": "No products found for the given IDs",
                    }
                ),
                200,
            )

        # Perform comparison
        comparison_result = compare_products(products)

        return jsonify({"success": True, "data": comparison_result}), 200

    except Exception as e:
        logger.error(f"Comparison error: {e}")
        return (
            jsonify(
                {"success": False, "error": "Internal Server Error", "message": str(e)}
            ),
            500,
        )


@api_bp.route("/products/<int:product_id>", methods=["GET"])
@rate_limit
def get_product_by_id(product_id: int):
    """
    Get detailed product information by ID.
    Triggers background refresh if data is stale beyond TTL.

    Path Parameters:
        product_id: The product ID

    Returns:
        JSON with full product record.
    """
    if not validate_product_id(product_id):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Bad Request",
                    "message": "Invalid product ID",
                }
            ),
            400,
        )

    try:
        db = get_db()
        product = db.get_product_by_id(product_id)

        if not product:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Not Found",
                        "message": f"Product with ID {product_id} not found",
                    }
                ),
                404,
            )

        # Check if data is stale and trigger background refresh
        from flask import current_app

        ttl = current_app.config.get("CACHE_TTL_SECONDS", 300)

        is_stale = db.is_stale(product_id, ttl)
        if is_stale and product.get("url"):
            # Schedule background refresh (non-blocking)
            try:
                scraper_service = ScraperService()
                refreshed = scraper_service.refresh_product(product["url"])
                if refreshed:
                    product = db.get_product_by_id(product_id)
            except Exception as e:
                logger.warning(f"Background refresh failed: {e}")

        # Get price history
        price_history = db.get_price_history(product_id)
        product["price_history"] = price_history
        product["is_stale"] = is_stale

        return jsonify({"success": True, "data": product}), 200

    except Exception as e:
        logger.error(f"Get product error: {e}")
        return (
            jsonify(
                {"success": False, "error": "Internal Server Error", "message": str(e)}
            ),
            500,
        )


@api_bp.route("/products", methods=["GET"])
@rate_limit
def get_product_by_url():
    """
    Get product information by URL.

    Query Parameters:
        url (required): The product URL

    Returns:
        JSON with full product record.
    """
    url = request.args.get("url", "").strip()

    if not url:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Bad Request",
                    "message": "Product URL is required",
                }
            ),
            400,
        )

    if not validate_url(url):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Bad Request",
                    "message": "Invalid URL format",
                }
            ),
            400,
        )

    try:
        db = get_db()

        # Check if product exists in database
        product = db.get_product_by_url(url)

        if product:
            # Check staleness
            from flask import current_app

            ttl = current_app.config.get("CACHE_TTL_SECONDS", 300)
            is_stale = db.is_stale(product["id"], ttl)

            if not is_stale:
                product["price_history"] = db.get_price_history(product["id"])
                product["is_stale"] = False
                return jsonify({"success": True, "data": product, "cached": True}), 200

        # Scrape fresh data
        scraper_service = ScraperService()
        scraped_data = scraper_service.scrape_product(url)

        if scraped_data:
            # Normalize and store
            source = scraped_data.get("source", "unknown")
            normalized = normalize_product(scraped_data, source)
            normalized["url"] = url

            product_id = db.upsert_product(normalized)
            normalized["id"] = product_id
            normalized["price_history"] = db.get_price_history(product_id)
            normalized["is_stale"] = False

            return jsonify({"success": True, "data": normalized, "cached": False}), 200

        return (
            jsonify(
                {
                    "success": False,
                    "error": "Not Found",
                    "message": "Could not scrape product from the given URL",
                }
            ),
            404,
        )

    except ValueError as e:
        return (
            jsonify({"success": False, "error": "Bad Request", "message": str(e)}),
            400,
        )
    except Exception as e:
        logger.error(f"Get product by URL error: {e}")
        return (
            jsonify(
                {"success": False, "error": "Internal Server Error", "message": str(e)}
            ),
            500,
        )


# Legacy endpoints for backward compatibility
@api_bp.route("/scrape", methods=["POST"])
@rate_limit
def scrape_product():
    """
    Scrape product information from a given URL.

    Request Body:
        {
            "url": "https://example.com/product"
        }

    Returns:
        Product information including name, price, etc.
    """
    data = request.get_json()

    if not data or "url" not in data:
        return jsonify({"success": False, "error": "URL is required"}), 400

    url = data["url"]

    if not validate_url(url):
        return jsonify({"success": False, "error": "Invalid URL format"}), 400

    try:
        scraper_service = ScraperService()
        result = scraper_service.scrape_product(url)

        return jsonify({"success": True, "data": result}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/scrape/batch", methods=["POST"])
@rate_limit
def scrape_batch():
    """
    Scrape multiple products from a list of URLs.

    Request Body:
        {
            "urls": ["https://example.com/product1", "https://example.com/product2"]
        }

    Returns:
        List of product information.
    """
    data = request.get_json()

    if not data or "urls" not in data:
        return jsonify({"success": False, "error": "URLs list is required"}), 400

    urls = data["urls"]

    if not isinstance(urls, list) or len(urls) == 0:
        return (
            jsonify({"success": False, "error": "URLs must be a non-empty list"}),
            400,
        )

    # Validate all URLs
    invalid_urls = [url for url in urls if not validate_url(url)]
    if invalid_urls:
        return (
            jsonify({"success": False, "error": f"Invalid URL format: {invalid_urls}"}),
            400,
        )

    try:
        scraper_service = ScraperService()
        results = scraper_service.scrape_batch(urls)

        return jsonify({"success": True, "data": results}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/products/<int:product_id>/prices", methods=["GET"])
@rate_limit
def get_price_history(product_id):
    """
    Get price history for a specific product.

    Query Parameters:
        - days: Number of days of history (default: 30)

    Returns:
        Price history data.
    """
    try:
        db = get_db()
        product = db.get_product_by_id(product_id)

        if not product:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Not Found",
                        "message": f"Product with ID {product_id} not found",
                    }
                ),
                404,
            )

        price_history = db.get_price_history(product_id)

        return (
            jsonify(
                {
                    "success": True,
                    "data": {"product_id": product_id, "prices": price_history},
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Get price history error: {e}")
        return (
            jsonify(
                {"success": False, "error": "Internal Server Error", "message": str(e)}
            ),
            500,
        )


@api_bp.route("/supported-sites", methods=["GET"])
def get_supported_sites():
    """
    Get list of supported e-commerce sites.

    Returns:
        List of supported sites with their configurations.
    """
    scraper_service = ScraperService()
    supported_sites = scraper_service.get_supported_sites()

    # Add status info
    sites_with_status = [
        {
            "name": site["name"],
            "key": site["key"],
            "domains": site["domains"],
            "status": (
                "active"
                if site["key"] in ["amazon", "flipkart", "snapdeal"]
                else "available"
            ),
        }
        for site in supported_sites
    ]

    return jsonify({"success": True, "data": sites_with_status}), 200


@api_bp.route("/stats", methods=["GET"])
def get_stats():
    """
    Get database and cache statistics.

    Returns:
        JSON with database stats and cache info.
    """
    try:
        db = get_db()
        db_stats = db.get_stats()

        cache = get_cache()
        cache_stats = cache.stats()

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "database": db_stats,
                        "cache": cache_stats,
                    },
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Stats error: {e}")
        return (
            jsonify(
                {"success": False, "error": "Internal Server Error", "message": str(e)}
            ),
            500,
        )


@api_bp.route("/products/all", methods=["GET"])
@rate_limit
def get_all_products():
    """
    Get all products from database with pagination.

    Query Parameters:
        page (optional): Page number, default 1
        per_page (optional): Results per page, default 20
        sort (optional): Sort by field, default 'updated_at'
        order (optional): Sort order 'asc' or 'desc', default 'desc'

    Returns:
        JSON with paginated products list.
    """
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Bad Request",
                    "message": "Page and per_page must be integers",
                }
            ),
            400,
        )

    page = max(1, page)
    per_page = max(1, min(100, per_page))

    sort_by = request.args.get("sort", "updated_at")
    sort_order = request.args.get("order", "desc")

    try:
        db = get_db()
        result = db.get_all_products(page, per_page, sort_by, sort_order)

        return jsonify({"success": True, "data": result}), 200

    except Exception as e:
        logger.error(f"Get all products error: {e}")
        return (
            jsonify(
                {"success": False, "error": "Internal Server Error", "message": str(e)}
            ),
            500,
        )


@api_bp.route("/docs", methods=["GET"])
def get_api_docs():
    """
    Get comprehensive API documentation.

    Returns:
        JSON with full API documentation including all endpoints,
        parameters, request/response examples, and supported sites.
    """
    # Check if Selenium is available
    from app.scrapers.selenium_driver import is_selenium_available

    selenium_available = is_selenium_available()

    docs = {
        "api_name": "Price Savvy API",
        "version": "1.0.0",
        "base_url": "/api/v1",
        "description": "Price comparison backend API that scrapes product information from multiple Indian e-commerce websites.",
        "rate_limit": "10 requests per minute per IP",
        "selenium_status": {
            "available": selenium_available,
            "message": (
                "Selenium enabled for JS-rendered sites"
                if selenium_available
                else "Install with: uv pip install selenium webdriver-manager"
            ),
        },
        "supported_sites": {
            "active": [
                {
                    "name": "Amazon",
                    "domains": ["amazon.in", "amazon.com"],
                    "features": ["search", "product_detail", "price_history"],
                    "method": "requests",
                },
                {
                    "name": "Flipkart",
                    "domains": ["flipkart.com"],
                    "features": ["search", "product_detail", "price_history"],
                    "method": "requests",
                },
                {
                    "name": "Snapdeal",
                    "domains": ["snapdeal.com"],
                    "features": ["search", "product_detail"],
                    "method": "requests",
                },
            ],
            "selenium_sites": [
                {
                    "name": "Myntra",
                    "domains": ["myntra.com"],
                    "status": "active" if selenium_available else "requires_selenium",
                    "method": "selenium",
                },
                {
                    "name": "Ajio",
                    "domains": ["ajio.com"],
                    "status": "active" if selenium_available else "requires_selenium",
                    "method": "selenium",
                },
                {
                    "name": "Croma",
                    "domains": ["croma.com"],
                    "status": "active" if selenium_available else "requires_selenium",
                    "method": "selenium",
                },
                {
                    "name": "TataCliq",
                    "domains": ["tatacliq.com"],
                    "status": "active" if selenium_available else "requires_selenium",
                    "method": "selenium",
                },
                {
                    "name": "JioMart",
                    "domains": ["jiomart.com"],
                    "status": "active" if selenium_available else "requires_selenium",
                    "method": "selenium",
                },
                {
                    "name": "Meesho",
                    "domains": ["meesho.com"],
                    "status": "active" if selenium_available else "requires_selenium",
                    "method": "selenium",
                },
            ],
        },
        "endpoints": [
            {
                "path": "/search",
                "method": "GET",
                "description": "Search for products across all active e-commerce sites concurrently",
                "parameters": {
                    "q": {
                        "type": "string",
                        "required": True,
                        "description": "Search query (e.g., 'wireless earbuds')",
                    },
                    "page": {
                        "type": "integer",
                        "required": False,
                        "default": 1,
                        "description": "Page number for pagination",
                    },
                    "per_page": {
                        "type": "integer",
                        "required": False,
                        "default": 20,
                        "max": 100,
                        "description": "Results per page",
                    },
                    "sort": {
                        "type": "string",
                        "required": False,
                        "default": "price",
                        "options": ["price", "rating"],
                        "description": "Sort field",
                    },
                    "order": {
                        "type": "string",
                        "required": False,
                        "default": "asc",
                        "options": ["asc", "desc"],
                        "description": "Sort order",
                    },
                },
                "response_example": {
                    "success": True,
                    "data": {
                        "products": [
                            {
                                "id": 1,
                                "title": "Product Name",
                                "price": 999,
                                "source": "Amazon",
                                "rating": 4.5,
                            }
                        ],
                        "pagination": {
                            "page": 1,
                            "per_page": 20,
                            "total": 100,
                            "pages": 5,
                        },
                        "query": "wireless earbuds",
                    },
                },
            },
            {
                "path": "/compare",
                "method": "GET",
                "description": "Compare multiple products by their IDs to find the best deal",
                "parameters": {
                    "ids": {
                        "type": "string",
                        "required": True,
                        "description": "Comma-separated product IDs (max 10)",
                    },
                },
                "response_example": {
                    "success": True,
                    "data": {
                        "products": [{"id": 1, "title": "...", "price": 999}],
                        "best": {
                            "lowest_price": {"id": 1, "price": 999},
                            "highest_rated": {"id": 2, "rating": 4.8},
                        },
                        "count": 2,
                    },
                },
            },
            {
                "path": "/products/{id}",
                "method": "GET",
                "description": "Get detailed product information by database ID, including price history",
                "parameters": {
                    "id": {
                        "type": "integer",
                        "required": True,
                        "location": "path",
                        "description": "Product ID",
                    },
                },
                "response_example": {
                    "success": True,
                    "data": {
                        "id": 1,
                        "title": "Product Name",
                        "price": 999,
                        "original_price": 1499,
                        "source": "Amazon",
                        "url": "https://amazon.in/...",
                        "rating": 4.5,
                        "image_url": "https://...",
                        "price_history": [
                            {"price": 999, "recorded_at": "2026-02-10T10:00:00"}
                        ],
                        "is_stale": False,
                    },
                },
            },
            {
                "path": "/products",
                "method": "GET",
                "description": "Get or scrape product information by URL",
                "parameters": {
                    "url": {
                        "type": "string",
                        "required": True,
                        "description": "Full product URL from supported site",
                    },
                },
                "response_example": {
                    "success": True,
                    "data": {
                        "id": 1,
                        "title": "...",
                        "price": 999,
                        "source": "Flipkart",
                    },
                    "cached": False,
                },
            },
            {
                "path": "/products/all",
                "method": "GET",
                "description": "Get all products from database with pagination",
                "parameters": {
                    "page": {"type": "integer", "required": False, "default": 1},
                    "per_page": {
                        "type": "integer",
                        "required": False,
                        "default": 20,
                        "max": 100,
                    },
                    "sort": {
                        "type": "string",
                        "required": False,
                        "default": "updated_at",
                        "options": ["price", "rating", "updated_at", "created_at"],
                    },
                    "order": {
                        "type": "string",
                        "required": False,
                        "default": "desc",
                        "options": ["asc", "desc"],
                    },
                },
            },
            {
                "path": "/products/{id}/prices",
                "method": "GET",
                "description": "Get price history for a specific product",
                "parameters": {
                    "id": {"type": "integer", "required": True, "location": "path"},
                },
                "response_example": {
                    "success": True,
                    "data": {
                        "product_id": 1,
                        "prices": [
                            {"price": 999, "recorded_at": "2026-02-10T10:00:00"}
                        ],
                    },
                },
            },
            {
                "path": "/scrape",
                "method": "POST",
                "description": "Scrape a single product URL and return data without saving",
                "request_body": {
                    "url": {
                        "type": "string",
                        "required": True,
                        "description": "Product URL to scrape",
                    }
                },
                "response_example": {
                    "success": True,
                    "data": {"title": "...", "price": 999, "source": "Amazon"},
                },
            },
            {
                "path": "/scrape/batch",
                "method": "POST",
                "description": "Scrape multiple product URLs concurrently",
                "request_body": {
                    "urls": {
                        "type": "array",
                        "required": True,
                        "description": "List of product URLs (max 10)",
                    }
                },
                "response_example": {
                    "success": True,
                    "data": [
                        {
                            "url": "https://...",
                            "success": True,
                            "data": {"title": "..."},
                        },
                        {"url": "https://...", "success": False, "error": "..."},
                    ],
                },
            },
            {
                "path": "/supported-sites",
                "method": "GET",
                "description": "Get list of all supported e-commerce sites and their status",
                "parameters": {},
                "response_example": {
                    "success": True,
                    "data": [
                        {
                            "name": "Amazon",
                            "key": "amazon",
                            "domains": ["amazon.in"],
                            "status": "active",
                        }
                    ],
                },
            },
            {
                "path": "/stats",
                "method": "GET",
                "description": "Get database and cache statistics",
                "parameters": {},
                "response_example": {
                    "success": True,
                    "data": {
                        "database": {"total_products": 100, "total_price_records": 500},
                        "cache": {
                            "size": 10,
                            "max_size": 100,
                            "hits": 50,
                            "misses": 20,
                        },
                    },
                },
            },
            {
                "path": "/docs",
                "method": "GET",
                "description": "Get this API documentation",
                "parameters": {},
            },
        ],
        "error_codes": {
            "400": "Bad Request - Invalid parameters or missing required fields",
            "404": "Not Found - Resource does not exist",
            "429": "Too Many Requests - Rate limit exceeded (10 req/min)",
            "500": "Internal Server Error - Server-side error",
        },
        "response_format": {
            "success_response": {
                "success": True,
                "data": "...",
                "cached": "boolean (optional)",
            },
            "error_response": {
                "success": False,
                "error": "Error Type",
                "message": "Detailed error message",
            },
        },
        "features": {
            "caching": "TTL-based cache (5 minutes) for search queries",
            "rate_limiting": "10 requests per minute per IP using sliding window",
            "concurrent_scraping": "Up to 5 concurrent workers for parallel scraping",
            "price_tracking": "Automatic price history recording on each scrape",
            "deduplication": "Fuzzy matching to merge similar products across sites",
            "normalization": "Consistent data format across all sources",
        },
    }

    return jsonify({"success": True, "data": docs}), 200


# In-memory log buffer for frontend
_log_buffer = []
_max_log_entries = 200


class FrontendLogHandler(logging.Handler):
    """Custom log handler to capture logs for frontend display."""

    def emit(self, record):
        global _log_buffer
        log_entry = {
            "timestamp": (
                self.formatter.formatTime(record) if self.formatter else record.created
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        _log_buffer.insert(0, log_entry)
        if len(_log_buffer) > _max_log_entries:
            _log_buffer.pop()


# Setup frontend log handler
_frontend_handler = FrontendLogHandler()
_frontend_handler.setLevel(logging.INFO)
_frontend_handler.setFormatter(logging.Formatter("%(asctime)s", "%H:%M:%S"))
logging.getLogger().addHandler(_frontend_handler)


@api_bp.route("/logs", methods=["GET"])
def get_logs():
    """
    Get recent server logs for frontend display.

    Query Parameters:
        limit (optional): Number of log entries to return (default 50, max 200)
        level (optional): Filter by log level (INFO, WARNING, ERROR)

    Returns:
        JSON with recent log entries.
    """
    limit = min(int(request.args.get("limit", 50)), _max_log_entries)
    level_filter = request.args.get("level", "").upper()

    logs = _log_buffer[:limit]

    if level_filter:
        logs = [log for log in logs if log["level"] == level_filter]

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "logs": logs,
                    "total": len(_log_buffer),
                    "returned": len(logs),
                },
            }
        ),
        200,
    )


@api_bp.route("/logs/clear", methods=["POST"])
def clear_logs():
    """Clear the log buffer."""
    global _log_buffer
    _log_buffer = []
    return jsonify({"success": True, "message": "Logs cleared"}), 200
