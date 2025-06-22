from selenium import webdriver
<<<<<<< HEAD
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth
from bs4 import BeautifulSoup
import pandas as pd
import time
import json
import os
from datetime import datetime
import logging
from urllib.parse import urljoin, quote
from search_terms import SEARCH_TERMS
import csv
import traceback
from typing import Dict, List, Optional, Any, Tuple
from scraper_utils import RequestHandler, CardInfoExtractor, PriceAnalyzer, ConditionAnalyzer
from dotenv import load_dotenv
import re
import socket
import requests.exceptions
import urllib3
import argparse
import statistics
from image_analyzer import ImageAnalyzer
import glob
from card_analyzer import CardAnalyzer
from rank_analyzer import RankAnalyzer, CardCondition
from ai_analyzer import AIAnalyzer

# Set up logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    logger.error("OPENAI_API_KEY not found. Please check your .env file and its location.")
    import sys
    sys.exit(1)

class BuyeeScraper:
    def __init__(self, output_dir: str = "scraped_results", max_pages: int = 5, headless: bool = True):
        """
        Initialize the BuyeeScraper with configuration options.
        
        Args:
            output_dir (str): Directory to save scraped data
            max_pages (int): Maximum number of pages to scrape per search
            headless (bool): Run Chrome in headless mode
        """
        self.base_url = "https://buyee.jp"
        self.output_dir = output_dir
        self.max_pages = max_pages
        self.headless = headless
        self.driver = None
        self.request_handler = RequestHandler()
        self.card_analyzer = CardAnalyzer()
        self.rank_analyzer = RankAnalyzer()
        self.ai_analyzer = AIAnalyzer()
        
        # Search URL parameters
        self.search_params = {
            'sort': 'bids',  # Default to highest bid
            'order': 'd',    # Descending order
            'ranking': None, # Will be set to 'popular' if using popularity sort
            'translationType': '98',
            'page': '1'
        }
        
        os.makedirs(self.output_dir, exist_ok=True)
        self.setup_driver()
        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        
    def cleanup(self):
        """Clean up resources and close the driver."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error during driver cleanup: {str(e)}")
            self.driver = None
            
    def setup_driver(self):
        """Set up and configure Chrome WebDriver with stealth mode."""
        try:
            chrome_options = Options()
            
            # Basic options
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-popup-blocking')
            chrome_options.add_argument('--disable-notifications')
            chrome_options.add_argument('--disable-infobars')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            
            # SSL/TLS related options
            chrome_options.add_argument('--ignore-certificate-errors')
            chrome_options.add_argument('--allow-insecure-localhost')
            
            # Window size and user agent
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--start-maximized')
            
            # Stealth mode configuration
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            if self.headless:
                chrome_options.add_argument('--headless=new')
            
            # Set up service
            service = Service(ChromeDriverManager().install())
            
            # Initialize driver
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Apply stealth mode
            stealth(
                self.driver,
                languages=["ja-JP", "ja"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )
            
            logger.info("WebDriver initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup WebDriver: {str(e)}")
            raise

    def search_items(self, 
                    query: str,
                    sort_by: str = 'bids',  # 'bids' or 'popular'
                    max_pages: int = 1) -> List[Dict[str, Any]]:
        """
        Search for items on Buyee.
=======
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import json
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from .card_analyzer2 import CardAnalyzer, CardInfo
from .rank_analyzer import RankAnalyzer
from .text_analyzer import TextAnalyzer
from .image_analyzer import ImageAnalyzer
from .deal_analyzer import DealAnalyzer

logger = logging.getLogger(__name__)

