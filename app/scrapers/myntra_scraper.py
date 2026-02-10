"""
Myntra Scraper - Scraper for Myntra products
As per PRD: BeautifulSoup4 for HTML parsing
"""

import re
import json
import logging
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class MyntraScraper(BaseScraper):
    """Scraper for Myntra product pages."""

    @property
    def name(self) -> str:
        return "Myntra"

    @property
    def supported_domains(self) -> list:
        return ["myntra.com"]

    @property
    def search_url_template(self) -> str:
        """Myntra search URL template."""
        return "https://www.myntra.com/{query}"

    def _build_search_url(self, query: str) -> str:
        """Build Myntra search URL - Myntra uses path-based search."""
        # Myntra uses hyphenated search paths
        formatted_query = query.lower().replace(" ", "-")
        return f"https://www.myntra.com/{formatted_query}"

    def search(self, query: str, max_results: int = 20) -> List[Dict]:
        """
        Search for products on Myntra.

        Args:
            query: Search query string
            max_results: Maximum results to return

        Returns:
            List of product dictionaries
        """
        search_url = self._build_search_url(query)
        try:
            html = self.fetch_page(search_url)
            return self.parse_search_results(html, max_results)
        except Exception as e:
            logger.error(f"Myntra search failed: {e}")
            return []

    def scrape(self, url: str) -> Dict:
        """
        Scrape product information from Myntra.

        Args:
            url: The Myntra product URL.

        Returns:
            Dictionary containing product information.
        """
        html = self.fetch_page(url)
        return self.parse_product(html, url)

    def parse_product(self, html: str, url: str) -> Dict:
        """
        Parse Myntra product page HTML.

        Args:
            html: The HTML content to parse.
            url: The original URL.

        Returns:
            Dictionary containing parsed product information.
        """
        soup = BeautifulSoup(html, "lxml")

        # Try to extract data from JSON-LD script
        product_data = self._extract_json_ld(soup)
        if product_data:
            return product_data

        # Fallback to HTML parsing
        title = self._extract_title(soup)
        price = self._extract_price(soup)
        original_price = self._extract_original_price(soup)
        rating = self._extract_rating(soup)
        image_url = self._extract_image(soup)

        return {
            "source": self.name,
            "url": url,
            "title": title,
            "price": price,
            "original_price": original_price,
            "currency": "INR",
            "rating": rating,
            "reviews": None,
            "availability": "In Stock",
            "image_url": image_url,
            "description": None,
        }

    def parse_search_results(self, html: str, max_results: int = 20) -> List[Dict]:
        """
        Parse Myntra search results page.

        Args:
            html: Search results page HTML
            max_results: Maximum results to return

        Returns:
            List of product dictionaries
        """
        soup = BeautifulSoup(html, "lxml")
        products = []

        # Myntra stores product data in a script tag
        script_data = self._extract_search_script_data(html)
        if script_data:
            for item in script_data[:max_results]:
                try:
                    product = self._parse_script_product(item)
                    if product:
                        products.append(product)
                except Exception as e:
                    logger.warning(f"Failed to parse Myntra script product: {e}")

        # Fallback: Parse HTML product cards
        if not products:
            product_cards = soup.find_all("li", class_="product-base")
            for card in product_cards[:max_results]:
                try:
                    product = self._parse_search_card(card)
                    if product and product.get("title") and product.get("url"):
                        products.append(product)
                except Exception as e:
                    logger.warning(f"Failed to parse Myntra search card: {e}")

        logger.info(f"Parsed {len(products)} products from Myntra search")
        return products

    def _extract_search_script_data(self, html: str) -> Optional[List]:
        """Extract product data from Myntra's script tag."""
        try:
            # Look for the __PRELOADED_STATE__ or similar pattern
            pattern = r"window\.__myx\s*=\s*(\{.*?\});"
            match = re.search(pattern, html, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                if "searchData" in data:
                    return data["searchData"].get("results", {}).get("products", [])
        except Exception as e:
            logger.debug(f"Failed to extract Myntra script data: {e}")
        return None

    def _parse_script_product(self, item: Dict) -> Optional[Dict]:
        """Parse a product from Myntra's script data."""
        try:
            product_id = item.get("productId")
            return {
                "source": self.name,
                "url": f"https://www.myntra.com/{item.get('landingPageUrl', '')}",
                "title": f"{item.get('brand', '')} {item.get('product', '')}".strip(),
                "price": str(item.get("price", "")),
                "original_price": str(item.get("mrp", "")) if item.get("mrp") else None,
                "currency": "INR",
                "rating": str(item.get("rating", "")) if item.get("rating") else None,
                "reviews": (
                    str(item.get("ratingCount", ""))
                    if item.get("ratingCount")
                    else None
                ),
                "image_url": item.get("searchImage", ""),
                "product_id": str(product_id) if product_id else None,
            }
        except Exception:
            return None

    def _parse_search_card(self, card: BeautifulSoup) -> Optional[Dict]:
        """Parse a single product card from search results."""
        # Extract link
        link_elem = card.find("a", href=True)
        if not link_elem:
            return None

        href = link_elem.get("href", "")
        url = f"https://www.myntra.com/{href}" if not href.startswith("http") else href

        # Extract brand and title
        brand_elem = card.find("h3", class_="product-brand")
        title_elem = card.find("h4", class_="product-product")

        brand = brand_elem.get_text(strip=True) if brand_elem else ""
        product_name = title_elem.get_text(strip=True) if title_elem else ""
        title = f"{brand} {product_name}".strip()

        if not title:
            return None

        # Extract price
        price_elem = card.find("span", class_="product-discountedPrice") or card.find(
            "span", class_="product-price"
        )
        price = None
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price = re.sub(r"[^\d]", "", price_text)

        # Extract original price
        original_elem = card.find("span", class_="product-strike")
        original_price = None
        if original_elem:
            original_price = original_elem.get_text(strip=True)

        # Extract rating
        rating_elem = card.find("span", class_="product-ratingsContainer")
        rating = None
        if rating_elem:
            rating_text = rating_elem.get_text(strip=True)
            rating_match = re.search(r"(\d+\.?\d*)", rating_text)
            if rating_match:
                rating = rating_match.group(1)

        # Extract image
        img_elem = card.find("img")
        image_url = img_elem.get("src") if img_elem else None

        return {
            "source": self.name,
            "url": url,
            "title": title,
            "price": price,
            "original_price": original_price,
            "currency": "INR",
            "rating": rating,
            "reviews": None,
            "image_url": image_url,
        }

    def _extract_json_ld(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extract product data from JSON-LD schema."""
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                data = json.loads(script.string)
                if data.get("@type") == "Product":
                    return {
                        "source": self.name,
                        "url": data.get("url", ""),
                        "title": data.get("name", ""),
                        "price": str(data.get("offers", {}).get("price", "")),
                        "currency": data.get("offers", {}).get("priceCurrency", "INR"),
                        "rating": str(
                            data.get("aggregateRating", {}).get("ratingValue", "")
                        ),
                        "image_url": data.get("image", ""),
                    }
            except (json.JSONDecodeError, TypeError):
                continue
        return None

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product title."""
        brand = soup.find("h1", class_="pdp-title")
        name = soup.find("h1", class_="pdp-name")

        parts = []
        if brand:
            parts.append(brand.get_text(strip=True))
        if name:
            parts.append(name.get_text(strip=True))

        return " ".join(parts) if parts else None

    def _extract_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract current price."""
        price_elem = soup.find("span", class_="pdp-price") or soup.find(
            "span", class_="pdp-discountedPrice"
        )
        if price_elem:
            return re.sub(r"[^\d]", "", price_elem.get_text(strip=True))
        return None

    def _extract_original_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract original price."""
        elem = soup.find("span", class_="pdp-mrp")
        if elem:
            return elem.get_text(strip=True)
        return None

    def _extract_rating(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product rating."""
        rating_elem = soup.find("div", class_="index-overallRating")
        if rating_elem:
            return rating_elem.get_text(strip=True)
        return None

    def _extract_image(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product image URL."""
        img = soup.find("img", class_="image-grid-image")
        return img.get("src") if img else None
