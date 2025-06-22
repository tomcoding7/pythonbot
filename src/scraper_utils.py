import requests
from bs4 import BeautifulSoup
import logging
import time
import random
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import quote
import statistics
import re
import os
import google.generativeai as genai
from openai import OpenAI

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RequestHandler:
    """Handles HTTP requests with retry logic and bot detection."""
    
    def __init__(self):
        """Initialize the RequestHandler with default headers and retry settings."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        })
        self.retry_delays = [1, 2, 5, 10, 30]  # Exponential backoff delays
        self.max_retries = 3
        self.timeout = 10
        
    def get_page(self, url: str, max_retries: int = None, timeout: int = None) -> Optional[str]:
        """
        Make a request with retry logic and bot detection.
        
        Args:
            url (str): URL to fetch
            max_retries (int): Maximum number of retries
            timeout (int): Request timeout in seconds
            
        Returns:
            Optional[str]: Page content or None if failed
        """
        retries = max_retries if max_retries is not None else self.max_retries
        timeout = timeout if timeout is not None else self.timeout
        
        for retry in range(retries):
            try:
                # Add random delay between requests
                time.sleep(random.uniform(3, 7))
                
                # Make request with timeout
                response = self.session.get(url, timeout=timeout)
                
                # Handle common error cases
                if response.status_code == 404:
                    logger.warning(f"Item not found (404): {url}")
                    return None
                
                if response.status_code in [403, 429]:
                    logger.warning(f"Bot detection triggered (HTTP {response.status_code})")
                    if retry < retries - 1:
                        delay = self.retry_delays[min(retry, len(self.retry_delays) - 1)]
                        logger.info(f"Waiting {delay} seconds before retry...")
                        time.sleep(delay)
                        continue
                    return None
                
                # Check for Japanese-specific error messages
                if 'このサービスは日本国内からのみご利用いただけます' in response.text:
                    logger.error("Access denied. This service is only available from Japan.")
                    return None
                
                if 'アクセスが集中' in response.text or '一時的なアクセス制限' in response.text:
                    logger.warning("Bot challenge page detected")
                    if retry < retries - 1:
                        delay = self.retry_delays[min(retry, len(self.retry_delays) - 1)]
                        logger.info(f"Waiting {delay} seconds before retry...")
                        time.sleep(delay)
                        continue
                    return None
                
                # Raise for any other HTTP errors
                response.raise_for_status()
                
                # Log successful request
                logger.info(f"Successfully fetched page: {url}")
                return response.text
                
            except requests.RequestException as e:
                logger.error(f"Error fetching {url}: {str(e)}")
                if retry < retries - 1:
                    delay = self.retry_delays[min(retry, len(self.retry_delays) - 1)]
                    logger.info(f"Waiting {delay} seconds before retry...")
                    time.sleep(delay)
                else:
                    logger.error("Max retries reached")
                    return None
        return None

class CardInfoExtractor:
    """Extracts and normalizes card information from titles."""
    
    def __init__(self):
        # Initialize OpenAI
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Common set codes and their full names
        self.set_patterns = {
            'SDK': 'Starter Deck Kaiba',
            'LOB': 'Legend of Blue Eyes White Dragon',
            'MRD': 'Metal Raiders',
            'SRL': 'Starter Deck Yugi',
            'PSV': 'Pharaoh\'s Servant',
        }
    
    def translate_to_english(self, japanese_text: str) -> str:
        """Translate Japanese card name to English using OpenAI."""
        try:
            prompt = f"""Translate this Yu-Gi-Oh card name from Japanese to English. 
            Only return the English name, nothing else. If it's a set name or condition, ignore it.
            Japanese text: {japanese_text}"""
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a Yu-Gi-Oh card name translator. Only return the English name, no explanations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3  # Lower temperature for more consistent translations
            )
            
            english_name = response.choices[0].message.content.strip()
            logger.info(f"Translated '{japanese_text}' to '{english_name}'")
            return english_name
            
        except Exception as e:
            logger.error(f"Error translating card name: {str(e)}")
            return japanese_text
    
    def extract_card_info(self, title: str) -> Tuple[str, Optional[str]]:
        """Extract card name and set from title."""
        try:
            # Try to find set code first
            set_code = None
            for code in self.set_patterns.keys():
                if code in title.upper():
                    set_code = code
                    break
            
            # Extract card name
            card_name = title
            
            # Remove common words and set codes
            common_words = [
                '遊戯王', 'Yu-Gi-Oh', 'カード', 'card', '1st', 'edition', 'limited', 
                'まとめ', 'レア', 'rare', 'セット', 'set', 'パック', 'pack',
                '新品', '未使用', '中古', '使用済み', 'プレイ済み'
            ]
            
            # Remove common words
            for word in common_words:
                card_name = card_name.replace(word, '').strip()
            
            # Remove set code if found
            if set_code:
                card_name = card_name.replace(set_code, '').strip()
            
            # Remove numbers at the end (like "864" in "まとめ 864")
            card_name = re.sub(r'\s*\d+$', '', card_name).strip()
            
            # If the name is too short or just numbers, try to extract from description
            if len(card_name) < 3 or card_name.isdigit():
                logger.warning(f"Card name too short or invalid: {card_name}")
                return None, set_code
            
            # Translate to English if it contains Japanese characters
            if any(ord(c) > 127 for c in card_name):
                card_name = self.translate_to_english(card_name)
            
            return card_name, set_code
            
        except Exception as e:
            logger.error(f"Error extracting card info: {str(e)}")
            return None, None

class PriceAnalyzer:
    """Analyzes card prices from 130point.com."""
    
    def __init__(self):
        self.request_handler = RequestHandler()
    
    def get_130point_prices(self, card_name: str, set_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get price data from 130point.com."""
        try:
            search_term = f"{card_name} {set_code}" if set_code else card_name
            url = f"https://www.130point.com/sales/search/?q={quote(search_term)}"
            
            html = self.request_handler.get_page(url)
            if not html:
                return None
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract prices
            prices = []
            for price_elem in soup.select('span.price'):
                try:
                    price_text = price_elem.text.strip()
                    price = float(re.sub(r'[^\d.]', '', price_text))
                    prices.append(price)
                except (ValueError, AttributeError):
                    continue
            
            if not prices:
                return None
            
            # Calculate statistics
            return {
                'min_price': min(prices),
                'max_price': max(prices),
                'avg_price': statistics.mean(prices),
                'median_price': statistics.median(prices),
                'price_count': len(prices)
            }
            
        except Exception as e:
            logger.error(f"Error getting 130point prices: {str(e)}")
            return None

