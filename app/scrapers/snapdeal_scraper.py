"""
Snapdeal Scraper - Scraper for Snapdeal products
As per PRD: BeautifulSoup4 for HTML parsing
"""

import re
import json
import logging
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class SnapdealScraper(BaseScraper):
    """Scraper for Snapdeal product pages."""

    @property
    def name(self) -> str:
        return "Snapdeal"

    @property
    def supported_domains(self) -> list:
        return ["snapdeal.com"]

    @property
    def search_url_template(self) -> str:
        """Snapdeal search URL template."""
        return "https://www.snapdeal.com/search?keyword={query}"

    def scrape(self, url: str) -> Dict:
        """
        Scrape product information from Snapdeal.

        Args:
            url: The Snapdeal product URL.

        Returns:
            Dictionary containing product information.
        """
        html = self.fetch_page(url)
        return self.parse_product(html, url)

    def parse_product(self, html: str, url: str) -> Dict:
        """
        Parse Snapdeal product page HTML.

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
        availability = self._extract_availability(soup)

        return {
            "source": self.name,
            "url": url,
            "title": title,
            "price": price,
            "original_price": original_price,
            "currency": "INR",
            "rating": rating,
            "reviews": None,
            "availability": availability,
            "image_url": image_url,
            "description": None,
        }

    def parse_search_results(self, html: str, max_results: int = 20) -> List[Dict]:
        """
        Parse Snapdeal search results page.

        Args:
            html: Search results page HTML
            max_results: Maximum results to return

        Returns:
            List of product dictionaries
        """
        soup = BeautifulSoup(html, "lxml")
        products = []

        # Find product cards - Snapdeal uses product-tuple-listing
        product_cards = soup.find_all("div", class_="product-tuple-listing")
        if not product_cards:
            product_cards = soup.find_all(
                "div", {"class": re.compile(r"product-tuple")}
            )

        for card in product_cards[: max_results * 2]:
            try:
                product = self._parse_search_card(card)
                if product and product.get("title") and product.get("url"):
                    products.append(product)
                    if len(products) >= max_results:
                        break
            except Exception as e:
                logger.warning(f"Failed to parse Snapdeal search card: {e}")

        logger.info(f"Parsed {len(products)} products from Snapdeal search")
        return products

    def _parse_search_card(self, card: BeautifulSoup) -> Optional[Dict]:
        """Parse a single product card from search results."""
        # Extract link
        link_elem = card.find("a", class_="dp-widget-link")
        if not link_elem:
            link_elem = card.find("a", href=True)

        if not link_elem:
            return None

        url = link_elem.get("href", "")

        # Extract title
        title_elem = card.find("p", class_="product-title")
        title = title_elem.get_text(strip=True) if title_elem else None

        # Try from image alt
        if not title:
            img = card.find("img", alt=True)
            if img:
                title = img.get("alt", "")

        if not title:
            return None

        # Extract price
        price = None
        price_elem = card.find("span", class_="product-price")
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price = re.sub(r"[^\d]", "", price_text)

        # Extract original price
        original_elem = card.find("span", class_="product-desc-price")
        original_price = original_elem.get_text(strip=True) if original_elem else None

        # Extract discount
        discount_elem = card.find("div", class_="product-discount")

        # Extract rating
        rating = None
        rating_elem = card.find("div", class_="filled-stars")
        if rating_elem:
            style = rating_elem.get("style", "")
            # Parse width percentage to get rating
            match = re.search(r"width:\s*(\d+)%", style)
            if match:
                # Convert percentage to 5-star scale
                rating = str(round(float(match.group(1)) / 20, 1))

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
            "original_price": original_price,
            "currency": "INR",
            "rating": rating,
            "reviews": None,
            "image_url": image_url,
        }

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product title."""
        title_elem = soup.find("h1", class_="pdp-e-i-head")
        return title_elem.get_text(strip=True) if title_elem else None

    def _extract_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract current price."""
        price_elem = soup.find("span", class_="payBlkBig")
        if price_elem:
            return re.sub(r"[^\d]", "", price_elem.get_text(strip=True))
        return None

    def _extract_original_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract original price."""
        elem = soup.find("span", class_="pdpCutPrice")
        if elem:
            return elem.get_text(strip=True)
        return None

    def _extract_rating(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product rating."""
        rating_elem = soup.find("span", class_="avrg-rating")
        if rating_elem:
            return rating_elem.get_text(strip=True)
        return None

    def _extract_availability(self, soup: BeautifulSoup) -> str:
        """Extract availability status."""
        out_of_stock = soup.find("div", class_="sold-out-err")
        if out_of_stock:
            return "Out of Stock"
        return "In Stock"

    def _extract_image(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product image URL."""
        img = soup.find("img", id="bx-slider-left-image-main")
        if img:
            return img.get("src") or img.get("data-src")
        return None
