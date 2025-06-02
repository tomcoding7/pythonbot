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
from card_analyzer import CardAnalyzer
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
        self.base_url = "https://buyee.jp"
        self.output_dir = output_dir
        self.max_pages = max_pages
        self.headless = headless
        os.makedirs(self.output_dir, exist_ok=True)
        self.setup_driver()

    def save_debug_info(self, search_term: str, error_type: str, page_source: str = None, screenshot: bool = True):
        """Save debug information including page source and screenshot."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_dir = os.path.join(self.output_dir, "debug")
        os.makedirs(debug_dir, exist_ok=True)
        
        # Save page source
        if page_source:
            source_path = os.path.join(debug_dir, f"page_source_{error_type}_{search_term}_{timestamp}.html")
            with open(source_path, "w", encoding="utf-8") as f:
                f.write(page_source)
            logger.info(f"Saved page source to {source_path}")
        
        # Save screenshot
        if screenshot:
            try:
                screenshot_path = os.path.join(debug_dir, f"screenshot_{error_type}_{search_term}_{timestamp}.png")
                self.driver.save_screenshot(screenshot_path)
                logger.info(f"Saved screenshot to {screenshot_path}")
            except Exception as e:
                logger.error(f"Failed to save screenshot: {str(e)}")
        
        # Save system info
        try:
            system_info = {
                "timestamp": timestamp,
                "error_type": error_type,
                "search_term": search_term,
                "chrome_version": self.driver.capabilities.get('chrome', {}).get('chromedriverVersion', 'unknown'),
                "platform": self.driver.capabilities.get('platformName', 'unknown'),
                "browser_version": self.driver.capabilities.get('browserVersion', 'unknown'),
                "user_agent": self.driver.execute_script("return navigator.userAgent"),
                "timezone": self.driver.execute_script("return Intl.DateTimeFormat().resolvedOptions().timeZone"),
                "system_time": datetime.now().isoformat()
            }
            
            system_info_path = os.path.join(debug_dir, f"system_info_{error_type}_{search_term}_{timestamp}.json")
            with open(system_info_path, "w", encoding="utf-8") as f:
                json.dump(system_info, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved system info to {system_info_path}")
            
        except Exception as e:
            logger.error(f"Failed to save system info: {str(e)}")

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
                        EC.presence_of_element_located((By.CSS_SELECTOR, analysis['item_analysis']['container_selector']))
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
        """
        Wait for the page to be in a ready state, handling various conditions.
        Returns True if page is ready for processing, False otherwise.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            state, is_error = self.check_page_state()
            
            if state == 'ready':
                return True
            elif state == 'no_results':
                return True  # No results is a valid state
            elif is_error:
                return False
            elif state == 'loading':
                time.sleep(2)  # Wait a bit before checking again
                continue
                
        logger.warning(f"Page did not reach ready state within {timeout} seconds")
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
        """Handle the cookie consent popup if present. Returns True if handled or not present."""
        try:
            logger.info("Checking for cookie consent pop-up...")
            accept_button = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div.cookiePolicyPopup__buttonWrapper button.accept_cookie"))
            )
            logger.info("Cookie consent pop-up found. Clicking 'Accept All Cookies'.")
            accept_button.click()
            time.sleep(2)  # Give a moment for the pop-up to disappear and page to adjust
            return True
        except TimeoutException:
            logger.info("Cookie consent pop-up not found or not clickable within timeout.")
            return True  # Not an error, just no popup
        except Exception as e:
            logger.warning(f"Error handling cookie pop-up: {e}")
            return False

    def search_items(self, search_term: str) -> List[Dict[str, Any]]:
        """Search for items using the given search term."""
        items = []
        max_retries = 3
        base_delay = 30  # seconds
        max_delay = 300  # maximum delay of 5 minutes
        
        for attempt in range(max_retries):
            try:
                # Calculate delay with exponential backoff
                current_delay = min(base_delay * (2 ** attempt), max_delay)
                
                # Construct search URL with sorting by popularity
                encoded_term = quote(search_term)
                search_url = f"https://buyee.jp/item/search/query/{encoded_term}?sort=popularity"  # Added sort parameter
                
                logger.info(f"Attempting search (attempt {attempt + 1}/{max_retries}): {search_url}")
                
                try:
                    # Load the page with explicit SSL error handling
                    self.driver.get(search_url)
                    
                    # Handle cookie popup if present
                    if not self.handle_cookie_popup():
                        logger.warning("Failed to handle cookie popup, but continuing...")
                    
                except WebDriverException as e:
                    if "SSL" in str(e) or "handshake" in str(e).lower():
                        logger.error(f"SSL handshake error on attempt {attempt + 1}: {str(e)}")
                        if attempt < max_retries - 1:
                            logger.info(f"SSL error occurred. Waiting {current_delay} seconds before retry...")
                            time.sleep(current_delay)
                            continue
                        else:
                            logger.error("Max retries reached after SSL errors")
                            break
                    else:
                        raise  # Re-raise if it's not an SSL error
                
                # Wait for page to be ready
                state, is_error = self.check_page_state()
                
                if state == 'ready':
                    # Page is ready, proceed with scraping
                    logger.info("Page is ready, proceeding with scraping")
                    items = self.scrape_items()
                    if items:
                        logger.info(f"Successfully scraped {len(items)} valuable items")
                        break  # Success, exit retry loop
                    else:
                        logger.info("No valuable items found, but page loaded successfully")
                        break  # No items found, but page loaded correctly
                        
                elif state == 'no_results':
                    logger.info(f"No results found for search term: {search_term}")
                    break  # No results is a valid state, no need to retry
                    
                elif is_error:
                    logger.error(f"Error state detected: {state}")
                    
                    if attempt < max_retries - 1:
                        logger.info(f"Error state detected. Waiting {current_delay} seconds before retry...")
                        time.sleep(current_delay)
                    else:
                        logger.error("Max retries reached after error states")
                        break
                        
            except Exception as e:
                logger.error(f"Error during search attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"Error occurred. Waiting {current_delay} seconds before retry...")
                    time.sleep(current_delay)
                else:
                    logger.error("Max retries reached after general errors")
                    break
        
        return items

    def scrape_item_details(self, item_url: str) -> Dict[str, Any]:
        """
        Scrape detailed information from an individual item page.
        Returns a dictionary containing the item's detailed information.
        """
        try:
            # Navigate to the item page
            self.driver.get(item_url)
            
            # Wait for the page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.itemDetail"))
            )
            
            details = {}
            
            # Extract seller's condition description
            try:
                condition_element = self.driver.find_element(By.CSS_SELECTOR, "div.itemDetail__condition")
                details['seller_condition'] = condition_element.text.strip()
                logger.debug(f"Found seller condition: {details['seller_condition']}")
            except NoSuchElementException:
                details['seller_condition'] = None
                logger.warning(f"Could not find seller condition for item: {item_url}")
            
            # Extract full item description
            try:
                description_element = self.driver.find_element(By.CSS_SELECTOR, "div.itemDetail__description")
                details['description'] = description_element.text.strip()
                logger.debug(f"Found description: {details['description'][:200]}...")  # Log first 200 chars
            except NoSuchElementException:
                details['description'] = None
                logger.warning(f"Could not find description for item: {item_url}")
            
            # Extract rank if present in description
            if details.get('description'):
                rank_match = re.search(r'【ランク】\s*([A-Z]+)', details['description'])
                if rank_match:
                    details['rank'] = rank_match.group(1)
                    logger.debug(f"Found rank: {details['rank']}")
                else:
                    details['rank'] = None
                    logger.debug("No rank found in description")
            
            # Extract all images
            try:
                # Main image
                main_img = self.driver.find_element(By.CSS_SELECTOR, "div.itemDetail__image img")
                details['main_image_url'] = main_img.get_attribute('src')
                if not details['main_image_url'] or 'spacer.gif' in details['main_image_url']:
                    data_src = main_img.get_attribute('data-src')
                    if data_src:
                        details['main_image_url'] = data_src
                
                # Additional images
                image_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.itemDetail__imageGallery img")
                details['additional_images'] = []
                for img in image_elements:
                    img_url = img.get_attribute('src')
                    if not img_url or 'spacer.gif' in img_url:
                        data_src = img.get_attribute('data-src')
                        if data_src:
                            img_url = data_src
                    if img_url:
                        details['additional_images'].append(img_url)
                
                logger.debug(f"Found {len(details['additional_images']) + 1} images")
            except NoSuchElementException:
                details['main_image_url'] = None
                details['additional_images'] = []
                logger.warning(f"Could not find images for item: {item_url}")
            
            # Extract seller information
            try:
                seller_element = self.driver.find_element(By.CSS_SELECTOR, "div.itemDetail__seller")
                details['seller_name'] = seller_element.text.strip()
                logger.debug(f"Found seller: {details['seller_name']}")
            except NoSuchElementException:
                details['seller_name'] = None
            
            # Extract shipping information
            try:
                shipping_element = self.driver.find_element(By.CSS_SELECTOR, "div.itemDetail__shipping")
                details['shipping_info'] = shipping_element.text.strip()
                logger.debug(f"Found shipping info: {details['shipping_info']}")
            except NoSuchElementException:
                details['shipping_info'] = None
            
            # Extract time remaining
            try:
                time_element = self.driver.find_element(By.CSS_SELECTOR, "div.itemDetail__timeRemaining")
                details['time_remaining'] = time_element.text.strip()
                logger.debug(f"Found time remaining: {details['time_remaining']}")
            except NoSuchElementException:
                details['time_remaining'] = None
            
            # Extract bid count
            try:
                bid_element = self.driver.find_element(By.CSS_SELECTOR, "div.itemDetail__bidCount")
                details['bid_count'] = bid_element.text.strip()
                logger.debug(f"Found bid count: {details['bid_count']}")
            except NoSuchElementException:
                details['bid_count'] = None
            
            # Analyze condition using RankAnalyzer
            rank_analyzer = RankAnalyzer()
            condition_analysis = rank_analyzer.analyze_condition(
                details.get('description', ''),
                details.get('seller_condition', '')
            )
            
            # Add condition analysis results to details
            details.update({
                'rank': condition_analysis['rank'],
                'condition': condition_analysis['condition'].value,
                'condition_confidence': condition_analysis['confidence'],
                'condition_indicators': condition_analysis['condition_indicators'],
                'condition_warnings': condition_analysis['warnings']
            })
            
            logger.info(f"Successfully scraped details for item: {item_url}")
            return details
            
        except Exception as e:
            logger.error(f"Error scraping item details for {item_url}: {str(e)}")
            return {
                'seller_condition': None,
                'description': None,
                'rank': None,
                'condition': CardCondition.UNKNOWN.value,
                'condition_confidence': 0.0,
                'condition_indicators': [],
                'condition_warnings': [f"Error: {str(e)}"],
                'main_image_url': None,
                'additional_images': [],
                'seller_name': None,
                'shipping_info': None,
                'time_remaining': None,
                'bid_count': None,
                'error': str(e)
            }

    def scrape_items(self) -> List[Dict[str, Any]]:
        """Scrape items from the current page."""
        items = []
        card_analyzer = CardAnalyzer()
        
        # Define minimum acceptable rank
        MIN_ACCEPTABLE_RANK = 'A'  # Only consider items with rank A or better
        
        try:
            # Get initial count of items
            item_card_selector = "li.itemCard"
            logger.debug(f"Attempting to find all item cards with selector: '{item_card_selector}'")
            
            item_cards = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, item_card_selector))
            )
            total_items = len(item_cards)
            logger.info(f"Found {total_items} item cards using '{item_card_selector}'.")
            
            # Process items by index instead of direct iteration
            i = 0
            while i < total_items:
                try:
                    # Re-fetch the current card to avoid stale references
                    current_cards = self.driver.find_elements(By.CSS_SELECTOR, item_card_selector)
                    if i >= len(current_cards):
                        logger.warning(f"Index {i} out of bounds after re-fetching cards. Current count: {len(current_cards)}")
                        break
                    
                    card = current_cards[i]
                    item_data = {}
                    
                    # Extract all data from the card as quickly as possible
                    try:
                        # Title and URL
                        title_element = card.find_element(By.CSS_SELECTOR, "div.itemCard__itemName a")
                        item_data['title'] = title_element.text.strip()
                        item_data['url'] = title_element.get_attribute('href')
                        
                        # Price
                        price_element = card.find_element(By.CSS_SELECTOR, "div.g-priceDetails span.g-price")
                        raw_price = price_element.text.strip()
                        item_data['price'] = raw_price
                        item_data['price_yen'] = self.clean_price(raw_price)
                        
                        # Log extracted data for debugging
                        logger.debug(f"EXTRACTED Card {i+1}/{total_items}: Title='{item_data['title']}', RawPrice='{raw_price}', CleanedPriceYen={item_data['price_yen']}")
                        
                        # Get detailed information from the item page
                        item_details = self.scrape_item_details(item_data['url'])
                        
                        # Parse card details from the listing
                        card_details = self.parse_card_details_from_buyee(item_data['title'], item_details.get('description', ''))
                        
                        # Update item data with all the information
                        item_data.update(item_details)
                        item_data.update(card_details)
                        
                        # Initial filtering based on rank
                        if item_data.get('rank') and item_data['rank'] >= MIN_ACCEPTABLE_RANK:
                            logger.debug(f"Card passed rank filter: {item_data['rank']}")
                            
                            # Analyze card with CardAnalyzer
                            card_info = card_analyzer.analyze_card(item_data)
                            logger.debug(f"Card analysis - Valuable: {card_info.is_valuable}, Confidence: {card_info.confidence_score}")
                            
                            # More lenient filtering - only require good condition
                            if card_info.condition in [CardCondition.MINT, CardCondition.NEAR_MINT, CardCondition.EXCELLENT, CardCondition.VERY_GOOD]:
                                # Add analysis results to item data
                                item_data.update({
                                    'condition': card_info.condition.value,
                                    'rarity': card_info.rarity,
                                    'set_code': card_info.set_code,
                                    'card_number': card_info.card_number,
                                    'edition': card_info.edition,
                                    'region': card_info.region,
                                    'confidence_score': card_info.confidence_score,
                                    'is_valuable': card_info.is_valuable
                                })
                                
                                items.append(item_data)
                                logger.info(f"Found valuable card: {card_info.title} ({card_info.condition.value}, {card_info.rarity})")
                            else:
                                logger.debug(f"Card failed condition filter - Condition: {card_info.condition.value} not in acceptable range")
                        else:
                            logger.debug(f"Card failed rank filter - Rank: {item_data.get('rank', 'None')} below minimum {MIN_ACCEPTABLE_RANK}")
                        
                        # If we got here without exceptions, move to next card
                        i += 1
                        
                    except StaleElementReferenceException:
                        logger.warning(f"StaleElementReferenceException for card at index {i}. Re-fetching card list...")
                        # Don't increment i, we'll retry this card with fresh elements
                        continue
                        
                except Exception as e:
                    logger.warning(f"Error processing card at index {i}: {str(e)}")
                    # Move to next card even if there was an error
                    i += 1
                    continue
            
            if items:
                logger.info(f"Successfully scraped {len(items)} valuable items")
            else:
                logger.info("No valuable items found on this page")
            
        except Exception as e:
            logger.error(f"Error during item scraping: {str(e)}")
        
        return items

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

def main():
    parser = argparse.ArgumentParser(description='Scrape Buyee for Yu-Gi-Oh cards')
    parser.add_argument('--output-dir', default='scraped_results', help='Directory to save results')
    parser.add_argument('--max-pages', type=int, default=5, help='Maximum number of pages to scrape per search term')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    args = parser.parse_args()
    
    scraper = BuyeeScraper(
        output_dir=args.output_dir,
        max_pages=args.max_pages,
        headless=args.headless
    )
    
    try:
        for search_term in SEARCH_TERMS:
            logger.info(f"Starting search for term: {search_term}")
            results = scraper.search_items(search_term)
            scraper.save_results(results, search_term)
            logger.info(f"Completed search for term: {search_term}")
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error in main: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        scraper.close()

if __name__ == "__main__":
    main() 