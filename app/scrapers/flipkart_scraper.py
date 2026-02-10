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
        return ['flipkart.com']
    
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
        soup = BeautifulSoup(html, 'lxml')
        
        # Extract product title
        title_elem = soup.find('span', {'class': 'VU-ZEz'}) or soup.find('h1', {'class': 'yhB1nd'})
        title = title_elem.get_text(strip=True) if title_elem else None
        
        # Extract price
        price = self._extract_price(soup)
        
        # Extract original price (if on sale)
        original_price = self._extract_original_price(soup)
        
        # Extract rating
        rating_elem = soup.find('div', {'class': 'XQDdHH'})
        rating = rating_elem.get_text(strip=True) if rating_elem else None
        
        # Extract number of ratings and reviews
        reviews_elem = soup.find('span', {'class': 'Wphh3N'})
        reviews = reviews_elem.get_text(strip=True) if reviews_elem else None
        
        # Extract availability
        availability = self._extract_availability(soup)
        
        # Extract image URL
        image_elem = soup.find('img', {'class': 'DByuf4'}) or soup.find('img', {'class': '_396cs4'})
        image_url = image_elem.get('src') if image_elem else None
        
        # Extract description
        description = self._extract_description(soup)
        
        return {
            'source': self.name,
            'url': url,
            'title': title,
            'price': price,
            'original_price': original_price,
            'currency': 'INR',
            'rating': rating,
            'reviews': reviews,
            'availability': availability,
            'image_url': image_url,
            'description': description,
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
        soup = BeautifulSoup(html, 'lxml')
        products = []
        
        # Find all product cards - Flipkart uses different classes for different layouts
        # Grid layout
        product_cards = soup.find_all('div', {'class': '_1AtVbE'})
        
        if not product_cards:
            # List layout
            product_cards = soup.find_all('div', {'class': 'cPHDOP'})
        
        for card in product_cards[:max_results * 2]:  # Get more in case some fail
            try:
                product = self._parse_search_card(card)
                if product and product.get('title') and product.get('url'):
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
        # Extract title
        title_elem = card.find('a', {'class': 'WKTcLC'}) or card.find('div', {'class': '_4rR01T'})
        if not title_elem:
            title_elem = card.find('a', {'class': 's1Q9rs'})
        
        if not title_elem:
            return None
        
        title = title_elem.get_text(strip=True)
        
        # Extract URL
        link_elem = card.find('a', {'class': '_1fQZEK'}) or card.find('a', {'class': 's1Q9rs'})
        if not link_elem:
            link_elem = title_elem if title_elem.name == 'a' else None
        
        if not link_elem:
            return None
        
        href = link_elem.get('href', '')
        url = f"https://www.flipkart.com{href}" if href.startswith('/') else href
        
        # Extract price
        price_elem = card.find('div', {'class': '_30jeq3'}) or card.find('div', {'class': 'Nx9bqj'})
        price = price_elem.get_text(strip=True).replace('₹', '').replace(',', '') if price_elem else None
        
        # Extract original price
        original_price_elem = card.find('div', {'class': '_3I9_wc'}) or card.find('div', {'class': 'yRaY8j'})
        original_price = original_price_elem.get_text(strip=True) if original_price_elem else None
        
        # Extract rating
        rating_elem = card.find('div', {'class': '_3LWZlK'}) or card.find('div', {'class': 'XQDdHH'})
        rating = rating_elem.get_text(strip=True) if rating_elem else None
        
        # Extract reviews count
        reviews_elem = card.find('span', {'class': '_2_R_DZ'})
        reviews = reviews_elem.get_text(strip=True) if reviews_elem else None
        
        # Extract image
        img_elem = card.find('img', {'class': '_396cs4'}) or card.find('img', {'class': '_2r_T1I'})
        image_url = img_elem.get('src') if img_elem else None
        
        return {
            'source': self.name,
            'url': url,
            'title': title,
            'price': price,
            'original_price': original_price,
            'currency': 'INR',
            'rating': rating,
            'reviews': reviews,
            'image_url': image_url,
        }
    
    def _extract_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract the current price from the page."""
        # Try different price selectors
        price_selectors = [
            {'class': 'Nx9bqj CxhGGd'},
            {'class': '_30jeq3 _16Jk6d'},
            {'class': '_30jeq3'},
        ]
        
        for selector in price_selectors:
            elem = soup.find('div', selector)
            if elem:
                return elem.get_text(strip=True)
        
        return None
    
    def _extract_original_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract the original price (before discount)."""
        elem = soup.find('div', {'class': 'yRaY8j'}) or soup.find('div', {'class': '_3I9_wc'})
        if elem:
            return elem.get_text(strip=True)
        return None
    
    def _extract_availability(self, soup: BeautifulSoup) -> str:
        """Extract product availability."""
        # Check for out of stock
        out_of_stock = soup.find('div', {'class': '_16FRp0'})
        if out_of_stock and 'out of stock' in out_of_stock.get_text().lower():
            return 'Out of Stock'
        
        # Check for buy button
        buy_button = soup.find('button', {'class': '_2KpZ6l'})
        if buy_button:
            return 'In Stock'
        
        return 'Unknown'
    
    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product description/highlights."""
        highlights = soup.find('div', {'class': '_2418kt'})
        if highlights:
            items = highlights.find_all('li', {'class': '_21Ahn-'})
            if items:
                return ' | '.join([item.get_text(strip=True) for item in items[:5]])
        return None
