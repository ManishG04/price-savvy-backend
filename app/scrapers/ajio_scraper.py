"""
Ajio Scraper - Scraper for Ajio products
As per PRD: BeautifulSoup4 for HTML parsing
"""

import re
import json
import logging
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class AjioScraper(BaseScraper):
    """Scraper for Ajio product pages."""

    @property
    def name(self) -> str:
        return "Ajio"

    @property
    def supported_domains(self) -> list:
        return ["ajio.com"]

    @property
    def search_url_template(self) -> str:
        """Ajio search URL template."""
        return "https://www.ajio.com/search/?text={query}"

    def scrape(self, url: str) -> Dict:
        """
        Scrape product information from Ajio.

        Args:
            url: The Ajio product URL.

        Returns:
            Dictionary containing product information.
        """
        html = self.fetch_page(url)
        return self.parse_product(html, url)

    def parse_product(self, html: str, url: str) -> Dict:
        """
        Parse Ajio product page HTML.

        Args:
            html: The HTML content to parse.
            url: The original URL.

        Returns:
            Dictionary containing parsed product information.
        """
        soup = BeautifulSoup(html, "lxml")

        # Try JSON-LD first
        product_data = self._extract_json_ld(soup)
        if product_data:
            product_data["url"] = url
            return product_data

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
        Parse Ajio search results page.

        Args:
            html: Search results page HTML
            max_results: Maximum results to return

        Returns:
            List of product dictionaries
        """
        soup = BeautifulSoup(html, "lxml")
        products = []

        # Try to extract from script data first
        script_products = self._extract_script_products(html)
        if script_products:
            for item in script_products[:max_results]:
                try:
                    product = self._parse_script_product(item)
                    if product:
                        products.append(product)
                except Exception as e:
                    logger.warning(f"Failed to parse Ajio script product: {e}")
            if products:
                logger.info(
                    f"Parsed {len(products)} products from Ajio search (script)"
                )
                return products

        # Fallback: Parse HTML cards
        product_cards = soup.find_all("div", class_="item")
        if not product_cards:
            product_cards = soup.find_all("div", {"class": re.compile(r"product")})

        for card in product_cards[: max_results * 2]:
            try:
                product = self._parse_search_card(card)
                if product and product.get("title") and product.get("url"):
                    products.append(product)
                    if len(products) >= max_results:
                        break
            except Exception as e:
                logger.warning(f"Failed to parse Ajio search card: {e}")

        logger.info(f"Parsed {len(products)} products from Ajio search")
        return products

    def _extract_script_products(self, html: str) -> Optional[List]:
        """Extract products from Ajio's embedded JSON."""
        try:
            # Look for __PRELOADED_STATE__ pattern
            pattern = r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});"
            match = re.search(pattern, html, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                return data.get("grid", {}).get("entities", [])
        except Exception as e:
            logger.debug(f"Failed to extract Ajio script products: {e}")
        return None

    def _parse_script_product(self, item: Dict) -> Optional[Dict]:
        """Parse a product from Ajio's script data."""
        try:
            return {
                "source": self.name,
                "url": f"https://www.ajio.com{item.get('url', '')}",
                "title": f"{item.get('brandName', '')} {item.get('name', '')}".strip(),
                "price": str(item.get("price", {}).get("value", "")),
                "original_price": (
                    str(item.get("wasPriceData", {}).get("value", ""))
                    if item.get("wasPriceData")
                    else None
                ),
                "currency": "INR",
                "rating": str(item.get("rating", "")) if item.get("rating") else None,
                "reviews": None,
                "image_url": (
                    item.get("images", [{}])[0].get("url", "")
                    if item.get("images")
                    else None
                ),
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
        url = f"https://www.ajio.com{href}" if href.startswith("/") else href

        # Extract brand and title
        brand_elem = card.find("div", class_="brand")
        name_elem = card.find("div", class_="name")

        brand = brand_elem.get_text(strip=True) if brand_elem else ""
        name = name_elem.get_text(strip=True) if name_elem else ""
        title = f"{brand} {name}".strip()

        # Try alternate title extraction
        if not title:
            img = card.find("img", alt=True)
            if img:
                title = img.get("alt", "")

        if not title:
            return None

        # Extract price
        price_elem = card.find("span", class_="price")
        price = None
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price = re.sub(r"[^\d]", "", price_text)

        # Extract original price
        original_elem = card.find("span", class_="orginal-price")
        original_price = original_elem.get_text(strip=True) if original_elem else None

        # Extract discount
        discount_elem = card.find("span", class_="discount")

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
            "rating": None,
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
                    offers = data.get("offers", {})
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    return {
                        "source": self.name,
                        "title": data.get("name", ""),
                        "price": str(offers.get("price", "")),
                        "currency": offers.get("priceCurrency", "INR"),
                        "rating": str(
                            data.get("aggregateRating", {}).get("ratingValue", "")
                        ),
                        "image_url": data.get("image", ""),
                        "description": data.get("description", ""),
                    }
            except (json.JSONDecodeError, TypeError):
                continue
        return None

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product title."""
        brand = soup.find("h2", class_="brand-name")
        name = soup.find("h1", class_="prod-name")

        parts = []
        if brand:
            parts.append(brand.get_text(strip=True))
        if name:
            parts.append(name.get_text(strip=True))

        return " ".join(parts) if parts else None

    def _extract_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract current price."""
        price_elem = soup.find("div", class_="prod-sp")
        if price_elem:
            return re.sub(r"[^\d]", "", price_elem.get_text(strip=True))
        return None

    def _extract_original_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract original price."""
        elem = soup.find("span", class_="prod-cp")
        if elem:
            return elem.get_text(strip=True)
        return None

    def _extract_rating(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product rating."""
        rating_elem = soup.find("span", class_="rating")
        if rating_elem:
            text = rating_elem.get_text(strip=True)
            match = re.search(r"(\d+\.?\d*)", text)
            if match:
                return match.group(1)
        return None

    def _extract_image(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product image URL."""
        img = soup.find("img", class_="rilrtl-lazy-img")
        if img:
            return img.get("src") or img.get("data-src")
        return None
