"""
Tata CLiQ Scraper - Scraper for Tata CLiQ products
As per PRD: BeautifulSoup4 for HTML parsing, Selenium for dynamic content
"""

import re
import json
import logging
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from app.scrapers.selenium_scraper import SeleniumScraper

logger = logging.getLogger(__name__)


class TataCliqScraper(SeleniumScraper):
    """Scraper for Tata CLiQ product pages. Uses Selenium for JS-rendered content."""

    def __init__(self, use_selenium: bool = True, **kwargs):
        """Initialize TataCliq scraper with Selenium support."""
        super().__init__(use_selenium=use_selenium, **kwargs)

    @property
    def name(self) -> str:
        return "TataCliq"

    @property
    def wait_selector(self) -> Optional[str]:
        """Wait for product grid to load."""
        return ".ProductModule__base, .ProductList"

    @property
    def supported_domains(self) -> list:
        return ["tatacliq.com"]

    @property
    def search_url_template(self) -> str:
        """Tata CLiQ search URL template."""
        return "https://www.tatacliq.com/search/?searchCategory=all&text={query}"

    def scrape(self, url: str) -> Dict:
        """
        Scrape product information from Tata CLiQ.

        Args:
            url: The Tata CLiQ product URL.

        Returns:
            Dictionary containing product information.
        """
        html = self.fetch_page(url)
        return self.parse_product(html, url)

    def parse_product(self, html: str, url: str) -> Dict:
        """
        Parse Tata CLiQ product page HTML.

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
        Parse Tata CLiQ search results page.

        Args:
            html: Search results page HTML
            max_results: Maximum results to return

        Returns:
            List of product dictionaries
        """
        soup = BeautifulSoup(html, "lxml")
        products = []

        # Try to extract from script data
        script_products = self._extract_script_products(html)
        if script_products:
            for item in script_products[:max_results]:
                try:
                    product = self._parse_script_product(item)
                    if product:
                        products.append(product)
                except Exception as e:
                    logger.warning(f"Failed to parse TataCliq script product: {e}")
            if products:
                logger.info(
                    f"Parsed {len(products)} products from TataCliq search (script)"
                )
                return products

        # Fallback: Parse HTML cards
        product_cards = soup.find_all("div", {"class": re.compile(r"ProductModule")})
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
                logger.warning(f"Failed to parse TataCliq search card: {e}")

        logger.info(f"Parsed {len(products)} products from TataCliq search")
        return products

    def _extract_script_products(self, html: str) -> Optional[List]:
        """Extract products from TataCliq's embedded JSON."""
        try:
            # Look for __NEXT_DATA__ pattern (Next.js)
            pattern = r'<script id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>'
            match = re.search(pattern, html, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                return (
                    data.get("props", {})
                    .get("pageProps", {})
                    .get("searchResult", {})
                    .get("products", [])
                )
        except Exception as e:
            logger.debug(f"Failed to extract TataCliq script products: {e}")
        return None

    def _parse_script_product(self, item: Dict) -> Optional[Dict]:
        """Parse a product from TataCliq's script data."""
        try:
            return {
                "source": self.name,
                "url": f"https://www.tatacliq.com{item.get('webURL', '')}",
                "title": f"{item.get('brandName', '')} {item.get('productName', '')}".strip(),
                "price": str(item.get("price", {}).get("formattedValue", ""))
                .replace("₹", "")
                .replace(",", ""),
                "original_price": (
                    str(item.get("mrp", {}).get("formattedValue", ""))
                    if item.get("mrp")
                    else None
                ),
                "currency": "INR",
                "rating": (
                    str(item.get("averageRating", ""))
                    if item.get("averageRating")
                    else None
                ),
                "reviews": (
                    str(item.get("numberOfReviews", ""))
                    if item.get("numberOfReviews")
                    else None
                ),
                "image_url": item.get("imageURL", ""),
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
        url = f"https://www.tatacliq.com{href}" if href.startswith("/") else href

        # Extract brand and title
        brand_elem = card.find("h3") or card.find(
            "span", class_="ProductModule__brandName"
        )
        title_elem = card.find("p") or card.find(
            "span", class_="ProductModule__productName"
        )

        brand = brand_elem.get_text(strip=True) if brand_elem else ""
        name = title_elem.get_text(strip=True) if title_elem else ""
        title = f"{brand} {name}".strip()

        # Try from image alt
        if not title:
            img = card.find("img", alt=True)
            if img:
                title = img.get("alt", "")

        if not title:
            return None

        # Extract price
        price = None
        price_elem = card.find("span", {"class": re.compile(r"price|Price")})
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price = re.sub(r"[^\d]", "", price_text)

        # Also try finding any element with ₹
        if not price:
            price_text = card.find(string=lambda t: t and "₹" in t if t else False)
            if price_text:
                price = re.sub(r"[^\d]", "", price_text)

        # Extract original price
        original_elem = card.find("span", class_="ProductModule__mrp")
        original_price = original_elem.get_text(strip=True) if original_elem else None

        # Extract rating
        rating = None
        rating_elem = card.find("span", class_="ProductModule__rating")
        if rating_elem:
            rating_text = rating_elem.get_text(strip=True)
            rating_match = re.search(r"(\d+\.?\d*)", rating_text)
            if rating_match:
                rating = rating_match.group(1)

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
        brand = soup.find("h1", class_="ProductDetailsMainCard__brandName")
        name = soup.find("p", class_="ProductDetailsMainCard__productName")

        parts = []
        if brand:
            parts.append(brand.get_text(strip=True))
        if name:
            parts.append(name.get_text(strip=True))

        return " ".join(parts) if parts else None

    def _extract_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract current price."""
        price_elem = soup.find("span", class_="ProductDetailsMainCard__price")
        if price_elem:
            return re.sub(r"[^\d]", "", price_elem.get_text(strip=True))
        return None

    def _extract_original_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract original price."""
        elem = soup.find("span", class_="ProductDetailsMainCard__mrp")
        if elem:
            return elem.get_text(strip=True)
        return None

    def _extract_rating(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product rating."""
        rating_elem = soup.find("span", class_="ProductDetailsMainCard__rating")
        if rating_elem:
            text = rating_elem.get_text(strip=True)
            match = re.search(r"(\d+\.?\d*)", text)
            if match:
                return match.group(1)
        return None

    def _extract_image(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product image URL."""
        img = soup.find("img", class_="ProductDetailsMainCard__image")
        if img:
            return img.get("src") or img.get("data-src")
        return None
