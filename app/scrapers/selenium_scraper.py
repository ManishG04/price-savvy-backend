"""
Selenium-enabled Base Scraper
Extends BaseScraper to support JavaScript-rendered pages
As per PRD: Use Selenium as a fallback for dynamic content
"""

import logging
from typing import Dict, List, Optional
from abc import abstractmethod

from app.scrapers.base_scraper import BaseScraper
from app.scrapers.selenium_driver import SeleniumDriver, is_selenium_available

logger = logging.getLogger(__name__)


class SeleniumScraper(BaseScraper):
    """
    Base scraper that uses Selenium for JavaScript-rendered pages.
    Falls back to requests if Selenium is not available.
    """

    def __init__(
        self,
        timeout: int = 5,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        use_selenium: bool = True,
        headless: bool = True,
    ):
        """
        Initialize Selenium-enabled scraper.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            backoff_factor: Exponential backoff factor
            use_selenium: Whether to use Selenium (True) or requests (False)
            headless: Run browser in headless mode
        """
        super().__init__(timeout, max_retries, backoff_factor)
        self.use_selenium = use_selenium and is_selenium_available()
        self.headless = headless
        self._selenium_driver: Optional[SeleniumDriver] = None

        if use_selenium and not is_selenium_available():
            logger.warning(
                f"{self.name}: Selenium requested but not available. "
                "Install with: uv pip install selenium webdriver-manager"
            )

    @property
    def wait_selector(self) -> Optional[str]:
        """
        CSS selector to wait for when using Selenium.
        Override in subclass for site-specific elements.
        """
        return None

    def _get_selenium_driver(self) -> SeleniumDriver:
        """Get or create Selenium driver instance."""
        if self._selenium_driver is None:
            self._selenium_driver = SeleniumDriver(
                headless=self.headless,
                timeout=self.timeout,
                page_load_timeout=30,
                disable_images=True,
            )
        return self._selenium_driver

    def fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch page using Selenium or requests based on configuration.

        Args:
            url: URL to fetch

        Returns:
            HTML content or None
        """
        if self.use_selenium:
            return self._fetch_with_selenium(url)
        else:
            return super().fetch_page(url)

    def _fetch_with_selenium(self, url: str) -> Optional[str]:
        """
        Fetch page using Selenium WebDriver.

        Args:
            url: URL to fetch

        Returns:
            Rendered HTML content or None
        """
        try:
            driver = self._get_selenium_driver()
            return driver.fetch_page(url, self.wait_selector)
        except Exception as e:
            logger.error(f"Selenium fetch failed for {url}: {e}")
            # Fall back to requests
            logger.info(f"Falling back to requests for {url}")
            return super().fetch_page(url)

    def search(self, query: str, max_results: int = 20) -> List[Dict]:
        """
        Search for products using Selenium if needed.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            List of product dictionaries
        """
        if not self.search_url_template:
            logger.warning(f"Search not implemented for {self.name}")
            return []

        try:
            from urllib.parse import quote_plus

            search_url = self.search_url_template.format(query=quote_plus(query))
            html = self.fetch_page(search_url)

            if html:
                products = self.parse_search_results(html, max_results)
                logger.info(
                    f"{self.name}: Found {len(products)} products for '{query}'"
                )
                return products
            return []
        except Exception as e:
            logger.error(f"Search failed for {self.name}: {e}")
            return []

    def close(self) -> None:
        """Close Selenium driver if active."""
        if self._selenium_driver:
            self._selenium_driver.close()
            self._selenium_driver = None

    def __del__(self):
        """Ensure driver is closed on destruction."""
        self.close()
