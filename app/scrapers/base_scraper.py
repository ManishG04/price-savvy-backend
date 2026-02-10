"""
Base Scraper - Abstract base class for all scrapers
As per PRD: BeautifulSoup for parsing, timeouts, retries with exponential backoff
"""
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all product scrapers."""
    
    def __init__(self, timeout: int = 5, max_retries: int = 3, backoff_factor: float = 2.0):
        """
        Initialize base scraper with common settings.
        
        Args:
            timeout: Request timeout in seconds (default 5s per PRD)
            max_retries: Maximum retry attempts (default 3)
            backoff_factor: Exponential backoff factor (default 2.0)
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        
        # Configure session with retry strategy
        self.session = requests.Session()
        
        # Setup retry strategy with exponential backoff
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        # Custom User-Agent as per PRD
        self.headers = {
            'User-Agent': 'PriceSavvy/1.0 (+https://github.com/pricesavvy; contact@pricesavvy.com)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
        }
        self.session.headers.update(self.headers)
        
        # Track last request time for rate limiting
        self._last_request_time: Dict[str, float] = {}
        self._request_interval = 1.0  # Minimum seconds between requests to same domain
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the scraper."""
        pass
    
    @property
    @abstractmethod
    def supported_domains(self) -> list:
        """Return list of supported domains."""
        pass
    
    @property
    def search_url_template(self) -> Optional[str]:
        """Return the search URL template for this site."""
        return None
    
    def can_handle(self, url: str) -> bool:
        """
        Check if this scraper can handle the given URL.
        
        Args:
            url: The URL to check.
            
        Returns:
            True if this scraper can handle the URL, False otherwise.
        """
        return any(domain in url.lower() for domain in self.supported_domains)
    
    def _respect_rate_limit(self, domain: str) -> None:
        """
        Ensure we respect the per-site request interval.
        As per PRD: Polite scraping with per-site intervals.
        """
        current_time = time.time()
        last_time = self._last_request_time.get(domain, 0)
        
        time_since_last = current_time - last_time
        if time_since_last < self._request_interval:
            sleep_time = self._request_interval - time_since_last
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s for {domain}")
            time.sleep(sleep_time)
        
        self._last_request_time[domain] = time.time()
    
    def fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch the HTML content of a page with retry logic.
        
        Args:
            url: The URL to fetch.
            
        Returns:
            HTML content as string or None if failed.
        """
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        
        self._respect_rate_limit(domain)
        
        try:
            logger.info(f"Fetching: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            logger.info(f"Successfully fetched {url} ({len(response.text)} bytes)")
            return response.text
        except requests.Timeout:
            logger.error(f"Timeout fetching {url}")
            raise Exception(f"Request timed out after {self.timeout}s")
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            raise Exception(f"Failed to fetch page: {str(e)}")
    
    @abstractmethod
    def scrape(self, url: str) -> Dict:
        """
        Scrape product information from the given URL.
        
        Args:
            url: The product URL to scrape.
            
        Returns:
            Dictionary containing product information.
        """
        pass
    
    @abstractmethod
    def parse_product(self, html: str, url: str) -> Dict:
        """
        Parse product information from HTML content.
        
        Args:
            html: The HTML content to parse.
            url: The original URL.
            
        Returns:
            Dictionary containing parsed product information.
        """
        pass
    
    def search(self, query: str, max_results: int = 20) -> List[Dict]:
        """
        Search for products on this site.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            
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
                return self.parse_search_results(html, max_results)
            return []
        except Exception as e:
            logger.error(f"Search failed for {self.name}: {e}")
            return []
    
    def parse_search_results(self, html: str, max_results: int = 20) -> List[Dict]:
        """
        Parse search results from HTML.
        Override in subclass to implement site-specific parsing.
        
        Args:
            html: Search results page HTML
            max_results: Maximum results to return
            
        Returns:
            List of product dictionaries
        """
        logger.warning(f"parse_search_results not implemented for {self.name}")
        return []
