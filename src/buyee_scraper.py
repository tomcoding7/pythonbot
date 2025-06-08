from selenium import webdriver
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
            
            # Save initial leads for this term
            if initial_leads:
                self.save_initial_leads(term, initial_leads)
                
        return all_initial_leads
        
    def process_search_term(self, term: str, max_pages: int) -> List[Dict[str, Any]]:
        """Process a single search term and return initial leads."""
        initial_leads = []
        
        try:
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