"""
Amazon Scraper - Scraper for Amazon products
As per PRD: BeautifulSoup4 for HTML parsing
"""

import logging
import time
import random
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class AmazonScraper(BaseScraper):
    """Scraper for Amazon product pages."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Amazon-specific headers to avoid bot detection
        self.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
            }
        )
        self.session.headers.update(self.headers)

    @property
    def name(self) -> str:
        return "Amazon"

    @property
    def supported_domains(self) -> list:
        return ["amazon.com", "amazon.in", "amazon.co.uk", "amazon.de"]

    @property
    def search_url_template(self) -> str:
        """Amazon search URL template."""
        return "https://www.amazon.in/s?k={query}"

    def fetch_page(self, url: str) -> str:
        """
        Fetch page with Amazon-specific retry logic.
        Overrides base class to add random delays.
        """
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Add a small random delay to avoid detection
                if attempt > 0:
                    delay = random.uniform(1, 3)
                    time.sleep(delay)

                response = self.session.get(url, timeout=self.timeout)

                # Check for bot detection page
                if response.status_code == 503:
                    logger.warning(f"Amazon returned 503 on attempt {attempt + 1}")
                    if attempt < max_attempts - 1:
                        continue

                response.raise_for_status()
                return response.text

            except Exception as e:
                if attempt == max_attempts - 1:
                    logger.error(f"Failed to fetch {url}: {e}")
                    raise
                logger.warning(f"Attempt {attempt + 1} failed, retrying...")

        raise Exception(f"Failed to fetch {url} after {max_attempts} attempts")

    def scrape(self, url: str) -> Dict:
        """
        Scrape product information from Amazon.

        Args:
            url: The Amazon product URL.

        Returns:
            Dictionary containing product information.
        """
        html = self.fetch_page(url)
        return self.parse_product(html, url)

    def parse_product(self, html: str, url: str) -> Dict:
        """
        Parse Amazon product page HTML.

        Args:
            html: The HTML content to parse.
            url: The original URL.

        Returns:
            Dictionary containing parsed product information.
        """
        soup = BeautifulSoup(html, "lxml")

        # Extract product title
        title_elem = soup.find("span", {"id": "productTitle"})
        title = title_elem.get_text(strip=True) if title_elem else None

        # Extract price
        price = self._extract_price(soup)

        # Extract original price (if on sale)
        original_price = self._extract_original_price(soup)

        # Extract rating
        rating_elem = soup.find("span", {"class": "a-icon-alt"})
        rating = rating_elem.get_text(strip=True) if rating_elem else None

        # Extract number of reviews
        reviews_elem = soup.find("span", {"id": "acrCustomerReviewText"})
        reviews = reviews_elem.get_text(strip=True) if reviews_elem else None

        # Extract availability
        availability_elem = soup.find("div", {"id": "availability"})
        availability = (
            availability_elem.get_text(strip=True) if availability_elem else None
        )

        # Extract image URL
        image_elem = soup.find("img", {"id": "landingImage"})
        image_url = image_elem.get("src") if image_elem else None

        # Extract description
        description = self._extract_description(soup)

        return {
            "source": self.name,
            "url": url,
            "title": title,
            "price": price,
            "original_price": original_price,
            "currency": self._detect_currency(url),
            "rating": rating,
            "reviews": reviews,
            "availability": availability,
            "image_url": image_url,
            "description": description,
        }

    def parse_search_results(self, html: str, max_results: int = 20) -> List[Dict]:
        """
        Parse Amazon search results page.

        Args:
            html: Search results page HTML
            max_results: Maximum results to return

        Returns:
            List of product dictionaries
        """
        soup = BeautifulSoup(html, "lxml")
        products = []

        # Find all product cards in search results
        product_cards = soup.find_all("div", {"data-component-type": "s-search-result"})

        for card in product_cards[:max_results]:
            try:
                product = self._parse_search_card(card)
                if product and product.get("title"):
                    products.append(product)
            except Exception as e:
                logger.warning(f"Failed to parse Amazon search card: {e}")
                continue

        logger.info(f"Parsed {len(products)} products from Amazon search")
        return products

    def _parse_search_card(self, card: BeautifulSoup) -> Optional[Dict]:
        """Parse a single product card from search results."""
        # Extract ASIN
        asin = card.get("data-asin", "")
        if not asin:
            return None

        # Extract title
        title_elem = card.find("span", {"class": "a-text-normal"})
        if not title_elem:
            title_elem = card.find("h2")
        title = title_elem.get_text(strip=True) if title_elem else None

        # Extract URL
        link_elem = card.find("a", {"class": "a-link-normal s-no-outline"})
        if not link_elem:
            link_elem = card.find("a", {"class": "a-link-normal"})
        url = f"https://www.amazon.in{link_elem.get('href', '')}" if link_elem else None

        # Extract price
        price_whole = card.find("span", {"class": "a-price-whole"})
        price = (
            price_whole.get_text(strip=True).replace(",", "") if price_whole else None
        )

        # Extract original price
        original_price_elem = card.find(
            "span", {"class": "a-price", "data-a-strike": "true"}
        )
        original_price = None
        if original_price_elem:
            offscreen = original_price_elem.find("span", {"class": "a-offscreen"})
            if offscreen:
                original_price = offscreen.get_text(strip=True)

        # Extract rating
        rating_elem = card.find("span", {"class": "a-icon-alt"})
        rating = rating_elem.get_text(strip=True) if rating_elem else None

        # Extract review count
        reviews_elem = card.find("span", {"class": "a-size-base", "dir": "auto"})
        reviews = reviews_elem.get_text(strip=True) if reviews_elem else None

        # Extract image
        img_elem = card.find("img", {"class": "s-image"})
        image_url = img_elem.get("src") if img_elem else None

        return {
            "source": self.name,
            "url": url,
            "title": title,
            "price": price,
            "original_price": original_price,
            "currency": "INR",
            "rating": rating,
            "reviews": reviews,
            "image_url": image_url,
            "asin": asin,
        }

    def _extract_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract the current price from the page."""
        # Try different price selectors
        price_selectors = [
            {"class": "a-price-whole"},
            {"id": "priceblock_ourprice"},
            {"id": "priceblock_dealprice"},
            {"class": "a-offscreen"},
        ]

        for selector in price_selectors:
            elem = soup.find("span", selector)
            if elem:
                return elem.get_text(strip=True)

        return None

    def _extract_original_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract the original price (before discount)."""
        elem = soup.find("span", {"class": "a-price", "data-a-strike": "true"})
        if elem:
            price_span = elem.find("span", {"class": "a-offscreen"})
            if price_span:
                return price_span.get_text(strip=True)
        return None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product description/bullet points."""
        feature_bullets = soup.find("div", {"id": "feature-bullets"})
        if feature_bullets:
            bullets = feature_bullets.find_all("li")
            if bullets:
                return " | ".join([b.get_text(strip=True) for b in bullets[:5]])
        return None

    def _detect_currency(self, url: str) -> str:
        """Detect currency based on URL domain."""
        if "amazon.in" in url:
            return "INR"
        elif "amazon.co.uk" in url:
            return "GBP"
        elif "amazon.de" in url:
            return "EUR"
        else:
            return "USD"
