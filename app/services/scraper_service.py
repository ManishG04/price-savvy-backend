"""
Scraper Service - Core scraping logic
As per PRD: Concurrent scraping with ThreadPoolExecutor
"""

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
from app.scrapers.base_scraper import BaseScraper
from app.scrapers.amazon_scraper import AmazonScraper
from app.scrapers.flipkart_scraper import FlipkartScraper
from app.scrapers.myntra_scraper import MyntraScraper
from app.scrapers.ajio_scraper import AjioScraper
from app.scrapers.croma_scraper import CromaScraper
from app.scrapers.tatacliq_scraper import TataCliqScraper
from app.scrapers.snapdeal_scraper import SnapdealScraper
from app.scrapers.jiomart_scraper import JioMartScraper
from app.scrapers.meesho_scraper import MeeshoScraper

logger = logging.getLogger(__name__)


class ScraperService:
    """Service class for handling product scraping operations."""

    def __init__(self, max_workers: int = 5):
        """
        Initialize scraper service with available scrapers.

        Args:
            max_workers: Maximum concurrent workers (default 5 per PRD)
        """
        self.scrapers: Dict[str, BaseScraper] = {
            "amazon": AmazonScraper(),
            "flipkart": FlipkartScraper(),
            "myntra": MyntraScraper(),
            "ajio": AjioScraper(),
            "croma": CromaScraper(),
            "tatacliq": TataCliqScraper(),
            "snapdeal": SnapdealScraper(),
            "jiomart": JioMartScraper(),
            "meesho": MeeshoScraper(),
        }
        self.max_workers = max_workers

    def get_scraper_for_url(self, url: str) -> Optional[BaseScraper]:
        """
        Get the appropriate scraper for a given URL.

        Args:
            url: The product URL to scrape.

        Returns:
            The appropriate scraper instance or None if not supported.
        """
        url_lower = url.lower()

        for name, scraper in self.scrapers.items():
            if scraper.can_handle(url_lower):
                return scraper

        return None

    def scrape_product(self, url: str) -> Dict:
        """
        Scrape product information from a URL.

        Args:
            url: The product URL to scrape.

        Returns:
            Dictionary containing product information.

        Raises:
            ValueError: If the URL is not supported.
        """
        scraper = self.get_scraper_for_url(url)

        if not scraper:
            raise ValueError(f"URL not supported: {url}")

        return scraper.scrape(url)

    def scrape_batch(self, urls: List[str]) -> List[Dict]:
        """
        Scrape multiple products from a list of URLs concurrently.

        Args:
            urls: List of product URLs to scrape.

        Returns:
            List of dictionaries containing product information.
        """
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_url = {
                executor.submit(self._safe_scrape_product, url): url for url in urls
            }

            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    results.append({"url": url, "success": True, "data": result})
                except Exception as e:
                    logger.error(f"Failed to scrape {url}: {e}")
                    results.append({"url": url, "success": False, "error": str(e)})

        return results

    def _safe_scrape_product(self, url: str) -> Dict:
        """Wrapper for scrape_product with error handling."""
        return self.scrape_product(url)

    def search_products(self, query: str) -> List[Dict]:
        """
        Search for products across all available scrapers concurrently.
        As per PRD: Complete a two-site search within ~4 seconds

        Args:
            query: Search query string

        Returns:
            List of results from each scraper
        """
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_scraper = {
                executor.submit(self._safe_search, name, scraper, query): name
                for name, scraper in self.scrapers.items()
            }

            for future in as_completed(future_to_scraper):
                scraper_name = future_to_scraper[future]
                try:
                    result = future.result()
                    results.append(
                        {"source": scraper_name, "success": True, "products": result}
                    )
                    logger.info(
                        f"Search completed for {scraper_name}: {len(result)} products"
                    )
                except Exception as e:
                    logger.error(f"Search failed for {scraper_name}: {e}")
                    results.append(
                        {
                            "source": scraper_name,
                            "success": False,
                            "error": str(e),
                            "products": [],
                        }
                    )

        return results

    def _safe_search(self, name: str, scraper: BaseScraper, query: str) -> List[Dict]:
        """Wrapper for scraper search with error handling."""
        try:
            return scraper.search(query)
        except Exception as e:
            logger.error(f"Scraper {name} search error: {e}")
            raise

    def get_supported_sites(self) -> List[Dict]:
        """
        Get list of all supported sites.

        Returns:
            List of dictionaries with site information
        """
        return [
            {
                "name": scraper.name,
                "key": key,
                "domains": scraper.supported_domains,
            }
            for key, scraper in self.scrapers.items()
        ]

    def search_specific_sites(
        self, query: str, sites: List[str], max_results_per_site: int = 20
    ) -> List[Dict]:
        """
        Search specific sites only.

        Args:
            query: Search query string
            sites: List of site keys to search (e.g., ['amazon', 'flipkart'])
            max_results_per_site: Maximum results per site

        Returns:
            List of results from specified scrapers
        """
        results = []
        selected_scrapers = {
            name: scraper for name, scraper in self.scrapers.items() if name in sites
        }

        if not selected_scrapers:
            logger.warning(f"No valid scrapers found for sites: {sites}")
            return results

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_scraper = {
                executor.submit(self._safe_search, name, scraper, query): name
                for name, scraper in selected_scrapers.items()
            }

            for future in as_completed(future_to_scraper):
                scraper_name = future_to_scraper[future]
                try:
                    result = future.result()
                    results.append(
                        {
                            "source": scraper_name,
                            "success": True,
                            "products": result[:max_results_per_site],
                        }
                    )
                except Exception as e:
                    logger.error(f"Search failed for {scraper_name}: {e}")
                    results.append(
                        {
                            "source": scraper_name,
                            "success": False,
                            "error": str(e),
                            "products": [],
                        }
                    )

        return results

    def refresh_product(self, url: str) -> Optional[Dict]:
        """
        Refresh product data from source.

        Args:
            url: The product URL to refresh

        Returns:
            Updated product data or None if failed
        """
        try:
            return self.scrape_product(url)
        except Exception as e:
            logger.error(f"Failed to refresh product {url}: {e}")
            return None