class BuyeeScraper:
    def __init__(self, headless: bool = True):
        self.setup_logging()
        self.setup_driver(headless)
        self.card_analyzer = CardAnalyzer()
        self.rank_analyzer = RankAnalyzer()
        self.text_analyzer = TextAnalyzer()
        self.image_analyzer = ImageAnalyzer()
        self.deal_analyzer = DealAnalyzer()
        self.setup_directories()
        
    def setup_logging(self):
        """Set up logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('scraper.log'),
                logging.StreamHandler()
            ]
        )
>>>>>>> 8bb70d8ae833099f966a0f3d4917015c508300ca
        
    def setup_driver(self, headless: bool):
        """Set up the Selenium WebDriver with appropriate options."""
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
    def setup_directories(self):
        """Create necessary directories for saving results."""
        os.makedirs('scraped_results', exist_ok=True)
        os.makedirs('scraped_results/debug', exist_ok=True)
        os.makedirs('scraped_results/initial_leads', exist_ok=True)
        os.makedirs('scraped_results/final_gems', exist_ok=True)
        
    def search_items(self, search_terms: List[str], max_pages: int = 3):
        """Search for items using the provided search terms."""
        all_initial_leads = []
        
        for term in search_terms:
            logger.info(f"Processing search term: {term}")
            initial_leads = self.process_search_term(term, max_pages)
            all_initial_leads.extend(initial_leads)
            
<<<<<<< HEAD
            # Construct search URL
            search_url = f"https://buyee.jp/item/search/query/{quote(query)}"
            params = {k: v for k, v in self.search_params.items() if v is not None}
            search_url += '?' + '&'.join(f"{k}={v}" for k, v in params.items())
            
            logging.info(f"Searching page {page} with URL: {search_url}")
            
            try:
                self.driver.get(search_url)
                
                # Wait for item cards to load
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "li.itemCard"))
                    )
                except TimeoutException:
                    logging.warning(f"Timeout waiting for item cards on page {page}")
                    continue
                
                # Get all item cards
                item_cards = self.driver.find_elements(By.CSS_SELECTOR, "li.itemCard")
                logging.info(f"Found {len(item_cards)} items on page {page}")
                
                for card in item_cards:
                    try:
                        # Extract item data
                        item_data = self._extract_item_data(card)
                        if item_data:
                            # Try to get more details from the item page
                            try:
                                # Click the item link to open detail page
                                link_elem = card.find_element(By.CSS_SELECTOR, "div.itemCard__itemName a")
                                item_url = link_elem.get_attribute('href')
                                
                                # Open detail page in new tab
                                self.driver.execute_script("window.open(arguments[0]);", item_url)
                                self.driver.switch_to.window(self.driver.window_handles[-1])
                                
                                # Wait for detail page to load
                                try:
                                    WebDriverWait(self.driver, 10).until(
                                        EC.presence_of_element_located((By.CSS_SELECTOR, "section#auction_item_description"))
                                    )
                                    
                                    # Get page source and analyze
                                    detail_html = self.driver.page_source
                                    detail_data = self.scrape_item_detail_page(detail_html)
                                    
                                    if detail_data:
                                        # Merge detail data with item data
                                        item_data.update(detail_data)
                                        logging.info(f"Successfully scraped detail page for item: {item_data.get('title', '')}")
                                    else:
                                        logging.warning(f"Failed to scrape detail page for item: {item_data.get('title', '')}")
                                    
                                except TimeoutException:
                                    logging.warning(f"Timeout waiting for detail page to load: {item_url}")
                                except Exception as e:
                                    logging.error(f"Error scraping detail page: {str(e)}")
                                
                                # Close detail tab and switch back to search results
                                self.driver.close()
                                self.driver.switch_to.window(self.driver.window_handles[0])
                                
                            except Exception as e:
                                logging.error(f"Error processing detail page: {str(e)}")
                            
                            all_items.append(item_data)
                    except Exception as e:
                        logging.error(f"Error processing item card: {str(e)}")
                        continue
                
            except Exception as e:
                logging.error(f"Error searching page {page}: {str(e)}")
                break
=======
            # Save initial leads for this term
            if initial_leads:
                self.save_initial_leads(term, initial_leads)
                
        return all_initial_leads
        
    def process_search_term(self, term: str, max_pages: int) -> List[Dict[str, Any]]:
        """Process a single search term and return initial leads."""
        initial_leads = []
>>>>>>> 8bb70d8ae833099f966a0f3d4917015c508300ca
        
        try:
<<<<<<< HEAD
            # Extract title - the correct selector is "div.itemCard__itemName a"
            title_elem = card.find_element(By.CSS_SELECTOR, "div.itemCard__itemName a")
            title = title_elem.text.strip()
            
            # Extract price - the correct selector is "span.g-price" within "div.g-priceDetails"
            price_elem = card.find_element(By.CSS_SELECTOR, "div.g-priceDetails span.g-price")
            price_text = price_elem.text.strip()
            price_match = re.search(r'[\d,]+', price_text)
            if not price_match:
                return None
            price = int(price_match.group().replace(',', ''))
            
            # Extract URL - the correct selector is "div.itemCard__itemName a"
            link_elem = card.find_element(By.CSS_SELECTOR, "div.itemCard__itemName a")
            url = link_elem.get_attribute('href')
            
            # Extract image URL - the correct selector is "img.lazyLoadV2.g-thumbnail__image"
            img_elem = card.find_element(By.CSS_SELECTOR, "img.lazyLoadV2.g-thumbnail__image")
            image_url = img_elem.get_attribute('src')
            if not image_url or image_url.endswith('spacer.gif'):
                # Try data-src attribute for lazy-loaded images
                image_url = img_elem.get_attribute('data-src')
            
            # Extract bid count - the correct selector is "span.g-text" within the bid info item
            bid_count = None
            try:
                # Find the bid count from the info list
                info_items = card.find_elements(By.CSS_SELECTOR, "li.itemCard__infoItem")
                for item in info_items:
                    title_span = item.find_element(By.CSS_SELECTOR, "span.g-title")
                    if "Number of Bids" in title_span.text:
                        bid_text_elem = item.find_element(By.CSS_SELECTOR, "span.g-text")
                        bid_count = int(bid_text_elem.text.strip())
                        break
            except:
                pass
                
            # Extract time remaining
            time_remaining = None
            try:
                info_items = card.find_elements(By.CSS_SELECTOR, "li.itemCard__infoItem")
                for item in info_items:
                    title_span = item.find_element(By.CSS_SELECTOR, "span.g-title")
                    if "Time Remaining" in title_span.text:
                        time_elem = item.find_element(By.CSS_SELECTOR, "span.g-text")
                        time_remaining = time_elem.text.strip()
                        break
            except:
                pass
            
            # Extract seller
            seller = None
            try:
                info_items = card.find_elements(By.CSS_SELECTOR, "li.itemCard__infoItem")
                for item in info_items:
                    title_span = item.find_element(By.CSS_SELECTOR, "span.g-title")
                    if "Seller" in title_span.text:
                        seller_elem = item.find_element(By.CSS_SELECTOR, "span.g-text a")
                        seller = seller_elem.text.strip()
                        break
            except:
                pass
            
            return {
                'title': title,
                'price_text': price_text,
                'price': price,
                'url': url,
                'image_url': image_url,
                'bid_count': bid_count,
                'time_remaining': time_remaining,
                'seller': seller
            }
            
        except Exception as e:
            logging.error(f"Error extracting item data: {str(e)}")
            return None

    def scrape_item_detail_page(self, html_content: str) -> Optional[Dict]:
        """Scrape detailed information from an item's detail page."""
