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


@api_bp.route('/search', methods=['GET'])
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
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({
            'success': False,
            'error': 'Bad Request',
            'message': 'Search query (q) is required'
        }), 400
    
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Bad Request',
            'message': 'Page and per_page must be integers'
        }), 400
    
    # Validate pagination
    page = max(1, page)
    per_page = max(1, min(100, per_page))  # Limit to 100 per page
    
    sort_by = request.args.get('sort', 'price')
    sort_order = request.args.get('order', 'asc')
    
    # Validate sort parameters
    if sort_by not in ('price', 'rating'):
        sort_by = 'price'
    if sort_order not in ('asc', 'desc'):
        sort_order = 'asc'
    
    # Check cache first
    cache = get_cache()
    cache_key = f"search:{query}:{page}:{per_page}:{sort_by}:{sort_order}"
    cached_result = cache.get(cache_key)
    
    if cached_result:
        logger.info(f"Cache hit for search: {query}")
        return jsonify({
            'success': True,
            'data': cached_result,
            'cached': True
        }), 200
    
    try:
        # Perform concurrent scraping from multiple sources
        scraper_service = ScraperService()
        raw_results = scraper_service.search_products(query)
        
        # Normalize all results
        normalized_products = []
        for result in raw_results:
            if result.get('success') and result.get('products'):
                source = result.get('source', 'unknown')
                for product in result['products']:
                    normalized = normalize_product(product, source)
                    normalized_products.append(normalized)
        
        # Merge duplicates using fuzzy matching
        deduplicated = merge_duplicates(normalized_products)
        
        # Store in database
        db = get_db()
        for product in deduplicated:
            try:
                product_id = db.upsert_product(product)
                product['id'] = product_id
            except Exception as e:
                logger.error(f"Failed to store product: {e}")
        
        # Sort results
        reverse = sort_order == 'desc'
        if sort_by == 'price':
            deduplicated.sort(key=lambda p: p.get('best_price') or p.get('price') or 0, reverse=reverse)
        elif sort_by == 'rating':
            deduplicated.sort(key=lambda p: p.get('rating') or 0, reverse=reverse)
        
        # Paginate
        total = len(deduplicated)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_products = deduplicated[start_idx:end_idx]
        
        result = {
            'products': paginated_products,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page if total > 0 else 0,
                'has_next': end_idx < total,
                'has_prev': page > 1
            },
            'query': query,
            'sort': {
                'by': sort_by,
                'order': sort_order
            }
        }
        
        # Cache the result
        cache.set(cache_key, result)
        
        return jsonify({
            'success': True,
            'data': result,
            'cached': False
        }), 200
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        
        # Try to return cached/database results as fallback
        db = get_db()
        db_results = db.search_products(query, page, per_page, sort_by, sort_order)
        
        if db_results.get('products'):
            return jsonify({
                'success': True,
                'data': db_results,
                'partial': True,
                'message': 'Returning cached results due to scraping error'
            }), 200
        
        return jsonify({
            'success': False,
            'error': 'Internal Server Error',
            'message': str(e)
        }), 500


@api_bp.route('/compare', methods=['GET'])
@rate_limit
def compare_products_endpoint():
    """
    Compare multiple products by their IDs.
    
    Query Parameters:
        ids (required): Comma-separated product IDs
    
    Returns:
        JSON with aligned product fields and best-by metrics.
    """
    ids_param = request.args.get('ids', '')
    
    if not ids_param:
        return jsonify({
            'success': False,
            'error': 'Bad Request',
            'message': 'Product IDs (ids) are required'
        }), 400
    
    try:
        # Parse comma-separated IDs
        product_ids = [int(id.strip()) for id in ids_param.split(',') if id.strip()]
    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Bad Request',
            'message': 'Invalid product ID format. IDs must be integers.'
        }), 400
    
    if not product_ids:
        return jsonify({
            'success': False,
            'error': 'Bad Request',
            'message': 'At least one product ID is required'
        }), 400
    
    if len(product_ids) > 10:
        return jsonify({
            'success': False,
            'error': 'Bad Request',
            'message': 'Maximum 10 products can be compared at once'
        }), 400
    
    try:
        db = get_db()
        products = db.get_products_by_ids(product_ids)
        
        if not products:
            return jsonify({
                'success': True,
                'data': {
                    'products': [],
                    'best': {},
                    'count': 0
                },
                'message': 'No products found for the given IDs'
            }), 200
        
        # Perform comparison
        comparison_result = compare_products(products)
        
        return jsonify({
            'success': True,
            'data': comparison_result
        }), 200
        
    except Exception as e:
        logger.error(f"Comparison error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal Server Error',
            'message': str(e)
        }), 500


