import os
import time
import json
import logging
import sys
import random
from typing import List, Dict, Any, Optional
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth
from src.analysis_manager import AnalysisManager, CardAnalysisResult
from src.search_terms import SEARCH_TERMS
from urllib3.exceptions import ProtocolError
from requests.exceptions import ConnectionError

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create console handler with UTF-8 encoding
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class BuyeeScraper:
    def __init__(self, output_dir: str = "scraped_results/final_gems", max_pages: int = 5, headless: bool = True):
        """Initialize the BuyeeScraper with configuration options."""
        self.base_url = "https://buyee.jp"
        self.output_dir = output_dir
        self.max_pages = max_pages
        self.headless = headless
        self.driver = None
        self.analysis_manager = AnalysisManager()
        os.makedirs(self.output_dir, exist_ok=True)
        self.options = webdriver.ChromeOptions()
        self.options.add_argument('--disable-gpu')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        self.wait = None
        self.initialize_driver()

    def initialize_driver(self):
        if self.driver:
            self.driver.quit()
        self.driver = webdriver.Chrome(options=self.options)
        self.wait = WebDriverWait(self.driver, 10)
        logger.info("WebDriver initialized successfully")

    def random_delay(self, min_seconds=2, max_seconds=5):
        """Add random delay between requests to avoid being blocked"""
        time.sleep(random.uniform(min_seconds, max_seconds))

    def retry_on_connection_error(func):
        """Decorator to retry functions on connection errors"""
        def wrapper(self, *args, **kwargs):
            max_retries = 3
            retry_delay = 5
            
            for attempt in range(max_retries):
                try:
                    return func(self, *args, **kwargs)
                except (ConnectionResetError, ProtocolError, ConnectionError, WebDriverException) as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Failed after {max_retries} attempts: {str(e)}")
                        raise
                    logger.warning(f"Connection error on attempt {attempt + 1}, retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    self.initialize_driver()  # Reinitialize driver on connection error
            return None
        return wrapper

    def _extract_item_data(self, item_element) -> Optional[Dict]:
        """Extract data from a single item card on the search page"""
        try:
            # Updated selectors based on current Buyee layout
            title_element = item_element.find_element(By.CSS_SELECTOR, 'a.itemCard__itemName')
            price_element = item_element.find_element(By.CSS_SELECTOR, '.g-price')
            image_element = item_element.find_element(By.CSS_SELECTOR, '.itemCard__itemImage img')
            
            item_data = {
                'title': title_element.text.strip(),
                'url': title_element.get_attribute('href'),
                'price': price_element.text.strip(),
                'image_url': image_element.get_attribute('src')
            }
            
            # Log successful extraction
            logger.info(f"Successfully extracted data for item: {item_data['title'][:30]}...")
            return item_data
            
        except Exception as e:
            logger.warning(f"Failed to extract item data: {str(e)}")
            return None

    def scrape_search_page(self, url: str) -> List[Dict[str, Any]]:
        """Scrape a search results page"""
        self.driver.get(url)
        self.random_delay()
        
        try:
            # Wait for the item cards to load
            self.wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.itemCard')))
            
            # Find all item cards
            items = self.driver.find_elements(By.CSS_SELECTOR, '.itemCard')
            results = []
            
            for item in items:
                item_data = self._extract_item_data(item)
                if item_data:  # Only process if we successfully extracted data
                    results.append(item_data)
            
            logger.info(f"Successfully extracted {len(results)} items from page")
            return results
            
        except TimeoutException:
            logger.warning("Timeout waiting for items to load")
            return []

    def scrape_item_detail_page(self, url: str) -> Dict[str, Any]:
        """Scrape an item's detail page"""
        self.driver.get(url)
        self.random_delay(3, 6)
        
        try:
            # Wait for main content
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.l-main')))
            
            # Updated selectors for detail page
            detail = {
                'url': url,
                'title': self.safe_get_text('.g-itemInfo__title'),
                'current_price': self.safe_get_text('.g-price'),
                'description': self.safe_get_text('.g-itemInfo__description'),
                'seller': self.safe_get_text('.g-itemInfo__seller'),
                'condition': self.safe_get_text('.g-itemInfo__status'),
                'images': [img.get_attribute('src') for img in self.driver.find_elements(By.CSS_SELECTOR, '.g-itemPhotos__item img')],
                'scraped_at': datetime.now().isoformat()
            }
            
            logger.info(f"Successfully scraped details for: {detail['title'][:30]}...")
            return detail
            
        except TimeoutException:
            logger.warning(f"Timeout waiting for detail page to load: {url}")
            return {'url': url, 'error': 'timeout'}

    def run(self, search_terms: List[str]):
        """Run the scraper"""
        for term in search_terms:
            logger.info(f"Searching for: {term}")
            page = 1
            
            while page <= self.max_pages:
                search_url = f"{self.base_url}/item/search/query/{term}?page={page}"
                logger.info(f"Navigating to {search_url}")
                
                try:
                    items = self.scrape_search_page(search_url)
                    if not items:
                        logger.info(f"No more items found on page {page}")
                        break
                    
                    for item in items:
                        try:
                            detail = self.scrape_item_detail_page(item['url'])
                            # Save the details (implement your saving logic here)
                            logger.info(f"Successfully scraped: {detail.get('title', 'Unknown Title')}")
                            self.random_delay()
                        except Exception as e:
                            logger.error(f"Error scraping item detail: {str(e)}")
                            continue
                    
                    page += 1
                    self.random_delay(4, 7)
                    
                except Exception as e:
                    logger.error(f"Error on page {page}: {str(e)}")
                    break
        
        self.driver.quit()

    def save_gems(self, gems: List[CardAnalysisResult]):
        """Save the found gems to a JSON file."""
        output_path = os.path.join(
            self.output_dir,
            f"gems_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump([g.__dict__ for g in gems], f, ensure_ascii=False, indent=2)
        logger.info(f"Results saved to {output_path}")

    def cleanup(self):
        """Clean up resources."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error during driver cleanup: {str(e)}")
            self.driver = None

if __name__ == "__main__":
    scraper = BuyeeScraper()
    try:
        scraper.run(SEARCH_TERMS)
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
        scraper.driver.quit()
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        scraper.driver.quit() 