=======
            # Navigate to search page
            search_url = f"https://buyee.jp/item/search/query/{term}"
            self.driver.get(search_url)
            
            # Handle cookie popup if present
            self.handle_cookie_popup()
            
            # Process each page
            for page in range(1, max_pages + 1):
                logger.info(f"Processing page {page} for term: {term}")
                
                # Wait for items to load
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.itemCard"))
                    )
                except TimeoutException:
                    logger.warning(f"No items found on page {page} for term: {term}")
                    break
                    
                # Get item summaries
                item_summaries = self.get_item_summaries_from_search_page()
                
                # Analyze each item
                for item in item_summaries:
                    try:
                        # Get detailed information
                        detail_data = self.scrape_item_detail_page(item['url'])
                        if detail_data:
                            item.update(detail_data)
                        
                        # Perform AI analysis
                        card_info = self.card_analyzer.analyze_card(item)
                        
                        # If item looks promising, add to initial leads
                        if card_info.is_valuable and card_info.confidence_score >= 0.7:
                            item['card_info'] = card_info
                            item['analysis'] = {
                                'estimated_value': card_info.estimated_value,
                                'profit_potential': card_info.profit_potential,
                                'recommendation': card_info.recommendation
                            }
                            initial_leads.append(item)
                            logger.info(f"Found promising lead: {item['title']}")
                            logger.info(f"Estimated value: ¥{card_info.estimated_value['min']}-¥{card_info.estimated_value['max']}")
                            logger.info(f"Profit potential: ¥{card_info.profit_potential}")
                            logger.info(f"Recommendation: {card_info.recommendation}")
                            
                    except Exception as e:
                        logger.error(f"Error analyzing item: {str(e)}")
                        continue
                        
                # Try to go to next page
                if not self.go_to_next_page():
                    break
                    
        except Exception as e:
            logger.error(f"Error processing search term {term}: {str(e)}")
            
        return initial_leads
        
    def get_item_summaries_from_search_page(self) -> List[Dict[str, Any]]:
        """Extract item summaries from the current search page."""
        items = []
        
        try:
            # Find all item cards
            item_cards = self.driver.find_elements(By.CSS_SELECTOR, "div.itemCard")
            
            for card in item_cards:
                try:
                    # Extract basic information
                    title = card.find_element(By.CSS_SELECTOR, "div.itemCard__title").text
                    price_text = card.find_element(By.CSS_SELECTOR, "div.itemCard__price").text
                    price = self.extract_price(price_text)
                    
                    # Get item URL
                    item_url = card.find_element(By.CSS_SELECTOR, "a.itemCard__titleLink").get_attribute("href")
                    
                    # Get thumbnail image URL
                    try:
                        img = card.find_element(By.CSS_SELECTOR, "img.itemCard__image")
                        image_url = img.get_attribute("src")
                    except NoSuchElementException:
                        image_url = None
                        
                    items.append({
                        'title': title,
                        'price': price,
                        'price_text': price_text,
                        'url': item_url,
                        'image_url': image_url
                    })
                    
                except Exception as e:
                    logger.error(f"Error extracting item summary: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error getting item summaries: {str(e)}")
            
        return items
        
    def scrape_item_detail_page(self, item_url: str) -> Optional[Dict[str, Any]]:
        """Scrape detailed information from an item's page."""