@api_bp.route('/products/<int:product_id>', methods=['GET'])
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
        return jsonify({
            'success': False,
            'error': 'Bad Request',
            'message': 'Invalid product ID'
        }), 400
    
    try:
        db = get_db()
        product = db.get_product_by_id(product_id)
        
        if not product:
            return jsonify({
                'success': False,
                'error': 'Not Found',
                'message': f'Product with ID {product_id} not found'
            }), 404
        
        # Check if data is stale and trigger background refresh
        from flask import current_app
        ttl = current_app.config.get('CACHE_TTL_SECONDS', 300)
        
        is_stale = db.is_stale(product_id, ttl)
        if is_stale and product.get('url'):
            # Schedule background refresh (non-blocking)
            try:
                scraper_service = ScraperService()
                refreshed = scraper_service.refresh_product(product['url'])
                if refreshed:
                    product = db.get_product_by_id(product_id)
            except Exception as e:
                logger.warning(f"Background refresh failed: {e}")
        
        # Get price history
        price_history = db.get_price_history(product_id)
        product['price_history'] = price_history
        product['is_stale'] = is_stale
        
        return jsonify({
            'success': True,
            'data': product
        }), 200
        
    except Exception as e:
        logger.error(f"Get product error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal Server Error',
            'message': str(e)
        }), 500


@api_bp.route('/products', methods=['GET'])
@rate_limit
def get_product_by_url():
    """
    Get product information by URL.
    
    Query Parameters:
        url (required): The product URL
    
    Returns:
        JSON with full product record.
    """
    url = request.args.get('url', '').strip()
    
    if not url:
        return jsonify({
            'success': False,
            'error': 'Bad Request',
            'message': 'Product URL is required'
        }), 400
    
    if not validate_url(url):
        return jsonify({
            'success': False,
            'error': 'Bad Request',
            'message': 'Invalid URL format'
        }), 400
    
    try:
        db = get_db()
        
        # Check if product exists in database
        product = db.get_product_by_url(url)
        
        if product:
            # Check staleness
            from flask import current_app
            ttl = current_app.config.get('CACHE_TTL_SECONDS', 300)
            is_stale = db.is_stale(product['id'], ttl)
            
            if not is_stale:
                product['price_history'] = db.get_price_history(product['id'])
                product['is_stale'] = False
                return jsonify({
                    'success': True,
                    'data': product,
                    'cached': True
                }), 200
        
        # Scrape fresh data
        scraper_service = ScraperService()
        scraped_data = scraper_service.scrape_product(url)
        
        if scraped_data:
            # Normalize and store
            source = scraped_data.get('source', 'unknown')
            normalized = normalize_product(scraped_data, source)
            normalized['url'] = url
            
            product_id = db.upsert_product(normalized)
            normalized['id'] = product_id
            normalized['price_history'] = db.get_price_history(product_id)
            normalized['is_stale'] = False
            
            return jsonify({
                'success': True,
                'data': normalized,
                'cached': False
            }), 200
        
        return jsonify({
            'success': False,
            'error': 'Not Found',
            'message': 'Could not scrape product from the given URL'
        }), 404
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': 'Bad Request',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Get product by URL error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal Server Error',
            'message': str(e)
        }), 500


# Legacy endpoints for backward compatibility
@api_bp.route('/scrape', methods=['POST'])
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
    
    if not data or 'url' not in data:
        return jsonify({
            'success': False,
            'error': 'URL is required'
        }), 400
    
    url = data['url']
    
    if not validate_url(url):
        return jsonify({
            'success': False,
            'error': 'Invalid URL format'
        }), 400
    
    try:
        scraper_service = ScraperService()
        result = scraper_service.scrape_product(url)
        
        return jsonify({
            'success': True,
            'data': result
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/scrape/batch', methods=['POST'])
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
    
    if not data or 'urls' not in data:
        return jsonify({
            'success': False,
            'error': 'URLs list is required'
        }), 400
    
    urls = data['urls']
    
    if not isinstance(urls, list) or len(urls) == 0:
        return jsonify({
            'success': False,
            'error': 'URLs must be a non-empty list'
        }), 400
    
    # Validate all URLs
    invalid_urls = [url for url in urls if not validate_url(url)]
    if invalid_urls:
        return jsonify({
            'success': False,
            'error': f'Invalid URL format: {invalid_urls}'
        }), 400
    
    try:
        scraper_service = ScraperService()
        results = scraper_service.scrape_batch(urls)
        
        return jsonify({
            'success': True,
            'data': results
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/products/<int:product_id>/prices', methods=['GET'])
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
            return jsonify({
                'success': False,
                'error': 'Not Found',
                'message': f'Product with ID {product_id} not found'
            }), 404
        
        price_history = db.get_price_history(product_id)
        
        return jsonify({
            'success': True,
            'data': {
                'product_id': product_id,
                'prices': price_history
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Get price history error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal Server Error',
            'message': str(e)
        }), 500


@api_bp.route('/supported-sites', methods=['GET'])
def get_supported_sites():
    """
    Get list of supported e-commerce sites.
    
    Returns:
        List of supported sites with their configurations.
    """
    supported_sites = [
        {
            'name': 'Amazon India',
            'domain': 'amazon.in',
            'status': 'active'
        },
        {
            'name': 'Amazon',
            'domain': 'amazon.com',
            'status': 'active'
        },
        {
            'name': 'Flipkart',
            'domain': 'flipkart.com',
            'status': 'active'
        }
    ]
    
    return jsonify({
        'success': True,
        'data': supported_sites
    }), 200
