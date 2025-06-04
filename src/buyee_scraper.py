from bs4 import BeautifulSoup
import re
import logging
from typing import List, Dict, Optional, Any
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time

class BuyeeScraper:
    def get_item_summaries_from_search_page(self, html_content: str) -> List[Dict]:
        """Extract item summaries from a search page."""
        soup = BeautifulSoup(html_content, 'html.parser')
        items = []
        
        # Find all item containers
        item_containers = soup.find_all('div', class_='item-card')
        
        for container in item_containers:
            try:
                # Extract basic information
                title_elem = container.find('div', class_='item-card__title')
                price_elem = container.find('div', class_='item-card__price')
                link_elem = container.find('a', class_='item-card__link')
                
                if not all([title_elem, price_elem, link_elem]):
                    continue
                
                title = title_elem.get_text(strip=True)
                price_text = price_elem.get_text(strip=True)
                link = link_elem.get('href', '')
                
                # Extract price value
                price_match = re.search(r'[\d,]+', price_text)
                if not price_match:
                    continue
                    
                price = int(price_match.group().replace(',', ''))
                
                # Skip if price is too high
                if price > self.max_price:
                    continue
                
                # Analyze title for valuable keywords
                title_lower = title.lower()
                confidence = 0.0
                matched_keywords = []
                
                # Check for brand names
                for brand in self.brand_keywords:
                    if brand.lower() in title_lower:
                        confidence += 0.4  # Increased from 0.3
                        matched_keywords.append(brand)
                
                # Check for condition keywords
                for condition in self.condition_keywords:
                    if condition.lower() in title_lower:
                        confidence += 0.2  # Increased from 0.15
                        matched_keywords.append(condition)
                
                # Check for model keywords
                for model in self.model_keywords:
                    if model.lower() in title_lower:
                        confidence += 0.3  # Increased from 0.25
                        matched_keywords.append(model)
                
                # Check for material keywords
                for material in self.material_keywords:
                    if material.lower() in title_lower:
                        confidence += 0.15  # Increased from 0.1
                        matched_keywords.append(material)
                
                # Check for style keywords
                for style in self.style_keywords:
                    if style.lower() in title_lower:
                        confidence += 0.15  # Increased from 0.1
                        matched_keywords.append(style)
                
                # Check for size keywords
                for size in self.size_keywords:
                    if size.lower() in title_lower:
                        confidence += 0.1  # Increased from 0.05
                        matched_keywords.append(size)
                
                # Log detailed information about the item
                logging.info(f"\nAnalyzing item: {title}")
                logging.info(f"Price: {price}")
                logging.info(f"Matched keywords: {', '.join(matched_keywords)}")
                logging.info(f"Confidence score: {confidence:.2f}")
                
                # Lower confidence threshold to 0.2 (from 0.3)
                if confidence >= 0.2:
                    items.append({
                        'title': title,
                        'price': price,
                        'link': link,
                        'confidence': confidence,
                        'matched_keywords': matched_keywords
                    })
                    logging.info("Item ACCEPTED")
                else:
                    logging.info("Item REJECTED - Low confidence")
                
            except Exception as e:
                logging.error(f"Error processing item: {str(e)}")
                continue
        
        return items 

    def scrape_item_details(self, item_url: str) -> Optional[Dict[str, Any]]:
        """Scrape details from an item's detail page."""
        logger.info(f"STARTED: scrape_item_details() for URL: {item_url}")
        max_retries = 3
        base_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                # Clear cookies before loading to avoid stale sessions
                logger.info("Clearing cookies...")
                self.driver.delete_all_cookies()
                
                # Set page load timeout
                logger.info("Setting page load timeout to 30 seconds...")
                self.driver.set_page_load_timeout(30)
                
                # Load the page
                logger.info(f"Loading page: {item_url}")
                self.driver.get(item_url)
                
                # Handle cookie popup if present
                try:
                    logger.info("Checking for cookie popup...")
                    cookie_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "div.cookiePolicyPopup__buttonWrapper button.accept_cookie"))
                    )
                    logger.info("Found cookie popup, clicking accept...")
                    cookie_button.click()
                    time.sleep(1)  # Short wait for popup to disappear
                except TimeoutException:
                    logger.info("No cookie popup found or already handled")
                
                # Wait for the main item description section - this is the most reliable indicator
                try:
                    logger.info("Waiting for item description section...")
                    description_selector = "section#auction_item_description"
                    description_element = WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, description_selector))
                    )
                    logger.info("Found item description section")
                except TimeoutException:
                    logger.warning(f"Timeout waiting for item description section on attempt {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.info(f"Retrying in {delay} seconds...")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error("Failed to find item description section after all retries")
                        self.save_debug_info(item_url.split('/')[-1], "description_timeout", self.driver.page_source)
                        return None
                
                # Extract Yahoo Auction ID and URL
                yahoo_id = None
                yahoo_url = None
                try:
                    logger.info("Extracting Yahoo Auction ID and URL...")
                    # First try to get ID from URL
                    yahoo_id_match = re.search(r'/([a-z]\d+)(?:\?|$)', item_url)
                    if yahoo_id_match:
                        yahoo_id = yahoo_id_match.group(1)
                        yahoo_url = f"https://page.auctions.yahoo.co.jp/jp/auction/{yahoo_id}"
                        logger.info(f"Found Yahoo ID from URL: {yahoo_id}")
                    
                    # Then try to get URL from the "View on original site" link
                    logger.info("Looking for 'View on original site' link...")
                    original_site_link = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.detail_to_shopping a[target='_blank']"))
                    )
                    yahoo_url = original_site_link.get_attribute('href')
                    if not yahoo_id and yahoo_url:
                        yahoo_id = yahoo_url.split('/')[-1]
                        logger.info(f"Found Yahoo ID from link: {yahoo_id}")
                except Exception as e:
                    logger.warning(f"Could not find Yahoo Auction link: {str(e)}")
                
                # Extract item condition
                condition = None
                try:
                    logger.info("Looking for item condition...")
                    condition_element = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//li[em[contains(text(), 'Item Condition')]]/span"))
                    )
                    condition = condition_element.text.strip()
                    logger.info(f"Found item condition: {condition}")
                except Exception as e:
                    logger.warning(f"Could not find item condition: {str(e)}")
                
                # Extract description
                description = None
                try:
                    logger.info("Extracting item description...")
                    description = description_element.text.strip()
                    logger.info(f"Found item description (first 100 chars): {description[:100]}...")
                except Exception as e:
                    logger.warning(f"Could not extract item description: {str(e)}")
                
                # Extract main image URL
                main_image_url = None
                try:
                    logger.info("Looking for main image...")
                    main_image = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "#itemPhoto_sec .flexslider .slides li:first-child img"))
                    )
                    main_image_url = main_image.get_attribute('data-src') or main_image.get_attribute('src')
                    logger.info(f"Found main image URL: {main_image_url}")
                except Exception as e:
                    logger.warning(f"Could not find main image: {str(e)}")
                
                # Extract additional images
                additional_images = []
                try:
                    logger.info("Looking for additional images...")
                    image_elements = self.driver.find_elements(By.CSS_SELECTOR, "#itemPhoto_sec .flexslider .slides li:not(:first-child) img")
                    for img in image_elements:
                        img_url = img.get_attribute('data-src') or img.get_attribute('src')
                        if img_url:
                            additional_images.append(img_url)
                    logger.info(f"Found {len(additional_images)} additional images")
                except Exception as e:
                    logger.warning(f"Could not find additional images: {str(e)}")
                
                # Validate that we have essential data
                if not all([yahoo_id, yahoo_url, condition, description, main_image_url]):
                    missing = []
                    if not yahoo_id: missing.append("yahoo_id")
                    if not yahoo_url: missing.append("yahoo_url")
                    if not condition: missing.append("condition")
                    if not description: missing.append("description")
                    if not main_image_url: missing.append("main_image_url")
                    logger.warning(f"Missing essential data: {', '.join(missing)}")
                    self.save_debug_info(item_url.split('/')[-1], "missing_data", self.driver.page_source)
                    return None
                
                logger.info("Successfully scraped all item details")
                return {
                    'yahoo_id': yahoo_id,
                    'yahoo_url': yahoo_url,
                    'condition': condition,
                    'description': description,
                    'main_image_url': main_image_url,
                    'additional_images': additional_images
                }
                
            except Exception as e:
                logger.error(f"Error scraping item detail page {item_url} on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    logger.error("Failed after all retries")
                    self.save_debug_info(item_url.split('/')[-1], "error", self.driver.page_source)
                    return None
        
        return None 