>>>>>>> 8bb70d8ae833099f966a0f3d4917015c508300ca
        try:
            # Add delay to avoid rate limiting
            time.sleep(3)
            
            # Load the item page
            self.driver.get(item_url)
            
            # Wait for page to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.itemDetail"))
                )
            except TimeoutException:
                logger.warning(f"Timeout waiting for item page to load: {item_url}")
                return None
                
            # Check for error pages
            error_indicators = [
                "この商品は存在しません",
                "アクセスが集中しています",
                "メンテナンス中",
                "アクセスが制限されています",
                "CAPTCHA",
                "not found",
                "maintenance",
                "access denied"
            ]
            
            page_source = self.driver.page_source
            if any(indicator in page_source for indicator in error_indicators):
                logger.warning(f"Error page detected: {item_url}")
                self.save_debug_info(item_url, page_source, "error_page")
                return None
<<<<<<< HEAD
            
            # Try multiple selectors for description (Buyee specific)
            description = None
            desc_selectors = [
                'section#auction_item_description',
                'div.item-description',
                'div[class*="description"]',
                'div[class*="detail"]',
                'div[class*="content"]',
                'div[class*="text"]',
                'section[class*="description"]',
                'section[class*="detail"]',
                'section[class*="content"]',
                'section[class*="text"]',
                'div[class*="item-description"]',
                'div[class*="product-description"]',
                'div[class*="auction-description"]',
                'div[class*="item-detail"]',
                'div[class*="product-detail"]',
                'div[class*="auction-detail"]',
                'div[class*="item-content"]',
                'div[class*="product-content"]',
                'div[class*="auction-content"]'
            ]
            
            for selector in desc_selectors:
                desc_elem = soup.select_one(selector)
                if desc_elem:
                    description = desc_elem.get_text(strip=True)
                    logging.info(f"Found description using selector '{selector}' (first 100 chars): {description[:100]}...")
                    break
            
            if not description:
                logging.warning("Could not find description element")
                return None
            
            # Enhanced image handling for lazy-loaded images
            images = []
            image_selectors = [
                'img.item-image',
                'img[class*="item-image"]',
                'img[class*="product-image"]',
                'img[class*="main-image"]',
                'img[class*="thumbnail"]',
                'img[class*="photo"]',
                'img[class*="picture"]',
                'img[class*="auction"]',
                'img[class*="detail"]',
                'img[class*="content"]',
                'img[class*="item-photo"]',
                'img[class*="product-photo"]',
                'img[class*="auction-photo"]',
                'img[class*="item-picture"]',
                'img[class*="product-picture"]',
                'img[class*="auction-picture"]',
                'img[class*="item-thumbnail"]',
                'img[class*="product-thumbnail"]',
                'img[class*="auction-thumbnail"]'
            ]
            
            for selector in image_selectors:
                img_elems = soup.select(selector)
                for img in img_elems:
                    # Try data-src first (lazy-loaded image)
                    image_url = img.get('data-src')
                    if not image_url or 'spacer.gif' in image_url:
                        # Fall back to src if data-src is not available or is a placeholder
                        image_url = img.get('src')
                    
                    if image_url and not any(x in image_url.lower() for x in ['spacer.gif', 'blank.gif', 'placeholder']):
                        images.append(image_url)
                        logging.info(f"Found image using selector '{selector}': {image_url}")
            
            # Get the first image URL for analysis
            image_url = images[0] if images else None
            
            # Get eBay prices
            ebay_prices = self.ai_analyzer.get_ebay_prices(title, description)
            
            # Analyze the card
            analysis = self.ai_analyzer.analyze_card(
                title=title,
                description=description,
                price_yen=price,
                image_url=image_url,
                ebay_prices=ebay_prices
            )
            
            if not analysis:
                logging.warning("AI analysis failed")
                return None
            
            # Log detailed information about the scraped data
            logging.info(f"\nScraped detail page for: {title}")
            logging.info(f"Price: {price}")
            logging.info(f"Card Info: {analysis.card_name} ({analysis.set_code}-{analysis.card_number})")
            logging.info(f"Condition: {analysis.condition.value}")
            logging.info(f"Market Price: ${analysis.market_price:,.2f}")
            logging.info(f"Profit Margin: {analysis.profit_margin:.1%}")
            logging.info(f"Recommendation: {analysis.recommendation}")
            logging.info(f"Confidence: {analysis.confidence:.1%}")
            
            return {
                'title': title,
                'price': price,
                'description': description,
                'images': images,
                'analysis': {
                    'card_info': {
                        'card_name': analysis.card_name,
                        'set_code': analysis.set_code,
                        'card_number': analysis.card_number,
                        'rarity': analysis.rarity,
                        'edition': analysis.edition,
                        'region': analysis.region
                    },
                    'condition': {
                        'grade': analysis.condition.value,
                        'notes': analysis.condition_notes
                    },
                    'market': {
                        'ebay_price': analysis.market_price,
                        'profit_margin': analysis.profit_margin
                    },
                    'ai_analysis': {
                        'confidence': analysis.confidence,
                        'recommendation': analysis.recommendation,
                        'notes': analysis.notes
                    }
                }
            }
            
        except Exception as e:
            logging.error(f"Error scraping detail page: {str(e)}")
            return None

    def save_initial_promising_links(self, summaries: List[Dict[str, Any]], search_term: str) -> None:
        """Save initial promising links with hyperlinks and confidence scores."""
        if not summaries:
            logging.warning("No promising links to save")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"initial_leads_{search_term}_{timestamp}"
        
        # Create HTML report with hyperlinks
        html_content = """
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                tr:nth-child(even) { background-color: #f9f9f9; }
                tr:hover { background-color: #f5f5f5; }
                .confidence-high { color: green; }
                .confidence-medium { color: orange; }
                .confidence-low { color: red; }
                .thumbnail { max-width: 100px; max-height: 100px; cursor: pointer; }
                .title-jp { font-size: 1.1em; margin-bottom: 5px; }
                .title-en { color: #666; font-size: 0.9em; }
                .links-cell { white-space: nowrap; }
                .link-button {
                    display: inline-block;
                    padding: 5px 10px;
                    margin: 2px;
                    border-radius: 3px;
                    text-decoration: none;
                    color: white;
                    font-weight: bold;
                }
                .buyee-button { background-color: #4CAF50; }
                .yahoo-button { background-color: #2196F3; }
                .link-button:hover { opacity: 0.8; }
                .card-info { font-size: 0.9em; color: #666; }
                .condition-info { font-size: 0.9em; }
                .market-info { font-size: 0.9em; color: #2196F3; }
                .ai-analysis { font-size: 0.9em; color: #4CAF50; }
            </style>
            <script>
                function openImage(url) {
                    window.open(url, '_blank', 'width=800,height=600');
                }
            </script>
        </head>
        <body>
            <h1>Initial Promising Links - {search_term}</h1>
            <p>Generated on: {timestamp}</p>
            <table>
                <tr>
                    <th>Title</th>
                    <th>Card Info</th>
                    <th>Condition</th>
                    <th>Price</th>
                    <th>Market Analysis</th>
                    <th>AI Assessment</th>
                    <th>Confidence</th>
                    <th>Thumbnail</th>
                    <th>Links</th>
                </tr>
        """.format(search_term=search_term, timestamp=timestamp)

        for summary in summaries:
            title = summary.get('title', '')
            price = summary.get('price', 0)
            analysis = summary.get('analysis', {})
            confidence = analysis.get('confidence_score', 0)
            matched_keywords = analysis.get('matched_keywords', [])
            thumbnail_url = summary.get('thumbnail_url', '')
            buyee_url = summary.get('url', '')
            yahoo_url = summary.get('yahoo_url', '')
            
            # Extract card information
            card_info = analysis.get('card_info', {})
            set_code = card_info.get('set_code', '')
            card_number = card_info.get('card_number', '')
            rarity = card_info.get('rarity', '')
            edition = card_info.get('edition', '')
            region = card_info.get('region', '')
            
            # Extract condition information
            condition = analysis.get('condition', {})
            condition_grade = condition.get('grade', '')
            condition_notes = condition.get('notes', [])
            
            # Extract market analysis
            market = analysis.get('market', {})
            ebay_price = market.get('ebay_price', 0)
            profit_margin = market.get('profit_margin', 0)
            
            # Extract AI analysis
            ai_analysis = analysis.get('ai_analysis', {})
            ai_confidence = ai_analysis.get('confidence', 0)
            ai_recommendation = ai_analysis.get('recommendation', '')
            ai_notes = ai_analysis.get('notes', [])

            # Try to extract English title if available
            title_parts = title.split('|')
            title_jp = title_parts[0].strip()
            title_en = title_parts[1].strip() if len(title_parts) > 1 else ''

            # Determine confidence class
            confidence_class = 'confidence-low'
            if confidence >= 0.7:
                confidence_class = 'confidence-high'
            elif confidence >= 0.4:
                confidence_class = 'confidence-medium'

            html_content += f"""
                <tr>
                    <td>
                        <div class="title-jp">{title_jp}</div>
                        {f'<div class="title-en">{title_en}</div>' if title_en else ''}
                    </td>
                    <td class="card-info">
                        {f'Set: {set_code}-{card_number}<br>' if set_code and card_number else ''}
                        {f'Rarity: {rarity}<br>' if rarity else ''}
                        {f'Edition: {edition}<br>' if edition else ''}
                        {f'Region: {region}' if region else ''}
                    </td>
                    <td class="condition-info">
                        {f'Grade: {condition_grade}<br>' if condition_grade else ''}
                        {f'Notes: {", ".join(condition_notes)}' if condition_notes else ''}
                    </td>
                    <td>¥{price:,}</td>
                    <td class="market-info">
                        {f'eBay: ${ebay_price:,.2f}<br>' if ebay_price else ''}
                        {f'Margin: {profit_margin:.1%}' if profit_margin else ''}
                    </td>
                    <td class="ai-analysis">
                        {f'Confidence: {ai_confidence:.1%}<br>' if ai_confidence else ''}
                        {f'Recommendation: {ai_recommendation}<br>' if ai_recommendation else ''}
                        {f'Notes: {", ".join(ai_notes)}' if ai_notes else ''}
                    </td>
                    <td class="{confidence_class}">{confidence:.2f}</td>
                    <td>
                        <img src="{thumbnail_url}" class="thumbnail" alt="Thumbnail" 
                             onclick="openImage('{thumbnail_url}')" 
                             title="Click to view full size">
                    </td>
                    <td class="links-cell">
                        <a href="{buyee_url}" class="link-button buyee-button" target="_blank">Buyee</a>
                        {f'<a href="{yahoo_url}" class="link-button yahoo-button" target="_blank">Yahoo</a>' if yahoo_url else ''}
                    </td>
                </tr>
            """

        html_content += """
            </table>
        </body>
        </html>
        """

        # Save HTML report
        html_path = os.path.join(self.output_dir, f"{base_filename}.html")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logging.info(f"Saved HTML report with hyperlinks to: {html_path}")

        # Save CSV (for compatibility)
        csv_path = os.path.join(self.output_dir, f"{base_filename}.csv")
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Title (JP)', 'Title (EN)', 
                'Set Code', 'Card Number', 'Rarity', 'Edition', 'Region',
                'Condition Grade', 'Condition Notes',
                'Price (JPY)', 'eBay Price (USD)', 'Profit Margin',
                'AI Confidence', 'AI Recommendation', 'AI Notes',
                'Overall Confidence', 'Matched Keywords',
                'Buyee URL', 'Yahoo URL', 'Thumbnail URL'
            ])
            
            for summary in summaries:
                title = summary.get('title', '')
                title_parts = title.split('|')
                title_jp = title_parts[0].strip()
                title_en = title_parts[1].strip() if len(title_parts) > 1 else ''
                
                analysis = summary.get('analysis', {})
                card_info = analysis.get('card_info', {})
                condition = analysis.get('condition', {})
                market = analysis.get('market', {})
                ai_analysis = analysis.get('ai_analysis', {})
                
                writer.writerow([
                    title_jp, title_en,
                    card_info.get('set_code', ''), card_info.get('card_number', ''),
                    card_info.get('rarity', ''), card_info.get('edition', ''),
                    card_info.get('region', ''),
                    condition.get('grade', ''), ','.join(condition.get('notes', [])),
                    summary.get('price', 0), market.get('ebay_price', 0),
                    market.get('profit_margin', 0),
                    ai_analysis.get('confidence', 0), ai_analysis.get('recommendation', ''),
                    ','.join(ai_analysis.get('notes', [])),
                    analysis.get('confidence_score', 0),
                    ','.join(analysis.get('matched_keywords', [])),
                    summary.get('url', ''), summary.get('yahoo_url', ''),
                    summary.get('thumbnail_url', '')
                ])
        logging.info(f"Saved CSV report to: {csv_path}")

        # Save JSON (for programmatic access)
        json_path = os.path.join(self.output_dir, f"{base_filename}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(summaries, f, ensure_ascii=False, indent=2)
        logging.info(f"Saved JSON report to: {json_path}")

def main():
    """Main function to run the scraper."""
    parser = argparse.ArgumentParser(description='Buyee Card Scraper')
    parser.add_argument('--query', type=str, help='Search query')
    parser.add_argument('--sort', type=str, choices=['bids', 'popular'], default='bids',
                      help='Sort method (bids or popular)')
    parser.add_argument('--pages', type=int, default=1, help='Number of pages to scrape')
    parser.add_argument('--output', type=str, default='scraped_results',
                      help='Output directory')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    
    args = parser.parse_args()
    
    try:
        with BuyeeScraper(output_dir=args.output, max_pages=args.pages, headless=args.headless) as scraper:
            if args.query:
                results = scraper.search_items(args.query, sort_by=args.sort, max_pages=args.pages)
                if results:
                    scraper.save_initial_promising_links(results, args.query)
            else:
                # Use search terms from search_terms.py
                for term in SEARCH_TERMS:
                    results = scraper.search_items(term, sort_by=args.sort, max_pages=args.pages)
                    if results:
                        scraper.save_initial_promising_links(results, term)
                    
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main() 
=======
                
            # Extract detailed information
            item_data = {
                'url': item_url,
                'title': self.get_element_text("div.itemDetail__title"),
                'price': self.extract_price(self.get_element_text("div.itemDetail__price")),
                'description': self.get_element_text("div.itemDetail__description"),
                'condition': self.get_element_text("div.itemDetail__condition"),
                'seller': self.get_element_text("div.itemDetail__seller"),
                'image_urls': self.get_image_urls()
            }
            
            # Get Yahoo Auction URL if available
            try:
                yahoo_url = self.driver.find_element(By.CSS_SELECTOR, "a.itemDetail__yahooLink").get_attribute("href")
                item_data['yahoo_url'] = yahoo_url
            except NoSuchElementException:
                pass
                
            return item_data
            
        except Exception as e:
            logger.error(f"Error scraping item detail page: {str(e)}")
            self.save_debug_info(item_url, self.driver.page_source, "error")
            return None
            
    def get_element_text(self, selector: str) -> str:
        """Safely get text from an element."""
        try:
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            return element.text
        except NoSuchElementException:
            return ""
            
    def get_image_urls(self) -> List[str]:
        """Get all image URLs from the item page."""
        image_urls = []
        try:
            images = self.driver.find_elements(By.CSS_SELECTOR, "img.itemDetail__image")
            image_urls = [img.get_attribute("src") for img in images if img.get_attribute("src")]
        except Exception as e:
            logger.error(f"Error getting image URLs: {str(e)}")
        return image_urls
        
    def extract_price(self, price_text: str) -> float:
        """Extract price from text."""
        try:
            # Remove currency symbols and commas
            price_text = ''.join(c for c in price_text if c.isdigit() or c == '.')
            return float(price_text)
        except (ValueError, TypeError):
            return 0.0
            
    def handle_cookie_popup(self):
        """Handle cookie consent popup if present."""
        try:
            cookie_button = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.cookieConsent__button"))
            )
            cookie_button.click()
        except TimeoutException:
            pass  # No cookie popup found
            
    def go_to_next_page(self) -> bool:
        """Try to navigate to the next page of results."""
        try:
            next_button = self.driver.find_element(By.CSS_SELECTOR, "a.pagination__next")
            if "disabled" not in next_button.get_attribute("class"):
                next_button.click()
                time.sleep(2)  # Wait for page to load
                return True
        except NoSuchElementException:
            pass
        return False
        
    def save_debug_info(self, url: str, page_source: str, error_type: str):
        """Save debug information for failed scrapes."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"scraped_results/debug/{error_type}_{timestamp}.html"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"<!-- URL: {url} -->\n")
                f.write(f"<!-- Error Type: {error_type} -->\n")
                f.write(page_source)
        except Exception as e:
            logger.error(f"Error saving debug info: {str(e)}")
            
    def save_initial_leads(self, term: str, leads: List[Dict[str, Any]]):
        """Save initial leads to a JSON file with detailed analysis."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"scraped_results/initial_leads/{term}_{timestamp}.json"
        
        try:
            # Format leads for better readability
            formatted_leads = []
            for lead in leads:
                formatted_lead = {
                    'title': lead['title'],
                    'url': lead['url'],
                    'price': lead['price'],
                    'condition': lead.get('condition', 'Unknown'),
                    'analysis': {
                        'estimated_value': lead['analysis']['estimated_value'],
                        'profit_potential': lead['analysis']['profit_potential'],
                        'recommendation': lead['analysis']['recommendation']
                    },
                    'card_info': {
                        'rarity': lead['card_info'].rarity,
                        'set_code': lead['card_info'].set_code,
                        'card_number': lead['card_info'].card_number,
                        'edition': lead['card_info'].edition,
                        'region': lead['card_info'].region,
                        'confidence_score': lead['card_info'].confidence_score
                    }
                }
                formatted_leads.append(formatted_lead)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(formatted_leads, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Saved {len(formatted_leads)} leads to {filename}")
            
        except Exception as e:
            logger.error(f"Error saving initial leads: {str(e)}")
            
    def save_final_gems(self, term: str, gems: List[Dict[str, Any]]):
        """Save final gems to a JSON file with detailed analysis."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"scraped_results/final_gems/{term}_{timestamp}.json"
        
        try:
            # Format gems for better readability
            formatted_gems = []
            for gem in gems:
                formatted_gem = {
                    'title': gem['title'],
                    'url': gem['url'],
                    'price': gem['price'],
                    'condition': gem.get('condition', 'Unknown'),
                    'analysis': {
                        'estimated_value': gem['analysis']['estimated_value'],
                        'profit_potential': gem['analysis']['profit_potential'],
                        'recommendation': gem['analysis']['recommendation']
                    },
                    'card_info': {
                        'rarity': gem['card_info'].rarity,
                        'set_code': gem['card_info'].set_code,
                        'card_number': gem['card_info'].card_number,
                        'edition': gem['card_info'].edition,
                        'region': gem['card_info'].region,
                        'confidence_score': gem['card_info'].confidence_score
                    },
                    'images': gem.get('image_urls', [])
                }
                formatted_gems.append(formatted_gem)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(formatted_gems, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Saved {len(formatted_gems)} gems to {filename}")
            
        except Exception as e:
            logger.error(f"Error saving final gems: {str(e)}")
            
    def close(self):
        """Close the WebDriver."""
        if hasattr(self, 'driver'):
            self.driver.quit() 
>>>>>>> 8bb70d8ae833099f966a0f3d4917015c508300ca
