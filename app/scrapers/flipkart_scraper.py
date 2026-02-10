"""
Flipkart Scraper - Scraper for Flipkart products
As per PRD: BeautifulSoup4 for HTML parsing
"""

import logging
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class FlipkartScraper(BaseScraper):
    """Scraper for Flipkart product pages."""

    @property
    def name(self) -> str:
        return "Flipkart"

    @property
    def supported_domains(self) -> list:
        return ["flipkart.com"]

    @property
    def search_url_template(self) -> str:
        """Flipkart search URL template."""
        return "https://www.flipkart.com/search?q={query}"

    def scrape(self, url: str) -> Dict:
        """
        Scrape product information from Flipkart.

        Args:
            url: The Flipkart product URL.

        Returns:
            Dictionary containing product information.
        """
        html = self.fetch_page(url)
        return self.parse_product(html, url)

    def parse_product(self, html: str, url: str) -> Dict:
        """
        Parse Flipkart product page HTML.

        Args:
            html: The HTML content to parse.
            url: The original URL.

        Returns:
            Dictionary containing parsed product information.
        """
        soup = BeautifulSoup(html, "lxml")

        # Extract product title
        title_elem = soup.find("span", {"class": "VU-ZEz"}) or soup.find(
            "h1", {"class": "yhB1nd"}
        )
        title = title_elem.get_text(strip=True) if title_elem else None

        # Extract price
        price = self._extract_price(soup)

        # Extract original price (if on sale)
        original_price = self._extract_original_price(soup)

        # Extract rating
        rating_elem = soup.find("div", {"class": "XQDdHH"})
        rating = rating_elem.get_text(strip=True) if rating_elem else None

        # Extract number of ratings and reviews
        reviews_elem = soup.find("span", {"class": "Wphh3N"})
        reviews = reviews_elem.get_text(strip=True) if reviews_elem else None

        # Extract availability
        availability = self._extract_availability(soup)

        # Extract image URL
        image_elem = soup.find("img", {"class": "DByuf4"}) or soup.find(
            "img", {"class": "_396cs4"}
        )
        image_url = image_elem.get("src") if image_elem else None

        # Extract description
        description = self._extract_description(soup)

        return {
            "source": self.name,
            "url": url,
            "title": title,
            "price": price,
            "original_price": original_price,
            "currency": "INR",
            "rating": rating,
            "reviews": reviews,
            "availability": availability,
            "image_url": image_url,
            "description": description,
        }

    def parse_search_results(self, html: str, max_results: int = 20) -> List[Dict]:
        """
        Parse Flipkart search results page.

        Args:
            html: Search results page HTML
            max_results: Maximum results to return

        Returns:
            List of product dictionaries
        """
        soup = BeautifulSoup(html, "lxml")
        products = []

        # Flipkart uses data-id attribute on product container divs
        # This is the most reliable selector as class names are dynamically generated
        product_cards = soup.find_all("div", {"data-id": True})

        if not product_cards:
            # Fallback: Try older class-based selectors
            product_cards = soup.find_all("div", {"class": "_1AtVbE"})
            if not product_cards:
                product_cards = soup.find_all("div", {"class": "cPHDOP"})

        for card in product_cards[: max_results * 2]:  # Get more in case some fail
            try:
                product = self._parse_search_card(card)
                if product and product.get("title") and product.get("url"):
                    products.append(product)
                    if len(products) >= max_results:
                        break
            except Exception as e:
                logger.warning(f"Failed to parse Flipkart search card: {e}")
                continue

        logger.info(f"Parsed {len(products)} products from Flipkart search")
        return products

    def _parse_search_card(self, card: BeautifulSoup) -> Optional[Dict]:
        """Parse a single product card from search results."""
        # Extract URL - look for anchor tag with product link (/p/ in href)
        link_elem = card.find("a", href=lambda h: h and "/p/" in h if h else False)
        if not link_elem:
            return None

        href = link_elem.get("href", "")
        url = f"https://www.flipkart.com{href}" if href.startswith("/") else href

        # Extract title from image alt attribute (most reliable)
        img_elem = card.find("img", alt=True)
        title = img_elem.get("alt") if img_elem else None

        # Fallback: try to get title from anchor text or other elements
        if not title:
            title_elem = card.find("a", {"class": lambda c: c})
            if title_elem:
                title = title_elem.get_text(strip=True)

        if not title:
            return None

        # Extract price - find text containing ₹ symbol
        price = None
        price_text = card.find(string=lambda t: t and "₹" in t if t else False)
        if price_text:
            # Clean the price: remove ₹ and commas
            price = price_text.strip().replace("₹", "").replace(",", "")
            # Get just the numeric part
            import re

            price_match = re.search(r"[\d,]+", price)
            if price_match:
                price = price_match.group().replace(",", "")

        # Extract image URL
        image_url = img_elem.get("src") if img_elem else None

        # Extract rating - look for short numeric text like "4.2" or "3.9"
        rating = None
        rating_candidates = card.find_all("div")
        for div in rating_candidates:
            text = div.get_text(strip=True)
            if text and len(text) <= 3:
                import re

                if re.match(r"^\d(\.\d)?$", text):
                    rating = text
                    break

        # Extract original price (strikethrough price)
        original_price = None
        all_prices = card.find_all(string=lambda t: t and "₹" in t if t else False)
        if len(all_prices) > 1:
            # Second price is usually the original/strikethrough price
            original_price = all_prices[1].strip()

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

    def _extract_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract the current price from the page."""
        # Try different price selectors
        price_selectors = [
            {"class": "Nx9bqj CxhGGd"},
            {"class": "_30jeq3 _16Jk6d"},
            {"class": "_30jeq3"},
        ]

        for selector in price_selectors:
            elem = soup.find("div", selector)
            if elem:
                return elem.get_text(strip=True)

        return None

    def _extract_original_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract the original price (before discount)."""
        elem = soup.find("div", {"class": "yRaY8j"}) or soup.find(
            "div", {"class": "_3I9_wc"}
        )
        if elem:
            return elem.get_text(strip=True)
        return None

    def _extract_availability(self, soup: BeautifulSoup) -> str:
        """Extract product availability."""
        # Check for out of stock
        out_of_stock = soup.find("div", {"class": "_16FRp0"})
        if out_of_stock and "out of stock" in out_of_stock.get_text().lower():
            return "Out of Stock"

        # Check for buy button
        buy_button = soup.find("button", {"class": "_2KpZ6l"})
        if buy_button:
            return "In Stock"

        return "Unknown"

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product description/highlights."""
        highlights = soup.find("div", {"class": "_2418kt"})
        if highlights:
            items = highlights.find_all("li", {"class": "_21Ahn-"})
            if items:
                return " | ".join([item.get_text(strip=True) for item in items[:5]])
        return None
