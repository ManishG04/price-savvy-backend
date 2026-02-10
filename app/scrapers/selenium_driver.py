"""
Selenium WebDriver Manager for Price Savvy Backend
As per PRD: Use Selenium as a fallback for pages relying on client-side rendering
"""

import logging
import time
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Track if Selenium is available
SELENIUM_AVAILABLE = False

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException

    try:
        from webdriver_manager.chrome import ChromeDriverManager

        WEBDRIVER_MANAGER_AVAILABLE = True
    except ImportError:
        WEBDRIVER_MANAGER_AVAILABLE = False
        logger.warning("webdriver-manager not installed. Using system ChromeDriver.")

    SELENIUM_AVAILABLE = True
    logger.info("Selenium is available")
except ImportError:
    logger.warning(
        "Selenium not installed. Install with: uv pip install selenium webdriver-manager"
    )
    SELENIUM_AVAILABLE = False


class SeleniumDriver:
    """
    Manages Selenium WebDriver instances for scraping JavaScript-rendered pages.
    Uses headless Chrome by default for efficiency.
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 10,
        page_load_timeout: int = 30,
        disable_images: bool = True,
        disable_javascript: bool = False,
    ):
        """
        Initialize Selenium driver manager.

        Args:
            headless: Run browser in headless mode (default True)
            timeout: Wait timeout for elements in seconds
            page_load_timeout: Page load timeout in seconds
            disable_images: Disable image loading for faster scraping
            disable_javascript: Disable JS (only for static pages)
        """
        self.headless = headless
        self.timeout = timeout
        self.page_load_timeout = page_load_timeout
        self.disable_images = disable_images
        self.disable_javascript = disable_javascript
        self._driver: Optional[webdriver.Chrome] = None

    def _create_options(self) -> "ChromeOptions":
        """Create Chrome options with anti-detection settings."""
        options = ChromeOptions()

        if self.headless:
            options.add_argument("--headless=new")

        # Anti-detection settings
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # Performance settings
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")
        options.add_argument("--window-size=1920,1080")

        # User agent
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Disable images for faster loading
        if self.disable_images:
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.notifications": 2,
            }
            options.add_experimental_option("prefs", prefs)

        return options

    def get_driver(self) -> "webdriver.Chrome":
        """Get or create a WebDriver instance."""
        if not SELENIUM_AVAILABLE:
            raise RuntimeError(
                "Selenium is not installed. Install with: uv pip install selenium webdriver-manager"
            )

        if self._driver is None:
            options = self._create_options()

            try:
                if WEBDRIVER_MANAGER_AVAILABLE:
                    service = ChromeService(ChromeDriverManager().install())
                    self._driver = webdriver.Chrome(service=service, options=options)
                else:
                    self._driver = webdriver.Chrome(options=options)

                self._driver.set_page_load_timeout(self.page_load_timeout)

                # Execute anti-detection script
                self._driver.execute_cdp_cmd(
                    "Page.addScriptToEvaluateOnNewDocument",
                    {
                        "source": """
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });
                        """
                    },
                )

                logger.info("Selenium WebDriver initialized successfully")
            except WebDriverException as e:
                logger.error(f"Failed to initialize WebDriver: {e}")
                raise

        return self._driver

    def fetch_page(
        self, url: str, wait_selector: Optional[str] = None
    ) -> Optional[str]:
        """
        Fetch a page using Selenium and return the rendered HTML.

        Args:
            url: URL to fetch
            wait_selector: CSS selector to wait for before returning HTML

        Returns:
            Rendered HTML content or None on failure
        """
        driver = self.get_driver()

        try:
            logger.info(f"Selenium fetching: {url}")
            driver.get(url)

            # Wait for page to load
            time.sleep(2)  # Initial wait for JS to execute

            # Wait for specific element if selector provided
            if wait_selector:
                try:
                    WebDriverWait(driver, self.timeout).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
                    )
                except TimeoutException:
                    logger.warning(f"Timeout waiting for selector: {wait_selector}")

            # Scroll to load lazy content
            self._scroll_page(driver)

            html = driver.page_source
            logger.info(f"Selenium fetched {url} ({len(html)} bytes)")
            return html

        except TimeoutException:
            logger.error(f"Page load timeout for {url}")
            return None
        except WebDriverException as e:
            logger.error(f"Selenium error fetching {url}: {e}")
            return None

    def _scroll_page(
        self, driver: "webdriver.Chrome", scroll_pause: float = 0.5
    ) -> None:
        """Scroll the page to trigger lazy loading."""
        try:
            # Scroll down a few times
            for _ in range(3):
                driver.execute_script("window.scrollBy(0, 500);")
                time.sleep(scroll_pause)

            # Scroll back to top
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(scroll_pause)
        except Exception as e:
            logger.debug(f"Scroll error (non-critical): {e}")

    def close(self) -> None:
        """Close the WebDriver instance."""
        if self._driver:
            try:
                self._driver.quit()
                logger.info("Selenium WebDriver closed")
            except Exception as e:
                logger.warning(f"Error closing WebDriver: {e}")
            finally:
                self._driver = None

    def __enter__(self) -> "SeleniumDriver":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - ensure driver is closed."""
        self.close()


@contextmanager
def get_selenium_driver(**kwargs):
    """
    Context manager for getting a Selenium driver.
    Ensures proper cleanup after use.

    Usage:
        with get_selenium_driver() as driver:
            html = driver.fetch_page("https://example.com")
    """
    driver = SeleniumDriver(**kwargs)
    try:
        yield driver
    finally:
        driver.close()


def is_selenium_available() -> bool:
    """Check if Selenium is available for use."""
    return SELENIUM_AVAILABLE
