"""
Meesho Scraper - Scraper for Meesho products
As per PRD: BeautifulSoup4 for HTML parsing, Selenium for dynamic content
"""

import re
import json
import logging
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from app.scrapers.selenium_scraper import SeleniumScraper

logger = logging.getLogger(__name__)


class MeeshoScraper(SeleniumScraper):
    """Scraper for Meesho product pages. Uses Selenium for JS-rendered content."""

    def __init__(self, use_selenium: bool = True, **kwargs):
        """Initialize Meesho scraper with Selenium support."""
        super().__init__(use_selenium=use_selenium, **kwargs)

    @property
    def name(self) -> str:
        return "Meesho"

    @property
    def wait_selector(self) -> Optional[str]:
        """Wait for product cards to load."""
        return ".ProductList, .sc-dkzDqf"

    @property
    def supported_domains(self) -> list:
        return ["meesho.com"]

    @property
    def search_url_template(self) -> str:
        """Meesho search URL template."""
        return "https://www.meesho.com/search?q={query}"

    def scrape(self, url: str) -> Dict:
        """
        Scrape product information from Meesho.

        Args:
            url: The Meesho product URL.

        Returns:
            Dictionary containing product information.
        """
        html = self.fetch_page(url)
        return self.parse_product(html, url)

    def parse_product(self, html: str, url: str) -> Dict:
        """
        Parse Meesho product page HTML.

        Args:
            html: The HTML content to parse.
            url: The original URL.

        Returns:
            Dictionary containing parsed product information.
        """
        soup = BeautifulSoup(html, "lxml")

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
        Parse Meesho search results page.

        Args:
            html: Search results page HTML
            max_results: Maximum results to return

        Returns:
            List of product dictionaries
        """
        soup = BeautifulSoup(html, "lxml")
        products = []

        # Try to extract from Next.js script data
        script_products = self._extract_script_products(html)
        if script_products:
            for item in script_products[:max_results]:
                try:
                    product = self._parse_script_product(item)
                    if product:
                        products.append(product)
                except Exception as e:
                    logger.warning(f"Failed to parse Meesho script product: {e}")
            if products:
                logger.info(
                    f"Parsed {len(products)} products from Meesho search (script)"
                )
                return products

        # Fallback: Find product cards in HTML
        product_cards = soup.find_all("div", {"data-testid": re.compile(r"product")})
        if not product_cards:
            # Try generic product containers
            product_cards = soup.find_all(
                "a", href=lambda h: h and "/product/" in h if h else False
            )

        for card in product_cards[: max_results * 2]:
            try:
                product = self._parse_search_card(card)
                if product and product.get("title") and product.get("url"):
                    products.append(product)
                    if len(products) >= max_results:
                        break
            except Exception as e:
                logger.warning(f"Failed to parse Meesho search card: {e}")

        logger.info(f"Parsed {len(products)} products from Meesho search")
        return products

    def _extract_script_products(self, html: str) -> Optional[List]:
        """Extract products from Meesho's Next.js script data."""
        try:
            # Look for __NEXT_DATA__ pattern
            pattern = r'<script id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>'
            match = re.search(pattern, html, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                page_props = data.get("props", {}).get("pageProps", {})
                return page_props.get("initialData", {}).get("catalogList", [])
        except Exception as e:
            logger.debug(f"Failed to extract Meesho script products: {e}")
        return None

    def _parse_script_product(self, item: Dict) -> Optional[Dict]:
        """Parse a product from Meesho's script data."""
        try:
            product_id = item.get("product_id")
            return {
                "source": self.name,
                "url": (
                    f"https://www.meesho.com/product/{product_id}" if product_id else ""
                ),
                "title": item.get("name", ""),
                "price": str(item.get("min_catalog_price", "")),
                "original_price": (
                    str(item.get("min_product_price", ""))
                    if item.get("min_product_price")
                    else None
                ),
                "currency": "INR",
                "rating": (
                    str(
                        item.get("catalog_reviews_summary", {}).get(
                            "average_rating", ""
                        )
                    )
                    if item.get("catalog_reviews_summary")
                    else None
                ),
                "reviews": (
                    str(item.get("catalog_reviews_summary", {}).get("review_count", ""))
                    if item.get("catalog_reviews_summary")
                    else None
                ),
                "image_url": (
                    item.get("product_images", [{}])[0].get("url", "")
                    if item.get("product_images")
                    else None
                ),
            }
        except Exception:
            return None

    def _parse_search_card(self, card: BeautifulSoup) -> Optional[Dict]:
        """Parse a single product card from search results."""
        # If card is an anchor tag
        if card.name == "a":
            url = card.get("href", "")
            if not url.startswith("http"):
                url = f"https://www.meesho.com{url}"
        else:
            link_elem = card.find("a", href=True)
            if not link_elem:
                return None
            url = link_elem.get("href", "")
            if not url.startswith("http"):
                url = f"https://www.meesho.com{url}"

        # Extract title
        title_elem = card.find("p") or card.find("span")
        title = title_elem.get_text(strip=True) if title_elem else None

        # Try from image alt
        if not title:
            img = card.find("img", alt=True)
            if img:
                title = img.get("alt", "")

        if not title:
            return None

        # Extract price - look for ₹ symbol
        price = None
        price_text = card.find(string=lambda t: t and "₹" in t if t else False)
        if price_text:
            price = re.sub(r"[^\d]", "", price_text)

        # Extract image
        img_elem = card.find("img")
        image_url = None
        if img_elem:
            image_url = img_elem.get("src") or img_elem.get("data-src")

        return {
            "source": self.name,
            "url": url,
            "title": title,
            "price": price,
            "original_price": None,
            "currency": "INR",
            "rating": None,
            "reviews": None,
            "image_url": image_url,
        }

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product title."""
        title_elem = soup.find("h1") or soup.find(
            "span", {"data-testid": "product-name"}
        )
        return title_elem.get_text(strip=True) if title_elem else None

    def _extract_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract current price."""
        price_elem = soup.find("h2", {"data-testid": "price"}) or soup.find(
            "span", {"class": re.compile(r"price")}
        )
        if price_elem:
            return re.sub(r"[^\d]", "", price_elem.get_text(strip=True))
        return None

    def _extract_original_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract original price."""
        elem = soup.find("span", {"class": re.compile(r"line-through|strikethrough")})
        if elem:
            return elem.get_text(strip=True)
        return None

    def _extract_rating(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product rating."""
        rating_elem = soup.find("span", {"data-testid": "rating"})
        if rating_elem:
            text = rating_elem.get_text(strip=True)
            match = re.search(r"(\d+\.?\d*)", text)
            if match:
                return match.group(1)
        return None

    def _extract_image(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product image URL."""
        img = soup.find("img", {"data-testid": "product-image"})
        if img:
            return img.get("src") or img.get("data-src")
        return None