class ConditionAnalyzer:
    """Analyzes card condition from text and images."""
    
    def __init__(self):
        self.condition_keywords = {
            'mint': [
                'mint', 'mint condition', 'mint state',
                '未使用', '新品', '美品', '完全美品',
                'psa 10', 'bgs 10', 'psa 9.5', 'bgs 9.5'
            ],
            'near_mint': [
                'near mint', 'nm', 'nm-mt', 'near mint condition',
                'ほぼ新品', 'ほぼ未使用', '極美品', '極上美品'
            ],
            'excellent': [
                'excellent', 'ex', 'ex-mt', 'excellent condition',
                '美品', '上美品', '優良品'
            ],
            'very_good': [
                'very good', 'vg', 'vg-ex', 'very good condition',
                '良品', '良好品'
            ],
            'good': [
                'good', 'g', 'good condition',
                '並品', '普通品'
            ],
            'light_played': [
                'light played', 'lp', 'lightly played',
                'やや傷あり', '軽い傷あり'
            ],
            'played': [
                'played', 'p', 'played condition',
                '傷あり', '使用感あり'
            ],
            'poor': [
                'poor', 'damaged', 'heavily played', 'hp',
                '傷みあり', '破損あり', '状態悪い'
            ]
        }
    
    def analyze_condition(self, title: str, description: str, image_analysis: Optional[Dict] = None) -> Dict[str, Any]:
        """Analyze card condition from text and image analysis."""
        result = {
            'condition': None,
            'confidence': 0.0,
            'indicators': [],
            'warnings': []
        }
        
        # Analyze text
        text = f"{title} {description}".lower()
        found_conditions = []
        
        for condition, keywords in self.condition_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text:
                    found_conditions.append(condition)
                    result['indicators'].append(f"Found '{keyword}' in text")
        
        if found_conditions:
            # Use the best condition found
            condition_order = ['mint', 'near_mint', 'excellent', 'very_good', 'good', 'light_played', 'played', 'poor']
            best_condition = min(found_conditions, key=lambda x: condition_order.index(x))
            result['condition'] = best_condition
            result['confidence'] += 0.6  # Text analysis provides good confidence
        
        # Incorporate image analysis if available
        if image_analysis:
            if image_analysis.get('is_damaged'):
                result['warnings'].append("Image analysis indicates damage")
                if result['condition'] in ['mint', 'near_mint']:
                    result['confidence'] -= 0.3  # Reduce confidence if image contradicts text
            else:
                result['confidence'] += 0.2  # Image analysis supports good condition
        
        # Normalize confidence
        result['confidence'] = min(result['confidence'], 1.0)
        
        return result 