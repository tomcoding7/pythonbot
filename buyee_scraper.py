from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth
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
from src.card_analyzer2 import CardAnalyzer
from rank_analyzer import RankAnalyzer, CardCondition

# Set up logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more detailed logging
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
            
            # Stealth mode configuration
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
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

    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize a string to be used as a valid filename on Windows.
        
        Args:
            filename (str): Original filename to sanitize
            
        Returns:
            str: Sanitized filename
        """
        try:
            # Replace invalid characters with underscores
            invalid_chars = r'[<>:"/\\|?*]'
            sanitized = re.sub(invalid_chars, '_', filename)
            
            # Remove any leading/trailing spaces and dots
            sanitized = sanitized.strip('. ')
            
            # Ensure the filename isn't too long (Windows has a 255 character limit)
            if len(sanitized) > 240:  # Leave room for extension
                sanitized = sanitized[:240]
                
            return sanitized
            
        except Exception as e:
            logger.error(f"Error sanitizing filename: {str(e)}")
            return f"invalid_filename_{hash(filename)}"

    def save_debug_info(self, identifier: str, error_type: str, page_source: str) -> None:
        """Save debug information about a failed request."""
        try:
            # Sanitize the identifier for use in filenames
            safe_identifier = self.sanitize_filename(identifier)
            
            debug_dir = os.path.join(self.output_dir, "debug")
            os.makedirs(debug_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_identifier}_{error_type}_{timestamp}.html"
            filepath = os.path.join(debug_dir, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(page_source)
            logger.info(f"Saved debug info to {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving debug info: {str(e)}")

    def setup_driver(self):
        """Set up and return a configured Chrome WebDriver instance."""
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
            chrome_options.add_argument('--ignore-certificate-errors')  # For diagnostic purposes only
            chrome_options.add_argument('--allow-insecure-localhost')
            chrome_options.add_argument('--reduce-security-for-testing')  # For diagnostic purposes only
            
            # Window size and user agent
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--start-maximized')
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Additional anti-detection measures
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Create the driver
            service = Service()
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Apply stealth settings
            stealth(self.driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )
            
            # Set page load timeout
            self.driver.set_page_load_timeout(30)
            
            # Set window size explicitly after creation
            self.driver.set_window_size(1920, 1080)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup WebDriver: {str(e)}")
            return False

    def test_connection(self):
        """Test basic connectivity to Buyee and perform network diagnostics."""
        try:
            # First, test basic HTTPS connectivity with a simple site
            logger.info("Testing basic HTTPS connectivity with example.com")
            try:
                self.driver.get("https://example.com")
                logger.info("Successfully connected to example.com")
            except Exception as e:
                logger.error(f"Failed to connect to example.com: {str(e)}")
                return False
            
            # Then test Google (another reliable HTTPS site)
            logger.info("Testing HTTPS connectivity with google.com")
            try:
                self.driver.get("https://www.google.com")
                logger.info("Successfully connected to google.com")
            except Exception as e:
                logger.error(f"Failed to connect to google.com: {str(e)}")
                return False
            
            # Finally, test Buyee
            logger.info(f"Testing connection to {self.base_url}")
            try:
                self.driver.get(self.base_url)
                time.sleep(2)  # Short wait to let any initial scripts run
                
                # Check for common issues
                if "SSL" in self.driver.title or "Error" in self.driver.title:
                    logger.error(f"SSL or error page detected: {self.driver.title}")
                    self.save_debug_info("connection_test", "ssl_error", self.driver.page_source)
                    return False
                
                # Check for CAPTCHA
                if "captcha" in self.driver.page_source.lower():
                    logger.error("CAPTCHA detected")
                    self.save_debug_info("connection_test", "captcha", self.driver.page_source)
                    return False
                
                # Check for successful page load
                if not self.driver.title:
                    logger.error("Page title is empty, possible connection issue")
                    self.save_debug_info("connection_test", "empty_title", self.driver.page_source)
                    return False
                
                logger.info(f"Successfully connected to {self.base_url}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to connect to Buyee: {str(e)}")
                self.save_debug_info("connection_test", "connection_failed", self.driver.page_source)
                return False
                
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False

    def clean_price(self, price_text: str) -> float:
        """Clean and convert price text to float."""
        try:
            # Remove currency symbols, commas, and convert to float
            cleaned = re.sub(r'[^\d.]', '', price_text)
            return float(cleaned)
        except (ValueError, TypeError):
            logger.warning(f"Could not parse price: {price_text}")
            return 0.0

    def analyze_page_content(self) -> Dict[str, Any]:
        """
        Analyze the current page content and return detailed information about its state.
        """
        try:
            page_source = self.driver.page_source
            title = self.driver.title
            current_url = self.driver.current_url
            
            # Save detailed page analysis
            debug_dir = os.path.join(self.output_dir, "debug")
            os.makedirs(debug_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            analysis = {
                "timestamp": timestamp,
                "title": title,
                "url": current_url,
                "page_source_length": len(page_source),
                "has_item_cards": False,
                "has_item_container": False,
                "has_maintenance": False,
                "has_captcha": False,
                "has_error": False,
                "has_no_results": False,
                "maintenance_context": None,
                "error_context": None,
                "key_elements_found": [],
                "page_state": "unknown",
                "content_analysis": {
                    "has_header": False,
                    "has_footer": False,
                    "has_search_box": False,
                    "has_category_menu": False,
                    "has_translate_widget": False,
                    "has_pagination": False,
                    "has_breadcrumbs": False,
                    "has_cookie_popup": False
                },
                "item_analysis": {
                    "container_found": False,
                    "container_selector": "ul.auctionSearchResult.list_layout",
                    "items_found": 0,
                    "item_selector": "li.itemCard",
                    "first_item_html": None,
                    "container_candidates": []
                },
                "javascript_errors": [],
                "network_requests": []
            }
            
            # Save full page source
            source_path = os.path.join(debug_dir, f"full_page_source_{timestamp}.html")
            with open(source_path, "w", encoding="utf-8") as f:
                f.write(page_source)
            logger.info(f"Saved full page source to {source_path}")
            
            # Save screenshot
            screenshot_path = os.path.join(debug_dir, f"full_screenshot_{timestamp}.png")
            self.driver.save_screenshot(screenshot_path)
            logger.info(f"Saved full screenshot to {screenshot_path}")
            
            # Check for JavaScript errors
            try:
                js_errors = self.driver.execute_script("""
                    return window.performance.getEntries()
                        .filter(entry => entry.initiatorType === 'script' && entry.duration > 1000)
                        .map(entry => ({
                            name: entry.name,
                            duration: entry.duration,
                            startTime: entry.startTime
                        }));
                """)
                analysis["javascript_errors"] = js_errors
            except Exception as e:
                logger.warning(f"Could not check JavaScript errors: {str(e)}")
            
            # Check for essential page elements with explicit waits
            try:
                # First, wait for the page to be in a stable state
                WebDriverWait(self.driver, 10).until(
                    lambda driver: driver.execute_script('return document.readyState') == 'complete'
                )
                
                # Check for cookie popup
                try:
                    cookie_popup = self.driver.find_element(By.CSS_SELECTOR, "div.cookiePolicyPopup.expanded")
                    analysis["content_analysis"]["has_cookie_popup"] = True
                    analysis["key_elements_found"].append("Cookie popup present")
                except NoSuchElementException:
                    analysis["content_analysis"]["has_cookie_popup"] = False
                
                # Try to find the item container with the correct selector
                try:
                    logger.info(f"Waiting for item container: {analysis['item_analysis']['container_selector']}")
                    item_container = WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, analysis['item_analysis']['item_selector']))
                    )
                    analysis["has_item_container"] = True
                    analysis["item_analysis"]["container_found"] = True
                    analysis["key_elements_found"].append("Found item container")
                    
                    # If we have the container, wait for at least one item card
                    logger.info(f"Waiting for item cards: {analysis['item_analysis']['item_selector']}")
                    try:
                        # Wait for at least one item to be present
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, analysis['item_analysis']['item_selector']))
                        )
                        
                        # Now get all items
                        item_cards = self.driver.find_elements(By.CSS_SELECTOR, analysis['item_analysis']['item_selector'])
                        analysis["has_item_cards"] = len(item_cards) > 0
                        analysis["item_analysis"]["items_found"] = len(item_cards)
                        
                        if item_cards:
                            analysis["key_elements_found"].append(f"Found {len(item_cards)} item cards")
                            # Save the HTML of the first item for debugging
                            analysis["item_analysis"]["first_item_html"] = item_cards[0].get_attribute('outerHTML')
                            logger.debug(f"First item HTML: {analysis['item_analysis']['first_item_html']}")
                            
                    except TimeoutException:
                        logger.warning("Item container found but no items appeared within timeout")
                        analysis["item_analysis"]["items_found"] = 0
                        
                except TimeoutException:
                    logger.warning("Item container not found within timeout")
                    analysis["has_item_container"] = False
                
                # Check for other essential page elements
                header = self.driver.find_elements(By.CSS_SELECTOR, "header")
                analysis["content_analysis"]["has_header"] = len(header) > 0
                
                footer = self.driver.find_elements(By.CSS_SELECTOR, "footer")
                analysis["content_analysis"]["has_footer"] = len(footer) > 0
                
                search_box = self.driver.find_elements(By.CSS_SELECTOR, "input[type='search']")
                analysis["content_analysis"]["has_search_box"] = len(search_box) > 0
                
                category_menu = self.driver.find_elements(By.CSS_SELECTOR, "nav.category-menu")
                analysis["content_analysis"]["has_category_menu"] = len(category_menu) > 0
                
                translate_widget = self.driver.find_elements(By.CSS_SELECTOR, "#google_translate_element")
                analysis["content_analysis"]["has_translate_widget"] = len(translate_widget) > 0
                
                # Check for pagination
                pagination = self.driver.find_elements(By.CSS_SELECTOR, "div.pagination")
                analysis["content_analysis"]["has_pagination"] = len(pagination) > 0
                
                # Check for breadcrumbs
                breadcrumbs = self.driver.find_elements(By.CSS_SELECTOR, "div.breadcrumbs")
                analysis["content_analysis"]["has_breadcrumbs"] = len(breadcrumbs) > 0
                
            except Exception as e:
                logger.debug(f"Error checking page elements: {str(e)}")
            
            # Check for actual maintenance messages (more specific indicators)
            maintenance_indicators = [
                # Japanese maintenance messages
                'ただいまメンテナンス作業を実施しております',
                'システムメンテナンス中',
                '現在メンテナンス中です',
                'メンテナンス作業のため',
                'メンテナンスのため',
                'メンテナンスにより',
                'メンテナンスの影響で',
                'メンテナンスの関係で',
                'メンテナンスの都合上',
                'メンテナンスの都合により',
                'メンテナンスの都合で',
                # English maintenance messages
                'site is currently under maintenance',
                'undergoing maintenance',
                'system maintenance',
                'maintenance in progress',
                'temporarily unavailable due to maintenance'
            ]
            
            # Check for maintenance with context
            for indicator in maintenance_indicators:
                if indicator in page_source.lower():
                    # Get more context around the maintenance message
                    start = max(0, page_source.lower().find(indicator) - 200)
                    end = min(len(page_source), page_source.lower().find(indicator) + len(indicator) + 200)
                    context = page_source[start:end]
                    
                    # Only consider it maintenance if it's a prominent message
                    if any(phrase in context.lower() for phrase in ['maintenance', 'メンテナンス']):
                        analysis["has_maintenance"] = True
                        analysis["maintenance_context"] = context
                        analysis["page_state"] = "maintenance"
                        break
            
            # Check for CAPTCHA
            captcha_indicators = ['captcha', 'recaptcha', 'robot', 'verify', 'reCAPTCHA']
            if any(indicator in page_source.lower() for indicator in captcha_indicators):
                analysis["has_captcha"] = True
                analysis["key_elements_found"].append("CAPTCHA detected")
                analysis["page_state"] = "captcha"
            
            # Check for no results
            no_results_indicators = [
                'no results', 'no items found', '検索結果がありません',
                '検索結果はありませんでした', '該当する商品が見つかりませんでした',
                '商品が見つかりませんでした', '検索条件に一致する商品はありませんでした'
            ]
            if any(indicator in page_source.lower() for indicator in no_results_indicators):
                analysis["has_no_results"] = True
                analysis["key_elements_found"].append("No results message found")
                analysis["page_state"] = "no_results"
            
            # Check for error messages
            error_indicators = [
                'error', '申し訳ございません', 'エラー', '問題が発生しました',
                'system error', 'error occurred', '申し訳ありませんが',
                'アクセスできません', 'アクセス制限', 'too many requests',
                'rate limit', 'not available in your region', '地域制限'
            ]
            for indicator in error_indicators:
                if indicator in page_source.lower():
                    analysis["has_error"] = True
                    start = max(0, page_source.lower().find(indicator) - 200)
                    end = min(len(page_source), page_source.lower().find(indicator) + len(indicator) + 200)
                    analysis["error_context"] = page_source[start:end]
                    analysis["page_state"] = "error"
                    break
            
            # Determine page state based on content analysis
            if analysis["has_item_container"]:
                if analysis["has_item_cards"]:
                    analysis["page_state"] = "ready"
                elif analysis["has_no_results"]:
                    analysis["page_state"] = "no_results"
                else:
                    analysis["page_state"] = "error"
            elif not any([
                analysis["content_analysis"]["has_header"],
                analysis["content_analysis"]["has_footer"],
                analysis["content_analysis"]["has_search_box"],
                analysis["content_analysis"]["has_category_menu"]
            ]):
                # If we don't have the item container AND we're missing other essential elements,
                # the page is likely not loaded properly
                analysis["page_state"] = "error"
                analysis["has_error"] = True
                analysis["error_context"] = "Page appears to be incompletely loaded - missing essential elements"
            
            # Save analysis results
            analysis_path = os.path.join(debug_dir, f"page_analysis_{timestamp}.json")
            with open(analysis_path, "w", encoding="utf-8") as f:
                json.dump(analysis, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved page analysis to {analysis_path}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing page content: {str(e)}")
            return {
                "error": str(e),
                "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "page_state": "error"
            }

    def check_page_state(self):
        """Check the current page state and return (state, is_error) tuple."""
        try:
            # Save current page state for debugging
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            page_source = self.driver.page_source
            page_title = self.driver.title
            current_url = self.driver.current_url
            
            # Save full page source and screenshot
            debug_dir = os.path.join(self.output_dir, 'debug')
            os.makedirs(debug_dir, exist_ok=True)
            
            with open(os.path.join(debug_dir, f'full_page_source_{timestamp}.html'), 'w', encoding='utf-8') as f:
                f.write(page_source)
            
            self.driver.save_screenshot(os.path.join(debug_dir, f'full_screenshot_{timestamp}.png'))
            
            # Perform detailed page analysis
            analysis = {
                'timestamp': timestamp,
                'url': current_url,
                'title': page_title,
                'page_state': 'unknown',
                'has_item_container': False,
                'has_item_cards': False,
                'content_analysis': {
                    'has_header': False,
                    'has_footer': False,
                    'has_search_box': False,
                    'has_category_menu': False,
                    'has_translate_widget': False,
                    'has_pagination': False,
                    'has_breadcrumbs': False,
                    'has_cookie_popup': False,
                    'has_no_results_message': False,
                    'no_results_message': None,
                    'no_results_indicators': []
                },
                'error_context': None,
                'javascript_errors': [],
                'container_candidates': []
            }
            
            # Check for essential elements
            try:
                # First, wait for the page to be in a stable state
                WebDriverWait(self.driver, 10).until(
                    lambda driver: driver.execute_script('return document.readyState') == 'complete'
                )
                
                # Check for cookie popup
                try:
                    cookie_popup = self.driver.find_element(By.CSS_SELECTOR, "div.cookiePolicyPopup.expanded")
                    analysis['content_analysis']['has_cookie_popup'] = True
                except NoSuchElementException:
                    analysis['content_analysis']['has_cookie_popup'] = False
                
                # Check for no results message first - using exact selectors from observed HTML
                no_results_selectors = [
                    "div.bidNotfound_middle",  # From the Pokemon Card Starter example
                    "div.noResults",
                    "div.searchResult__noResults",
                    "div.searchResult__empty",
                    "div.searchResult__message",
                    "div.messageBox--noResults",
                    "div.searchResult__noItems",
                    "div.searchResult__emptyMessage",
                    "div.searchResult__noData",
                    "div.searchResult__noDataMessage"
                ]
                
                # Also check for common no results text in Japanese and English
                no_results_texts = [
                    # English messages
                    "No Results Found",
                    "Could not find any results for",
                    # Japanese messages
                    "該当する商品が見つかりませんでした",
                    "検索結果はありませんでした",
                    "商品が見つかりませんでした",
                    "検索条件に一致する商品はありませんでした",
                    "該当する商品はありませんでした",
                    "検索結果がありません",
                    "商品が見つかりません",
                    "該当する商品はありません",
                    "検索条件に一致する商品はありません"
                ]
                
                # Check for no results message using selectors
                for selector in no_results_selectors:
                    try:
                        no_results_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        message = no_results_element.text.strip()
                        analysis['content_analysis']['has_no_results_message'] = True
                        analysis['content_analysis']['no_results_message'] = message
                        analysis['content_analysis']['no_results_indicators'].append(f"Found no results element: {selector}")
                        logger.info(f"Found no results message: {message}")
                        return 'no_results', False
                    except NoSuchElementException:
                        continue
                
                # Check for no results text in page source
                for text in no_results_texts:
                    if text in page_source:
                        analysis['content_analysis']['has_no_results_message'] = True
                        analysis['content_analysis']['no_results_message'] = text
                        analysis['content_analysis']['no_results_indicators'].append(f"Found no results text: {text}")
                        logger.info(f"Found no results text in page source: {text}")
                        return 'no_results', False
                
                # Try to find the item container with the correct selector
                try:
                    logger.info("Waiting for item container: ul.auctionSearchResult.list_layout")
                    item_container = WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "ul.auctionSearchResult.list_layout"))
                    )
                    analysis['has_item_container'] = True
                    
                    # Check for item cards
                    item_cards = self.driver.find_elements(By.CSS_SELECTOR, "li.itemCard")
                    analysis['has_item_cards'] = len(item_cards) > 0
                    
                    if analysis['has_item_cards']:
                        analysis['page_state'] = 'ready'
                        return 'ready', False
                    else:
                        # If we have the container but no items, check for no results message again
                        # (some pages might show the container even with no results)
                        for selector in no_results_selectors:
                            try:
                                no_results_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                                message = no_results_element.text.strip()
                                analysis['content_analysis']['has_no_results_message'] = True
                                analysis['content_analysis']['no_results_message'] = message
                                analysis['content_analysis']['no_results_indicators'].append(f"Found no results element in empty container: {selector}")
                                logger.info(f"Found no results message in empty container: {message}")
                                return 'no_results', False
                            except NoSuchElementException:
                                continue
                        
                        # If we still don't have a no results message, this might be a loading issue
                        analysis['page_state'] = 'error'
                        analysis['error_context'] = "Container found but no items and no no-results message"
                        return 'error', True
                        
                except TimeoutException:
                    logger.warning("Item container not found within timeout")
                    analysis['error_context'] = "Item container not found"
                    
                    # Check if we have other essential elements to determine if page loaded properly
                    try:
                        analysis['content_analysis']['has_header'] = len(self.driver.find_elements(By.CSS_SELECTOR, "header")) > 0
                        analysis['content_analysis']['has_footer'] = len(self.driver.find_elements(By.CSS_SELECTOR, "footer")) > 0
                        analysis['content_analysis']['has_search_box'] = len(self.driver.find_elements(By.CSS_SELECTOR, "input[type='search']")) > 0
                        analysis['content_analysis']['has_category_menu'] = len(self.driver.find_elements(By.CSS_SELECTOR, "nav.categoryMenu")) > 0
                        
                        # If we have essential elements but no container, this might be a no results page
                        if (analysis['content_analysis']['has_header'] and 
                            analysis['content_analysis']['has_footer'] and 
                            analysis['content_analysis']['has_search_box']):
                            
                            # Check for no results message one more time
                            for selector in no_results_selectors:
                                try:
                                    no_results_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                                    message = no_results_element.text.strip()
                                    analysis['content_analysis']['has_no_results_message'] = True
                                    analysis['content_analysis']['no_results_message'] = message
                                    analysis['content_analysis']['no_results_indicators'].append(f"Found no results element after container timeout: {selector}")
                                    logger.info(f"Found no results message after container timeout: {message}")
                                    return 'no_results', False
                                except NoSuchElementException:
                                    continue
                            
                            # Check for no results text in page source one more time
                            for text in no_results_texts:
                                if text in page_source:
                                    analysis['content_analysis']['has_no_results_message'] = True
                                    analysis['content_analysis']['no_results_message'] = text
                                    analysis['content_analysis']['no_results_indicators'].append(f"Found no results text in page source after container timeout: {text}")
                                    logger.info(f"Found no results text in page source after container timeout: {text}")
                                    return 'no_results', False
                            
                            # If we have essential elements but no container and no no-results message,
                            # this might be a loading issue
                            analysis['page_state'] = 'error'
                            analysis['error_context'] = "Essential elements present but no container found"
                            return 'error', True
                        else:
                            # Missing essential elements suggests a more serious loading issue
                            analysis['page_state'] = 'error'
                            analysis['error_context'] = "Missing essential page elements"
                            return 'error', True
                            
                    except Exception as e:
                        logger.warning(f"Error checking page elements: {str(e)}")
                        analysis['page_state'] = 'error'
                        analysis['error_context'] = f"Error checking page elements: {str(e)}"
                        return 'error', True
            
                # Save analysis results
                with open(os.path.join(debug_dir, f'page_analysis_{timestamp}.json'), 'w', encoding='utf-8') as f:
                    json.dump(analysis, f, ensure_ascii=False, indent=2)
                
                return analysis['page_state'], analysis['page_state'].startswith('error')
                
            except Exception as e:
                logger.error(f"Error checking page state: {str(e)}")
                return 'error', True
            
        except Exception as e:
            logger.error(f"Error checking page state: {str(e)}")
            return 'error', True

    def handle_maintenance(self, search_term: str) -> bool:
        """
        Handle site maintenance by saving debug info and deciding whether to continue.
        Returns True if should continue, False if should stop.
        """
        # Save detailed maintenance info
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_dir = os.path.join(self.output_dir, "debug")
        os.makedirs(debug_dir, exist_ok=True)
        
        # Save maintenance page source
        maintenance_source_path = os.path.join(debug_dir, f"maintenance_page_{timestamp}.html")
        with open(maintenance_source_path, "w", encoding="utf-8") as f:
            f.write(self.driver.page_source)
        logger.info(f"Saved maintenance page source to {maintenance_source_path}")
        
        # Save maintenance screenshot
        maintenance_screenshot_path = os.path.join(debug_dir, f"maintenance_screenshot_{timestamp}.png")
        self.driver.save_screenshot(maintenance_screenshot_path)
        logger.info(f"Saved maintenance screenshot to {maintenance_screenshot_path}")
        
        # Create maintenance status file
        status_path = os.path.join(self.output_dir, "maintenance_status.txt")
        with open(status_path, "w", encoding="utf-8") as f:
            f.write(f"Maintenance detected at: {datetime.now().isoformat()}\n")
            f.write(f"Current URL: {self.driver.current_url}\n")
            f.write(f"Page title: {self.driver.title}\n")
            f.write(f"Search term: {search_term}\n")
            f.write(f"Page source (first 1000 chars):\n{self.driver.page_source[:1000]}\n")
        
        # Check if we should continue based on maintenance duration
        if os.path.exists(status_path):
            try:
                with open(status_path, "r", encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        maintenance_start = datetime.fromisoformat(first_line.split(": ")[1])
                        maintenance_duration = datetime.now() - maintenance_start
                        
                        # If maintenance has been ongoing for more than 2 hours, stop
                        if maintenance_duration.total_seconds() > 7200:  # 2 hours
                            logger.error("Maintenance has been ongoing for more than 2 hours. Stopping script.")
                            return False
            except Exception as e:
                logger.error(f"Error reading maintenance status: {str(e)}")
        
        # Wait 30 minutes before next retry
        logger.info("Waiting 30 minutes before next retry...")
        time.sleep(1800)  # 30 minutes
        return True

    def wait_for_page_ready(self, timeout: int = 30) -> bool:
        """Wait for the page to be in a ready state with improved reliability."""
        try:
            # Wait for document.readyState to be 'complete'
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            
            # Wait for jQuery to be ready (if present)
            try:
                WebDriverWait(self.driver, 5).until(
                    lambda driver: driver.execute_script('return jQuery.active') == 0
                )
            except:
                pass  # jQuery might not be present, which is fine
            
            # Wait for any loading indicators to disappear
            loading_selectors = [
                "div.loading",
                "div.spinner",
                "div.loading-indicator",
                "div[data-testid='loading']",
                "div.ajax-loading"
            ]
            
            for selector in loading_selectors:
                try:
                    WebDriverWait(self.driver, 5).until_not(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                except:
                    pass  # Loading indicator might not be present, which is fine
            
            # Check for error pages
            error_indicators = {
                'captcha': ['captcha', 'recaptcha', 'robot', 'verify'],
                'maintenance': ['maintenance', 'メンテナンス', 'system maintenance'],
                'not_found': ['not found', '404', 'page not found', 'ページが見つかりません'],
                'access_denied': ['access denied', '403', 'forbidden', 'アクセスできません'],
                'rate_limit': ['too many requests', 'rate limit', 'アクセス制限'],
                'region_block': ['not available in your region', '地域制限'],
                'error': ['error', 'エラー', '問題が発生しました', 'system error']
            }
            
            page_content = self.driver.page_source.lower()
            for error_type, indicators in error_indicators.items():
                if any(indicator in page_content for indicator in indicators):
                    logger.warning(f"Detected {error_type} page")
                    return False
            
            # Wait for main content to be visible
            main_content_selectors = [
                "div.itemDetail",
                "div.item-detail",
                "div[data-testid='item-detail']",
                "div.auction-item-detail"
            ]
            
            for selector in main_content_selectors:
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    return True
                except:
                    continue
            
            logger.warning("Could not find main content after waiting")
            return False
            
        except TimeoutException:
            logger.warning("Page did not reach ready state within timeout")
            return False
        except Exception as e:
            logger.error(f"Error while waiting for page ready: {str(e)}")
            return False

    def has_next_page(self) -> bool:
        """Check if there is a next page of results."""
        try:
            next_button = self.driver.find_element(By.CSS_SELECTOR, "a.pagination__next:not(.pagination__next--disabled)")
            return True
        except NoSuchElementException:
            return False

    def go_to_next_page(self) -> bool:
        """Navigate to the next page of results."""
        try:
            next_button = self.driver.find_element(By.CSS_SELECTOR, "a.pagination__next:not(.pagination__next--disabled)")
            next_button.click()
            return self.wait_for_page_ready()
        except (NoSuchElementException, WebDriverException) as e:
            logger.warning(f"Failed to navigate to next page: {str(e)}")
            return False

    def handle_cookie_popup(self) -> bool:
        """Handle cookie consent popups with improved reliability."""
        try:
            # Common cookie popup selectors
            cookie_selectors = [
                "button.accept_cookie",
                "button#js-accept-cookies",
                "button.accept-cookies",
                "button[data-testid='cookie-accept']",
                "button.cookie-accept",
                "button.cookie-consent-accept",
                "button[aria-label*='cookie']",
                "button[aria-label*='Cookie']",
                "button[aria-label*='クッキー']",
                "button.cookiePolicyPopup__buttonWrapper button",
                "div.cookiePolicyPopup__buttonWrapper button",
                "button.cookie-banner-accept",
                "button.cookie-notice-accept",
                "button.cookie-consent-button",
                "button.cookie-policy-accept"
            ]
            
            # Try each selector with a short timeout
            for selector in cookie_selectors:
                try:
                    # Wait for button to be clickable
                    cookie_button = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    
                    # Try to click the button
                    try:
                        cookie_button.click()
                        logger.info("Successfully handled cookie popup")
                        time.sleep(1)  # Short wait to let the popup disappear
                        return True
                    except:
                        # If normal click fails, try JavaScript click
                        try:
                            self.driver.execute_script("arguments[0].click();", cookie_button)
                            logger.info("Successfully handled cookie popup using JavaScript")
                            time.sleep(1)
                            return True
                        except:
                            continue
                        
                except TimeoutException:
                    continue
                except Exception as e:
                    logger.debug(f"Error with cookie selector {selector}: {str(e)}")
                    continue
            
            # If no cookie popup was found, that's fine
            return True
            
        except Exception as e:
            logger.warning(f"Error handling cookie popup: {str(e)}")
            return False  # Continue even if cookie handling fails

    def save_initial_promising_links(self, item_summaries: List[Dict[str, Any]], search_term: str) -> None:
        """Save initial promising links to a separate file before detailed analysis."""
        if not item_summaries:
            logger.warning(f"No promising items to save for search term: {search_term}")
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = f"initial_leads_{search_term}_{timestamp}"
            
            # Prepare data for saving
            leads_data = []
            for summary in item_summaries:
                # Extract Yahoo Auction ID from Buyee URL
                yahoo_id_match = re.search(r'/([a-z]\d+)(?:\?|$)', summary['url'])
                yahoo_auction_id = yahoo_id_match.group(1) if yahoo_id_match else None
                yahoo_auction_url = f"https://page.auctions.yahoo.co.jp/jp/auction/{yahoo_auction_id}" if yahoo_auction_id else None
                
                lead_info = {
                    'title': summary['title'],
                    'buyee_url': summary['url'],
                    'yahoo_auction_id': yahoo_auction_id,
                    'yahoo_auction_url': yahoo_auction_url,
                    'price_yen': summary['price_yen'],
                    'price_text': summary['price_text'],
                    'thumbnail_url': summary['thumbnail_url'],
                    'preliminary_analysis': summary['preliminary_analysis'],
                    'timestamp': timestamp
                }
                leads_data.append(lead_info)
            
            # Save as CSV
            df = pd.DataFrame(leads_data)
            csv_path = os.path.join(self.output_dir, f"{base_filename}.csv")
            df.to_csv(csv_path, index=False, encoding='utf-8')
            logger.info(f"Saved {len(leads_data)} initial promising leads to {csv_path}")
            
            # Save as JSON
            json_path = os.path.join(self.output_dir, f"{base_filename}.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(leads_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(leads_data)} initial promising leads to {json_path}")
            
        except Exception as e:
            logger.error(f"Error saving initial promising links: {str(e)}")
            logger.error(traceback.format_exc())

    def search_items(self, search_term: str) -> List[Dict[str, Any]]:
        """Search for items and analyze them."""
        try:
            logger.info(f"Starting search for: {search_term}")
            
            # Check if driver is valid before starting
            if not self.is_driver_valid():
                logger.error("WebDriver is not valid and could not be recreated")
                return []
            
            # Construct search URL
            search_url = f"{self.base_url}/item/search/query/{quote(search_term)}"
            logger.info(f"Search URL: {search_url}")
            
            # Navigate to search page with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.driver.get(search_url)
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Failed to load search page after {max_retries} attempts: {str(e)}")
                        return []
                    logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                    if not self.is_driver_valid():
                        return []
                    time.sleep(2)
            
            # Handle cookie popup if present
            self.handle_cookie_popup()
            
            # Wait for page to be ready
            if not self.wait_for_page_ready():
                logger.error("Page failed to load properly")
                return []
            
            # Initialize results list
            all_items = []
            promising_items = []  # New list for promising items
            page = 1
            
            while page <= self.max_pages:
                # Check if driver is still valid
                if not self.is_driver_valid():
                    logger.error("WebDriver became invalid during search")
                    break
                
                logger.info(f"Processing page {page}")
                
                # Get item summaries from current page
                item_summaries = self.get_item_summaries_from_search_page(page)
                if not item_summaries:
                    logger.warning(f"No items found on page {page}")
                    break
                
                # Process each item
                for summary in item_summaries:
                    try:
                        # Check if driver is still valid before processing each item
                        if not self.is_driver_valid():
                            logger.error("WebDriver became invalid while processing items")
                            break
                        
                        # Get detailed information
                        detailed_info = self.scrape_item_detail_page(summary['url'])
                        if not detailed_info:
                            continue
                        
                        # Check if the item is valuable based on both analyzers
                        is_valuable = (
                            detailed_info['card_details'].get('is_valuable', False) and
                            detailed_info['card_details'].get('confidence_score', 0) >= 0.6 and
                            self.rank_analyzer.is_good_condition(
                                CardCondition(detailed_info['card_details'].get('condition', 'UNKNOWN'))
                            )
                        )
                        
                        if is_valuable:
                            logger.info(f"Found valuable item: {detailed_info['title']}")
                            all_items.append(detailed_info)
                            promising_items.append(detailed_info)  # Add to promising items
                        
                    except Exception as e:
                        logger.error(f"Error processing item {summary['url']}: {str(e)}")
                        logger.error(traceback.format_exc())
                        continue
                
                # Check for next page
                if not self.has_next_page():
                    break
                    
                # Go to next page
                if not self.go_to_next_page():
                    break
                    
                page += 1
            
            # Save all results
            if all_items:
                self.save_results(all_items, search_term)
                logger.info(f"Found {len(all_items)} valuable items for {search_term}")
            
            # Save promising items to bookmarks
            if promising_items:
                self.save_promising_items(promising_items, search_term)
                logger.info(f"Bookmarked {len(promising_items)} promising items for {search_term}")
            else:
                logger.info(f"No promising items found for {search_term}")
            
            return all_items
            
        except Exception as e:
            logger.error(f"Error during search for {search_term}: {str(e)}")
            logger.error(traceback.format_exc())
            return []

    def scrape_item_detail_page(self, url):
        """Scrape detailed information from an item's page with improved reliability."""
        max_retries = 3
        retry_delay = 5
        current_retry = 0
        
        while current_retry < max_retries:
            try:
                if not self.is_driver_valid():
                    self.setup_driver()
                
                logger.info(f"Attempting to scrape item detail page: {url}")
                self.driver.get(url)
                
                # Wait for page to be fully loaded
                if not self.wait_for_page_ready(timeout=30):
                    raise TimeoutException("Page failed to load properly")
                
                # Handle cookie popup if present
                self.handle_cookie_popup()
                
                # Wait for main content to be visible
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.itemDetail"))
                )
                
                # Extract basic information with explicit waits
                title = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1.itemName"))
                ).text.strip()
                
                price_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "span.price"))
                )
                price = self.clean_price(price_element.text)
                
                # Extract description with fallback
                try:
                    description_element = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.itemDescription"))
                    )
                    description = description_element.text.strip()
                except TimeoutException:
                    description = "No description available"
                    logger.warning(f"No description found for item: {url}")
                
                # Extract images with retry logic
                images = []
                try:
                    image_elements = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.itemImage img"))
                    )
                    images = [img.get_attribute('src') for img in image_elements if img.get_attribute('src')]
                except TimeoutException:
                    logger.warning(f"No images found for item: {url}")
                
                # Extract seller information
                try:
                    seller_element = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.sellerName"))
                    )
                    seller = seller_element.text.strip()
                except TimeoutException:
                    seller = "Unknown"
                    logger.warning(f"No seller information found for item: {url}")
                
                # Extract condition information
                try:
                    condition_element = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.itemCondition"))
                    )
                    condition = condition_element.text.strip()
                except TimeoutException:
                    condition = "Unknown"
                    logger.warning(f"No condition information found for item: {url}")
                
                # Parse card details
                card_details = self.parse_card_details_from_buyee(title, description)
                
                # Combine all information
                item_data = {
                    'url': url,
                    'title': title,
                    'price': price,
                    'description': description,
                    'images': images,
                    'seller': seller,
                    'condition': condition,
                    'card_details': card_details,
                    'scraped_at': datetime.now().isoformat()
                }
                
                logger.info(f"Successfully scraped item: {title}")
                return item_data
                
            except TimeoutException as e:
                current_retry += 1
                logger.warning(f"Timeout while scraping {url} (Attempt {current_retry}/{max_retries}): {str(e)}")
                if current_retry < max_retries:
                    time.sleep(retry_delay)
                    continue
                self.save_debug_info(url, "timeout", self.driver.page_source)
                return None
                
            except WebDriverException as e:
                current_retry += 1
                logger.error(f"WebDriver error while scraping {url} (Attempt {current_retry}/{max_retries}): {str(e)}")
                if current_retry < max_retries:
                    time.sleep(retry_delay)
                    self.setup_driver()  # Reset driver on WebDriverException
                    continue
                self.save_debug_info(url, "webdriver_error", self.driver.page_source)
                return None
                
            except Exception as e:
                logger.error(f"Unexpected error while scraping {url}: {str(e)}")
                self.save_debug_info(url, "unexpected_error", self.driver.page_source)
                return None
        
        logger.error(f"Failed to scrape {url} after {max_retries} attempts")
        return None

    def get_item_summaries_from_search_page(self, page_number: int = 1) -> List[Dict]:
        """Extract item summaries from the current search results page."""
        summaries = []
        debug_dir = os.path.join(self.output_dir, "debug")
        os.makedirs(debug_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # First, verify we're on a search results page
            current_url = self.driver.current_url
            if "item/search" not in current_url:
                logger.error(f"Not on a search results page. Current URL: {current_url}")
                self.save_debug_info(f"search_page_{timestamp}", "wrong_page", self.driver.page_source)
                return []
            
            # Save initial page state for debugging
            with open(os.path.join(debug_dir, f"search_page_initial_{timestamp}.html"), 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            
            # Try multiple selectors for item cards
            item_card_selectors = [
                "li.itemCard",
                "div[data-testid='item-card']",
                "div.item-card",
                "div.search-result-item"
            ]
            
            card_elements = []
            used_selector = None
            
            # Try each selector in sequence
            for selector in item_card_selectors:
                try:
                    logger.info(f"Attempting to find item cards with selector: '{selector}'")
                    card_elements = WebDriverWait(self.driver, 15).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                    )
                    if card_elements:
                        used_selector = selector
                        logger.info(f"Successfully found {len(card_elements)} item cards using selector: '{selector}'")
                        break
                except TimeoutException:
                    logger.warning(f"Timeout waiting for item cards with selector: '{selector}'")
                    continue
                except Exception as e:
                    logger.warning(f"Error with selector '{selector}': {str(e)}")
                    continue
            
            if not card_elements:
                logger.error("No item cards found with any selector")
                self.save_debug_info(f"search_page_{timestamp}", "no_cards_found", self.driver.page_source)
                return []
            
            # Process each card with robust error handling
            for i, card in enumerate(card_elements):
                try:
                    # Try multiple selectors for each element
                    title_selectors = [
                        "h3[data-testid='item-card-title']",
                        "div.itemCard__itemName a",
                        "div.item-title a",
                        "a.item-title"
                    ]
                    
                    price_selectors = [
                        "span[data-testid='item-card-price']",
                        "div.g-priceDetails span.g-price",
                        "div.item-price",
                        "span.price"
                    ]
                    
                    # Extract title and URL
                    title = None
                    url = None
                    for selector in title_selectors:
                        try:
                            title_element = card.find_element(By.CSS_SELECTOR, selector)
                            title = title_element.text.strip()
                            url = title_element.get_attribute('href')
                            if title and url:
                                break
                        except NoSuchElementException:
                            continue
                    
                    if not title or not url:
                        logger.warning(f"Could not extract title/URL for card {i+1}")
                        continue
                    
                    # Extract price
                    price_text = None
                    for selector in price_selectors:
                        try:
                            price_element = card.find_element(By.CSS_SELECTOR, selector)
                            price_text = price_element.text.strip()
                            if price_text:
                                break
                        except NoSuchElementException:
                            continue
                    
                    if not price_text:
                        logger.warning(f"Could not extract price for card {i+1}: {title}")
                        continue
                    
                    price_yen = self.clean_price(price_text)
                    
                    # Extract thumbnail URL
                    thumbnail_url = None
                    thumbnail_selectors = [
                        "img[data-testid='item-card-image']",
                        "div.itemCard__image img",
                        "div.item-image img",
                        "img.item-image"
                    ]
                    
                    for selector in thumbnail_selectors:
                        try:
                            img_element = card.find_element(By.CSS_SELECTOR, selector)
                            thumbnail_url = img_element.get_attribute('src') or img_element.get_attribute('data-src')
                            if thumbnail_url:
                                break
                        except NoSuchElementException:
                            continue
                    
                    # Log basic info
                    logger.info(f"Item {i+1}/{len(card_elements)}:")
                    logger.info(f"  Title: {title}")
                    logger.info(f"  Price: {price_yen} yen")
                    logger.info(f"  URL: {url}")
                    
                    # Analyze the card
                    try:
                        card_info = self.card_analyzer.analyze_card({
                            'title': title,
                            'price_text': price_text,
                            'url': url,
                            'thumbnail_url': thumbnail_url
                        })
                        
                        # Convert CardInfo to dictionary for logging and storage
                        preliminary_analysis = {
                            'is_valuable': card_info.is_valuable,
                            'confidence_score': card_info.confidence_score,
                            'condition': str(card_info.condition.value) if card_info.condition else None,  # Convert CardCondition enum to string
                            'rarity': card_info.rarity,
                            'set_code': card_info.set_code,
                            'card_number': card_info.card_number,
                            'edition': card_info.edition,
                            'region': card_info.region
                        }
                        
                        # Log analysis results
                        logger.info(f"  Analysis Results:")
                        for key, value in preliminary_analysis.items():
                            logger.info(f"    {key.replace('_', ' ').title()}: {value}")
                        
                        # Create card info dictionary
                        card_info_dict = {
                            'title': title,
                            'price_text': price_text,
                            'price_yen': price_yen,
                            'url': url,
                            'thumbnail_url': thumbnail_url,
                            'preliminary_analysis': preliminary_analysis
                        }
                        
                        # Add to summaries if it's promising
                        if preliminary_analysis['is_valuable'] and preliminary_analysis['confidence_score'] >= 0.3:
                            summaries.append(card_info_dict)
                            logger.info(f"  Added promising item to summaries")
                        else:
                            logger.debug(f"  Skipped item at initial filter")
                        
                    except Exception as analysis_error:
                        logger.error(f"Error during card analysis for '{title}': {str(analysis_error)}")
                        logger.error(traceback.format_exc())
                        continue
                    
                except StaleElementReferenceException:
                    logger.warning(f"StaleElementReferenceException while processing card {i+1}. Page might have updated.")
                    # Save current page state for debugging
                    self.save_debug_info(f"search_page_stale_{timestamp}", "stale_element", self.driver.page_source)
                    break  # Break from the loop as the page has likely updated
                    
                except Exception as card_error:
                    logger.error(f"Error processing card {i+1}: {str(card_error)}")
                    logger.error(traceback.format_exc())
                    continue
            
            # Save successful scrape info
            if summaries:
                success_info = {
                    'timestamp': timestamp,
                    'page_number': page_number,
                    'total_cards_found': len(card_elements),
                    'promising_items': len(summaries),
                    'used_selector': used_selector
                }
                success_path = os.path.join(debug_dir, f"search_page_success_{timestamp}.json")
                with open(success_path, 'w', encoding='utf-8') as f:
                    json.dump(success_info, f, ensure_ascii=False, indent=2)
            
            return summaries
            
        except Exception as e:
            logger.error(f"Error getting item summaries: {str(e)}")
            logger.error(traceback.format_exc())
            self.save_debug_info(f"search_page_error_{timestamp}", "error", self.driver.page_source)
            return []

    def save_results(self, results: List[Dict[str, Any]], search_term: str) -> None:
        """Save results to CSV and JSON files with error handling."""
        if not results:
            logger.warning(f"No results to save for search term: {search_term}")
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = f"buyee_listings_{search_term}_{timestamp}"
            
            # Save as CSV
            df = pd.DataFrame(results)
            csv_path = os.path.join(self.output_dir, f"{base_filename}.csv")
            df.to_csv(csv_path, index=False, encoding='utf-8')
            logger.info(f"Saved {len(results)} results to {csv_path}")
            
            # Save as JSON
            json_path = os.path.join(self.output_dir, f"{base_filename}.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(results)} results to {json_path}")
            
        except Exception as e:
            logger.error(f"Error saving results: {str(e)}")
            logger.error(traceback.format_exc())

    def close(self):
        """Close the WebDriver with error handling."""
        try:
            self.driver.quit()
            logger.info("WebDriver closed successfully")
        except Exception as e:
            logger.error(f"Error closing WebDriver: {str(e)}")

    def parse_card_details_from_buyee(self, title: str, description: str) -> Dict[str, Any]:
        """
        Parse card details from Buyee listing title and description.
        Returns a dictionary containing structured card information.
        """
        details = {
            'name': None,
            'set_code': None,
            'card_number': None,
            'rarity': None,
            'edition': None,
            'language': None,
            'rank': None,
            'condition_text': None
        }
        
        try:
            # Extract rank from description
            if description:
                rank_match = re.search(r'【ランク】\s*([A-Z]+)', description)
                if rank_match:
                    details['rank'] = rank_match.group(1)
                    logger.debug(f"Found rank: {details['rank']}")
            
            # Extract set code and card number
            set_code_match = re.search(r'([A-Z]{2,4})-([A-Z]{2})(\d{3})', title)
            if set_code_match:
                details['set_code'] = set_code_match.group(1)
                details['card_number'] = set_code_match.group(3)
                logger.debug(f"Found set code: {details['set_code']}, card number: {details['card_number']}")
            
            # Extract rarity
            rarity_keywords = {
                'Secret Rare': ['secret rare', 'シークレットレア', 'sr'],
                'Ultimate Rare': ['ultimate rare', 'アルティメットレア', 'ur'],
                'Ghost Rare': ['ghost rare', 'ゴーストレア', 'gr'],
                'Collector\'s Rare': ['collector\'s rare', 'コレクターズレア', 'cr'],
                'Starlight Rare': ['starlight rare', 'スターライトレア', 'str'],
                'Quarter Century Secret Rare': ['quarter century secret rare', 'クォーターセンチュリーシークレットレア', 'qcsr'],
                'Prismatic Secret Rare': ['prismatic secret rare', 'プリズマティックシークレットレア', 'psr'],
                'Platinum Secret Rare': ['platinum secret rare', 'プラチナシークレットレア', 'plsr'],
                'Gold Secret Rare': ['gold secret rare', 'ゴールドシークレットレア', 'gsr'],
                'Ultra Rare': ['ultra rare', 'ウルトラレア', 'ur'],
                'Super Rare': ['super rare', 'スーパーレア', 'sr'],
                'Rare': ['rare', 'レア', 'r'],
                'Common': ['common', 'ノーマル', 'n']
            }
            
            for rarity, keywords in rarity_keywords.items():
                if any(keyword.lower() in title.lower() for keyword in keywords):
                    details['rarity'] = rarity
                    logger.debug(f"Found rarity: {rarity}")
                    break
            
            # Extract edition
            edition_keywords = {
                '1st Edition': ['1st', 'first edition', '初版', '初刷'],
                'Unlimited': ['unlimited', '無制限', '再版', '再刷']
            }
            
            for edition, keywords in edition_keywords.items():
                if any(keyword.lower() in title.lower() for keyword in keywords):
                    details['edition'] = edition
                    logger.debug(f"Found edition: {edition}")
                    break
            
            # Extract language/region
            region_keywords = {
                'Asia': ['asia', 'asian', 'アジア', 'アジア版'],
                'English': ['english', '英', '英語版'],
                'Japanese': ['japanese', '日', '日本語版'],
                'Korean': ['korean', '韓', '韓国版']
            }
            
            for region, keywords in region_keywords.items():
                if any(keyword.lower() in title.lower() for keyword in keywords):
                    details['language'] = region
                    logger.debug(f"Found language/region: {region}")
                    break
            
            # Extract condition text from description
            if description:
                condition_section = re.search(r'【商品の状態】\s*(.*?)(?=\n|$)', description)
                if condition_section:
                    details['condition_text'] = condition_section.group(1).strip()
                    logger.debug(f"Found condition text: {details['condition_text']}")
            
            # Try to extract card name (this is more complex and might need improvement)
            # For now, we'll just use the title as the name
            details['name'] = title.strip()
            
            logger.info(f"Successfully parsed card details from Buyee listing")
            return details
            
        except Exception as e:
            logger.error(f"Error parsing card details: {str(e)}")
            return details

    def is_driver_valid(self) -> bool:
        """Check if the WebDriver is still valid and handle reconnection if needed."""
        try:
            # Try a simple command to check if driver is responsive
            self.driver.current_url
            return True
        except Exception as e:
            logger.error(f"WebDriver is not valid: {str(e)}")
            try:
                # Try to clean up the old driver
                self.cleanup()
            except:
                pass
            # Try to create a new driver
            try:
                self.setup_driver()
                return True
            except Exception as setup_error:
                logger.error(f"Failed to recreate WebDriver: {str(setup_error)}")
                return False

    def save_promising_items(self, items: List[Dict[str, Any]], search_term: str) -> None:
        """Save promising items to a bookmarks file for easy review."""
        if not items:
            logger.warning(f"No promising items to bookmark for search term: {search_term}")
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            bookmarks_dir = os.path.join(self.output_dir, "bookmarks")
            os.makedirs(bookmarks_dir, exist_ok=True)
            
            # Prepare data for saving
            bookmarks_data = []
            for item in items:
                # Extract Yahoo Auction ID from Buyee URL
                yahoo_id_match = re.search(r'/([a-z]\d+)(?:\?|$)', item['url'])
                yahoo_auction_id = yahoo_id_match.group(1) if yahoo_id_match else None
                yahoo_auction_url = f"https://page.auctions.yahoo.co.jp/jp/auction/{yahoo_auction_id}" if yahoo_auction_id else None
                
                bookmark_info = {
                    'title': item['title'],
                    'buyee_url': item['url'],
                    'yahoo_auction_id': yahoo_auction_id,
                    'yahoo_auction_url': yahoo_auction_url,
                    'price_yen': item['price'],
                    'condition': item['condition'],
                    'seller': item['seller'],
                    'card_details': item['card_details'],
                    'images': item['images'],
                    'scraped_at': item['scraped_at'],
                    'search_term': search_term
                }
                bookmarks_data.append(bookmark_info)
            
            # Save as CSV
            df = pd.DataFrame(bookmarks_data)
            csv_path = os.path.join(bookmarks_dir, f"bookmarks_{search_term}_{timestamp}.csv")
            df.to_csv(csv_path, index=False, encoding='utf-8')
            logger.info(f"Saved {len(bookmarks_data)} bookmarked items to {csv_path}")
            
            # Save as JSON
            json_path = os.path.join(bookmarks_dir, f"bookmarks_{search_term}_{timestamp}.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(bookmarks_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(bookmarks_data)} bookmarked items to {json_path}")
            
            # Create a summary HTML file for easy viewing
            html_path = os.path.join(bookmarks_dir, f"bookmarks_{search_term}_{timestamp}.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write("""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Bookmarked Items</title>
                    <style>
                        body { font-family: Arial, sans-serif; margin: 20px; }
                        .item { border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }
                        .item:hover { background-color: #f5f5f5; }
                        .title { font-size: 1.2em; font-weight: bold; margin-bottom: 10px; }
                        .price { color: #e44d26; font-weight: bold; }
                        .details { margin: 10px 0; }
                        .image { max-width: 200px; margin: 10px 0; }
                        .links { margin-top: 10px; }
                        .links a { margin-right: 15px; }
                    </style>
                </head>
                <body>
                    <h1>Bookmarked Items</h1>
                    <p>Search Term: {search_term}</p>
                    <p>Total Items: {len(bookmarks_data)}</p>
                    <div class="items">
                """.format(search_term=search_term, len=len(bookmarks_data)))
                
                for item in bookmarks_data:
                    f.write(f"""
                    <div class="item">
                        <div class="title">{item['title']}</div>
                        <div class="price">Price: ¥{item['price_yen']:,.0f}</div>
                        <div class="details">
                            <p>Condition: {item['condition']}</p>
                            <p>Seller: {item['seller']}</p>
                            <p>Card Details: {json.dumps(item['card_details'], ensure_ascii=False)}</p>
                        </div>
                        <div class="links">
                            <a href="{item['buyee_url']}" target="_blank">View on Buyee</a>
                            {f'<a href="{item["yahoo_auction_url"]}" target="_blank">View on Yahoo Auctions</a>' if item['yahoo_auction_url'] else ''}
                        </div>
                        {f'<img class="image" src="{item["images"][0]}" alt="Card Image">' if item['images'] else ''}
                    </div>
                    """)
                
                f.write("""
                    </div>
                </body>
                </html>
                """)
            
            logger.info(f"Created HTML summary at {html_path}")
            
        except Exception as e:
            logger.error(f"Error saving bookmarked items: {str(e)}")
            logger.error(traceback.format_exc())

def main():
    parser = argparse.ArgumentParser(description='Scrape Buyee for Yu-Gi-Oh cards')
    parser.add_argument('--output-dir', default='scraped_results', help='Directory to save results')
    parser.add_argument('--max-pages', type=int, default=5, help='Maximum pages to scrape per search')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    args = parser.parse_args()
    
    scraper = None
    try:
        scraper = BuyeeScraper(
            output_dir=args.output_dir,
            max_pages=args.max_pages,
            headless=args.headless
        )
        
        # Test connection first
        if not scraper.test_connection():
            logger.error("Failed to establish connection. Exiting.")
            return
        
        # Process each search term
        for search_term in SEARCH_TERMS:
            try:
                # Check if driver is valid before each search
                if not scraper.is_driver_valid():
                    logger.error("WebDriver is not valid before starting search. Attempting to recreate...")
                    if not scraper.is_driver_valid():  # Try one more time
                        logger.error("Failed to recreate WebDriver. Skipping search term.")
                        continue
                
                logger.info(f"Starting search for term: {search_term}")
                results = scraper.search_items(search_term)
                
                if results:
                    logger.info(f"Found {len(results)} valuable items for {search_term}")
                else:
                    logger.info(f"No valuable items found for {search_term}")
                    
            except Exception as e:
                logger.error(f"Error processing search term {search_term}: {str(e)}")
                logger.error(traceback.format_exc())
                continue
                
    except Exception as e:
        logger.error(f"Fatal error in main: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        if scraper:
            try:
                scraper.close()
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}")

if __name__ == "__main__":
    main() 