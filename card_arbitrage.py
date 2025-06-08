import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth
import requests
from bs4 import BeautifulSoup
from googletrans import Translator
from dotenv import load_dotenv
import re
import time
from dataclasses import dataclass
from decimal import Decimal

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('arbitrage.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

@dataclass
class CardListing:
    """Data class to store card listing information."""
    title: str
    title_en: str
    price_yen: Decimal
    price_usd: Decimal
    condition: str
    image_url: str
    listing_url: str
    description: str
    description_en: str
    card_id: Optional[str] = None
    set_code: Optional[str] = None
    ebay_prices: Optional[Dict[str, List[Decimal]]] = None
    potential_profit: Optional[Decimal] = None
    profit_margin: Optional[float] = None

class CardArbitrageTool:
    def __init__(self, output_dir: str = "arbitrage_results"):
        """Initialize the arbitrage tool."""
        self.output_dir = output_dir
        self.driver = None
        self.translator = Translator()
        self.setup_driver()
        os.makedirs(output_dir, exist_ok=True)
        
    def setup_driver(self):
        """Set up Chrome WebDriver with stealth mode."""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
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

    def translate_text(self, text: str) -> str:
        """Translate Japanese text to English."""
        try:
            if not text:
                return ""
            result = self.translator.translate(text, src='ja', dest='en')
            return result.text
        except Exception as e:
            logger.error(f"Translation error: {str(e)}")
            return text

    def extract_card_id(self, title: str) -> Optional[str]:
        """Extract card ID from title."""
        # Common patterns for card IDs
        patterns = [
            r'([A-Z]{2,4}-\d{3})',  # Standard format like "LOB-001"
            r'(\d{3})',             # Just the number
            r'No\.(\d+)',           # Japanese format
            r'番号(\d+)'            # Japanese format
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title)
            if match:
                return match.group(1)
        return None

    def get_ebay_prices(self, card_id: str) -> Dict[str, List[Decimal]]:
        """Get eBay sold prices for a card."""
        try:
            # Construct eBay search URL
            search_url = f"https://www.ebay.com/sch/i.html?_nkw={card_id}&_sacat=0&LH_Sold=1&LH_Complete=1"
            
            # Make request with headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(search_url, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch eBay data: {response.status_code}")
                return {'raw': [], 'psa': []}
            
            # Parse the response
            soup = BeautifulSoup(response.text, 'html.parser')
            prices = {'raw': [], 'psa': []}
            
            # Find all sold items
            items = soup.find_all('div', class_='s-item__info')
            for item in items:
                try:
                    # Get price
                    price_elem = item.find('span', class_='s-item__price')
                    if not price_elem:
                        continue
                    
                    price_text = price_elem.text.strip()
                    price = Decimal(re.sub(r'[^\d.]', '', price_text))
                    
                    # Check if it's a PSA graded card
                    title_elem = item.find('div', class_='s-item__title')
                    if title_elem and 'PSA' in title_elem.text:
                        prices['psa'].append(price)
                    else:
                        prices['raw'].append(price)
                        
                except Exception as e:
                    logger.debug(f"Error parsing eBay item: {str(e)}")
                    continue
            
            return prices
            
        except Exception as e:
            logger.error(f"Error fetching eBay prices: {str(e)}")
            return {'raw': [], 'psa': []}

    def calculate_profit(self, price_yen: Decimal, ebay_prices: Dict[str, List[Decimal]]) -> tuple:
        """Calculate potential profit and margin."""
        try:
            # Convert yen to USD (using a simple rate, should be updated regularly)
            yen_to_usd = Decimal('0.0067')  # Update this rate regularly
            price_usd = price_yen * yen_to_usd
            
            # Calculate average eBay prices
            avg_raw = sum(ebay_prices['raw']) / len(ebay_prices['raw']) if ebay_prices['raw'] else Decimal('0')
            avg_psa = sum(ebay_prices['psa']) / len(ebay_prices['psa']) if ebay_prices['psa'] else Decimal('0')
            
            # Use the higher average price
            target_price = max(avg_raw, avg_psa)
            
            # Calculate profit (assuming 15% eBay fees and 5% shipping)
            fees = target_price * Decimal('0.20')
            profit = target_price - price_usd - fees
            margin = (profit / price_usd) * 100 if price_usd > 0 else 0
            
            return profit, margin
            
        except Exception as e:
            logger.error(f"Error calculating profit: {str(e)}")
            return Decimal('0'), 0.0

    def scrape_buyee_listings(self, keyword: str, max_results: int = 20) -> List[CardListing]:
        """Scrape card listings from Buyee."""
        listings = []
        try:
            # Construct search URL
            search_url = f"https://buyee.jp/item/search/query/{keyword}"
            self.driver.get(search_url)
            
            # Wait for results to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "li.itemCard"))
            )
            
            # Get item cards
            items = self.driver.find_elements(By.CSS_SELECTOR, "li.itemCard")[:max_results]
            
            for item in items:
                try:
                    # Extract basic information
                    title = item.find_element(By.CSS_SELECTOR, "h3.itemCard__itemName").text.strip()
                    price_text = item.find_element(By.CSS_SELECTOR, "div.itemCard__price").text.strip()
                    price_yen = Decimal(re.sub(r'[^\d.]', '', price_text))
                    image_url = item.find_element(By.CSS_SELECTOR, "img").get_attribute("src")
                    listing_url = item.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
                    
                    # Get condition if available
                    try:
                        condition = item.find_element(By.CSS_SELECTOR, "div.itemCard__condition").text.strip()
                    except NoSuchElementException:
                        condition = "Unknown"
                    
                    # Translate title
                    title_en = self.translate_text(title)
                    
                    # Extract card ID
                    card_id = self.extract_card_id(title)
                    
                    # Create listing object
                    listing = CardListing(
                        title=title,
                        title_en=title_en,
                        price_yen=price_yen,
                        price_usd=price_yen * Decimal('0.0067'),  # Convert to USD
                        condition=condition,
                        image_url=image_url,
                        listing_url=listing_url,
                        description="",  # Will be filled later
                        description_en="",  # Will be filled later
                        card_id=card_id
                    )
                    
                    listings.append(listing)
                    
                except Exception as e:
                    logger.error(f"Error processing item: {str(e)}")
                    continue
            
            return listings
            
        except Exception as e:
            logger.error(f"Error scraping Buyee listings: {str(e)}")
            return []

    def analyze_listings(self, listings: List[CardListing]) -> List[CardListing]:
        """Analyze listings and calculate potential profits."""
        analyzed_listings = []
        
        for listing in listings:
            try:
                if listing.card_id:
                    # Get eBay prices
                    ebay_prices = self.get_ebay_prices(listing.card_id)
                    listing.ebay_prices = ebay_prices
                    
                    # Calculate profit
                    profit, margin = self.calculate_profit(listing.price_yen, ebay_prices)
                    listing.potential_profit = profit
                    listing.profit_margin = margin
                
                analyzed_listings.append(listing)
                
            except Exception as e:
                logger.error(f"Error analyzing listing: {str(e)}")
                continue
        
        return analyzed_listings

    def save_results(self, listings: List[CardListing], keyword: str):
        """Save results to CSV and JSON files."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Convert to DataFrame
            data = []
            for listing in listings:
                data.append({
                    'title': listing.title,
                    'title_en': listing.title_en,
                    'price_yen': float(listing.price_yen),
                    'price_usd': float(listing.price_usd),
                    'condition': listing.condition,
                    'image_url': listing.image_url,
                    'listing_url': listing.listing_url,
                    'card_id': listing.card_id,
                    'ebay_raw_prices': [float(p) for p in listing.ebay_prices['raw']] if listing.ebay_prices else [],
                    'ebay_psa_prices': [float(p) for p in listing.ebay_prices['psa']] if listing.ebay_prices else [],
                    'potential_profit': float(listing.potential_profit) if listing.potential_profit else None,
                    'profit_margin': listing.profit_margin
                })
            
            df = pd.DataFrame(data)
            
            # Save as CSV
            csv_path = os.path.join(self.output_dir, f"arbitrage_{keyword}_{timestamp}.csv")
            df.to_csv(csv_path, index=False, encoding='utf-8')
            logger.info(f"Saved results to {csv_path}")
            
            # Save as JSON
            json_path = os.path.join(self.output_dir, f"arbitrage_{keyword}_{timestamp}.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved results to {json_path}")
            
        except Exception as e:
            logger.error(f"Error saving results: {str(e)}")

    def run(self, keyword: str, max_results: int = 20):
        """Run the arbitrage analysis."""
        try:
            logger.info(f"Starting arbitrage analysis for: {keyword}")
            
            # Scrape listings
            listings = self.scrape_buyee_listings(keyword, max_results)
            logger.info(f"Found {len(listings)} listings")
            
            # Analyze listings
            analyzed_listings = self.analyze_listings(listings)
            logger.info(f"Analyzed {len(analyzed_listings)} listings")
            
            # Save results
            self.save_results(analyzed_listings, keyword)
            
            return analyzed_listings
            
        except Exception as e:
            logger.error(f"Error in arbitrage analysis: {str(e)}")
            return []

    def cleanup(self):
        """Clean up resources."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error closing WebDriver: {str(e)}")

def main():
    # Example usage
    tool = CardArbitrageTool()
    try:
        results = tool.run("遊戯王 アジア", max_results=20)
        
        # Print summary
        print("\nArbitrage Analysis Results:")
        print("=" * 80)
        for listing in sorted(results, key=lambda x: x.profit_margin if x.profit_margin else 0, reverse=True):
            print(f"\nTitle: {listing.title_en}")
            print(f"Price: ¥{listing.price_yen:,.0f} (${listing.price_usd:.2f})")
            print(f"Condition: {listing.condition}")
            print(f"Potential Profit: ${listing.potential_profit:.2f}" if listing.potential_profit else "No profit data")
            print(f"Profit Margin: {listing.profit_margin:.1f}%" if listing.profit_margin else "No margin data")
            print("-" * 40)
            
    finally:
        tool.cleanup()

if __name__ == "__main__":
    main() 