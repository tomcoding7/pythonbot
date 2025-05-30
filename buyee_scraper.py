import requests
from bs4 import BeautifulSoup
import json
import time
import random
from datetime import datetime
import logging
from urllib.parse import urljoin, quote
from search_terms import SEARCH_TERMS
import os
from PIL import Image
import io
import base64
import openai
import google.generativeai as genai
from dotenv import load_dotenv
import re
import socket
import requests.exceptions
import urllib3

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class VPNChecker:
    def __init__(self):
        self.japan_ips = set()
        self.load_japan_ips()
    
    def load_japan_ips(self):
        """Load list of known Japanese IP ranges."""
        try:
            # You can expand this list with more Japanese IP ranges
            self.japan_ips = {
                '202.216.0.0/16',  # Example Japanese IP range
                '202.217.0.0/16',
                '202.218.0.0/16',
                '202.219.0.0/16',
                '202.220.0.0/16',
                '202.221.0.0/16',
                '202.222.0.0/16',
                '202.223.0.0/16',
            }
        except Exception as e:
            logger.warning(f"Error loading Japan IP ranges: {str(e)}")
    
    def check_ip_location(self):
        """Check if current IP is in Japan."""
        try:
            # Try multiple IP geolocation services
            services = [
                'https://ipapi.co/json/',
                'https://ipinfo.io/json',
                'https://api.ip.sb/geoip'
            ]
            
            for service in services:
                try:
                    response = requests.get(service, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        country = data.get('country', '').upper()
                        if country == 'JP':
                            return True
                except:
                    continue
            
            return False
        except Exception as e:
            logger.warning(f"Error checking IP location: {str(e)}")
            return False

class ImageAnalyzer:
    def __init__(self):
        # Initialize OpenAI client
        openai.api_key = os.getenv('OPENAI_API_KEY')
        
        # Initialize Gemini
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        self.gemini_model = genai.GenerativeModel('gemini-pro-vision')
        
        # Create a session for image downloads
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Referer': 'https://buyee.jp/',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'same-origin',
            'DNT': '1',
        })
        
    def get_image(self, image_url):
        """Download image through Buyee's proxy with proper headers and session handling."""
        try:
            # Ensure we're using Buyee's proxy
            if not image_url.startswith('https://buyee.jp'):
                logger.warning(f"Non-Buyee image URL detected: {image_url}")
                return None
            
            # Try multiple size variants
            size_variants = [
                image_url,
                image_url.replace('/item/image/', '/item/image/large/'),
                image_url.replace('/item/image/', '/item/image/medium/'),
                image_url.replace('/item/image/', '/item/image/small/')
            ]
            
            for url in size_variants:
                try:
                    logger.info(f"Attempting to download image from Buyee proxy: {url}")
                    response = self.session.get(url, timeout=10)
                    if response.status_code == 200:
                        logger.info(f"Successfully downloaded image from {url}")
                        return response.content
                    else:
                        logger.warning(f"Failed to download image from {url}: {response.status_code}")
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Request error for {url}: {str(e)}")
                    continue
                except Exception as e:
                    logger.warning(f"Unexpected error for {url}: {str(e)}")
                    continue
            
            logger.error("Failed to download image from any Buyee proxy URL")
            return None
            
        except Exception as e:
            logger.error(f"Error in get_image: {str(e)}")
            return None

    def analyze_with_openai(self, image_url):
        """Analyze image using OpenAI Vision API with robust error handling and retries."""
        max_retries = 3
        retry_delay = 5  # seconds
        
        # Generate multiple URL variants to try
        url_variants = [
            image_url,
            image_url.replace('i-img900x1200', 'i-img1200x900'),
            image_url.replace('i-img900x1200', 'i-img600x800'),
            image_url.replace('i-img900x1200', 'i-img800x600'),
            image_url.replace('i-img900x1200', 'i-img400x600'),
            image_url.replace('i-img900x1200', 'i-img600x400')
        ]
        
        logger.info(f"Starting image analysis for URL: {image_url}")
        logger.info(f"Will try {len(url_variants)} URL variants")
        
        for retry in range(max_retries):
            try:
                # Try each URL variant
                for variant_url in url_variants:
                    try:
                        logger.info(f"Attempting to download image from: {variant_url}")
                        image_content = self.get_image(variant_url)
                        
                        if not image_content:
                            logger.warning(f"Failed to download image from {variant_url}")
                            continue
                            
                        # Convert image to base64
                        try:
                            logger.info("Converting image to base64")
                            image = Image.open(io.BytesIO(image_content))
                            buffered = io.BytesIO()
                            image.save(buffered, format="JPEG")
                            img_str = base64.b64encode(buffered.getvalue()).decode()
                            logger.info("Successfully converted image to base64")
                        except Exception as e:
                            logger.error(f"Error converting image to base64: {str(e)}")
                            continue
                        
                        # Call OpenAI Vision API
                        logger.info("Sending request to OpenAI Vision API")
                        response = openai.ChatCompletion.create(
                            model="gpt-4-vision-preview",
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": "Analyze this Yu-Gi-Oh card image. Describe its condition, any visible damage, wear, or defects. Also identify if it's a rare card and its approximate value. Be specific about the card's physical condition."
                                        },
                                        {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:image/jpeg;base64,{img_str}"
                                            }
                                        }
                                    ]
                                }
                            ],
                            max_tokens=500
                        )
                        
                        analysis = response.choices[0].message.content
                        logger.info("Successfully received analysis from OpenAI")
                        return analysis
                        
                    except requests.exceptions.SSLError as e:
                        logger.warning(f"SSL Error with URL {variant_url}: {str(e)}")
                        continue
                    except requests.exceptions.RequestException as e:
                        logger.warning(f"Request Error with URL {variant_url}: {str(e)}")
                        continue
                    except Exception as e:
                        logger.error(f"Unexpected error with URL {variant_url}: {str(e)}")
                        continue
                
                # If we get here, all URL variants failed
                if retry < max_retries - 1:
                    logger.warning(f"All URL variants failed, retrying in {retry_delay} seconds (attempt {retry + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error("All URL variants failed after all retries")
                    raise Exception("Failed to analyze image after trying all URL variants and retries")
                    
            except Exception as e:
                if retry < max_retries - 1:
                    logger.warning(f"Error during analysis attempt {retry + 1}: {str(e)}")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(f"Final error after all retries: {str(e)}")
                    raise Exception(f"Failed to analyze image: {str(e)}")
        
        # This should never be reached due to the raise statements above
        raise Exception("Unexpected error in image analysis")

    def analyze_with_gemini(self, image_url):
        """Analyze image using Google's Gemini Vision API."""
        try:
            # Download image with proper headers
            image_content = self.get_image(image_url)
            if not image_content:
                logger.warning("Failed to download image for Gemini analysis")
                return None
                
            # Convert image to PIL Image
            image = Image.open(io.BytesIO(image_content))
            
            # Call Gemini Vision API
            response = self.gemini_model.generate_content([
                "Analyze this Yu-Gi-Oh card image. Describe its condition, any visible damage, wear, or defects. Also identify if it's a rare card and its approximate value. Be specific about the card's physical condition.",
                image
            ])
            
            return response.text
            
        except requests.exceptions.SSLError as e:
            logger.warning(f"SSL Error with Gemini image analysis: {str(e)}")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request Error with Gemini image analysis: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error analyzing image with Gemini: {str(e)}")
            return None

class BuyeeScraper:
    def __init__(self):
        self.base_url = "https://buyee.jp"
        self.yahoo_base_url = "https://auctions.yahoo.co.jp"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'DNT': '1',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.image_analyzer = ImageAnalyzer()
        self.vpn_checker = VPNChecker()
        
    def check_vpn_requirement(self):
        """Check if VPN is required and warn user if needed."""
        if not self.vpn_checker.check_ip_location():
            logger.warning("""
WARNING: It appears you are not accessing from a Japanese IP address.
Yahoo Auctions Japan is region-locked and requires a Japanese IP address to access.
Some features may not work correctly without a Japanese IP address.
Consider using a VPN with a Japanese server for better results.
            """)
        return True

    def get_page(self, url):
        """Make a request to the given URL with error handling and delay."""
        try:
            # Add random delay between requests (3-7 seconds)
            time.sleep(random.uniform(3, 7))
            
            # First visit the homepage to get cookies
            if not hasattr(self, 'initialized'):
                logger.info("Initializing session with homepage visit...")
                self.session.get(self.base_url, timeout=10)
                self.initialized = True
                time.sleep(random.uniform(2, 4))
            
            # Make the actual request
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Check for region-locked content
            if 'このサービスは日本国内からのみご利用いただけます' in response.text:
                logger.error("""
ERROR: Access denied. This service is only available from Japan.
Please connect to a Japanese VPN server and try again.
                """)
                return None
            
            # Check for bot detection
            if 'アクセスが集中' in response.text or '一時的なアクセス制限' in response.text:
                logger.warning("Bot detection triggered. Waiting longer before next request...")
                time.sleep(random.uniform(10, 15))
                return None
            
            # Log the response for debugging
            logger.info(f"Response status code: {response.status_code}")
            logger.info(f"Response URL: {response.url}")
            
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            # If we get a 403, try Yahoo Auctions directly
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 403:
                logger.warning("Received 403 error from Buyee, trying Yahoo Auctions directly...")
                try:
                    # Convert Buyee URL to Yahoo Auctions URL
                    yahoo_url = url.replace(self.base_url, self.yahoo_base_url)
                    response = self.session.get(yahoo_url, timeout=10)
                    response.raise_for_status()
                    return response.text
                except:
                    logger.error("Failed to access Yahoo Auctions directly")
                    time.sleep(random.uniform(15, 20))
            return None

    def extract_ko_data(self, html_content):
        """Extract data from Knockout.js data-bind attributes."""
        try:
            # Find the data-bind attribute containing the items
            pattern = r'<!-- ko ecView : \$root\.ec\.getViewHandler\(\{"impressions":\{"items":(\[.*?\])\}\}\) -->'
            match = re.search(pattern, html_content, re.DOTALL)
            
            if match:
                items_json = match.group(1)
                items = json.loads(items_json)
                return items
            return []
        except Exception as e:
            logger.error(f"Error extracting Knockout.js data: {str(e)}")
            return []

    def get_buyee_image_urls(self, item_id, service_type):
        """Generate Buyee image URLs for an item, including magnified versions."""
        base_path = f"{self.base_url}/item/image"
        
        # Different URL patterns based on service type
        if 'Yahoo' in service_type:
            return [
                f"{base_path}/yahoo/{item_id}",
                f"{base_path}/yahoo/{item_id}/large",
                f"{base_path}/yahoo/{item_id}/medium",
                f"{base_path}/yahoo/{item_id}/small",
                f"{base_path}/yahoo/{item_id}/magnify",  # Magnified version
                f"{base_path}/yahoo/{item_id}/original"   # Original size
            ]
        elif 'Rakuten' in service_type:
            return [
                f"{base_path}/rakuten/{item_id}",
                f"{base_path}/rakuten/{item_id}/large",
                f"{base_path}/rakuten/{item_id}/medium",
                f"{base_path}/rakuten/{item_id}/small",
                f"{base_path}/rakuten/{item_id}/magnify",
                f"{base_path}/rakuten/{item_id}/original"
            ]
        else:
            return [
                f"{base_path}/{item_id}",
                f"{base_path}/{item_id}/large",
                f"{base_path}/{item_id}/medium",
                f"{base_path}/{item_id}/small",
                f"{base_path}/{item_id}/magnify",
                f"{base_path}/{item_id}/original"
            ]

    def parse_listing(self, item_data):
        """Parse individual auction listing data from Knockout.js data."""
        try:
            title = item_data.get('name', '')
            item_id = item_data.get('id', '')
            price = item_data.get('price', 0)
            seller_id = item_data.get('partnerSellerId', '')
            category = item_data.get('category', '')
            service_type = item_data.get('serviceType', '')
            
            # Extract condition information from title
            condition_info = {
                'is_new': False,
                'is_used': False,
                'is_unopened': False,
                'is_played': False,
                'is_scratched': False,
                'is_damaged': False,
                'condition_notes': [],
                'condition_summary': ''  # Added for quick reference
            }
            
            # Common condition indicators in both English and Japanese
            condition_indicators = {
                'new': [
                    # Japanese
                    '新品', '新規', '未使用', '未開封', '新規未開封', '新品未開封',
                    # English
                    'new', 'unused', 'unopened', 'sealed', 'mint'
                ],
                'used': [
                    # Japanese
                    '中古', '使用済み', '使用感あり', '使用済', '使用後',
                    # English
                    'used', 'secondhand', 'pre-owned'
                ],
                'unopened': [
                    # Japanese
                    '未開封', 'シール付き', 'パッケージ付き', '封入済み',
                    # English
                    'unopened', 'sealed', 'packaged', 'in package'
                ],
                'played': [
                    # Japanese
                    'プレイ済み', '使用済み', '遊んだ', 'プレイ後', '使用後',
                    # English
                    'played', 'used in play', 'played with'
                ],
                'scratched': [
                    # Japanese
                    '傷あり', 'キズあり', '擦れあり', 'スレあり', 'スレ傷', '擦れ傷',
                    # English
                    'scratched', 'scuff', 'wear', 'surface damage'
                ],
                'damage': [
                    # Japanese
                    '傷あり', '汚れあり', '破れあり', '折れあり', 'シミあり',
                    '折れ', '破れ', '汚れ', 'シミ', '変色', '日焼け',
                    'カード傷', 'カード折れ', 'カード汚れ', 'カードシミ',
                    # English
                    'damaged', 'tear', 'stain', 'bent', 'fold', 'crease',
                    'discolored', 'sun damage', 'water damage'
                ],
                'good': [
                    # Japanese
                    '状態良好', '美品', '綺麗', '良品', '状態良', '状態◎',
                    # English
                    'good condition', 'excellent', 'like new', 'near mint'
                ],
                'fair': [
                    # Japanese
                    '並品', '普通', '状態普通', '状態△',
                    # English
                    'fair condition', 'average', 'normal wear'
                ],
                'poor': [
                    # Japanese
                    '状態悪い', '傷みあり', '状態×', '状態✕',
                    # English
                    'poor condition', 'damaged', 'heavily used'
                ],
                'card_specific': [
                    # Japanese
                    'カード傷', 'カード折れ', 'カード汚れ', 'カードシミ',
                    'カード擦れ', 'カードスレ', 'カード変色',
                    'カード状態良好', 'カード状態普通', 'カード状態悪い',
                    # English
                    'card damage', 'card wear', 'card scratch',
                    'card condition', 'card quality'
                ]
            }
            
            # Check title for condition indicators (case-insensitive)
            title_lower = title.lower()
            for condition_type, indicators in condition_indicators.items():
                for indicator in indicators:
                    if indicator.lower() in title_lower:
                        if condition_type in ['new', 'used', 'unopened', 'played', 'scratched', 'damaged']:
                            condition_info[f'is_{condition_type}'] = True
                        condition_info['condition_notes'].append(f"{condition_type}: {indicator}")
            
            # Generate condition summary
            condition_summary = []
            if condition_info['is_new']:
                condition_summary.append('New')
            if condition_info['is_used']:
                condition_summary.append('Used')
            if condition_info['is_unopened']:
                condition_summary.append('Unopened')
            if condition_info['is_played']:
                condition_summary.append('Played')
            if condition_info['is_scratched']:
                condition_summary.append('Scratched')
            if condition_info['is_damaged']:
                condition_summary.append('Damaged')
            
            # Add quality level if found
            for quality in ['good', 'fair', 'poor']:
                if any(indicator.lower() in title_lower for indicator in condition_indicators[quality]):
                    condition_summary.append(quality.capitalize())
                    break
            
            condition_info['condition_summary'] = ' | '.join(condition_summary) if condition_summary else 'Unknown'
            
            # Construct item URL based on service type
            if 'Yahoo' in service_type:
                item_url = f"{self.base_url}/item/yahoo/{item_id}"
            elif 'Rakuten' in service_type:
                item_url = f"{self.base_url}/item/rakuten/{item_id}"
            else:
                item_url = f"{self.base_url}/item/{item_id}"
            
            # Get image URLs through Buyee (optional)
            image_urls = []
            if 'imageUrl' in item_data and item_data['imageUrl'].startswith(self.base_url):
                image_urls.append(item_data['imageUrl'])
            
            # Add Buyee URLs
            buyee_urls = self.get_buyee_image_urls(item_id, service_type)
            image_urls.extend(buyee_urls)
            
            # Try to get a working image URL (optional)
            final_image_url = None
            if image_urls:
                for url in image_urls:
                    try:
                        response = self.session.head(url, timeout=5)
                        if response.status_code == 200:
                            final_image_url = url
                            break
                    except Exception as e:
                        continue
            
            # Image analysis is now optional
            image_analysis = None
            if final_image_url and os.getenv('ENABLE_IMAGE_ANALYSIS', 'false').lower() == 'true':
                try:
                    # Try OpenAI first
                    logger.info("Attempting image analysis with OpenAI...")
                    image_analysis = self.image_analyzer.analyze_with_openai(final_image_url)
                    
                    # If OpenAI fails, try Gemini
                    if not image_analysis:
                        logger.info("OpenAI analysis failed, attempting with Gemini...")
                        image_analysis = self.image_analyzer.analyze_with_gemini(final_image_url)
                except Exception as e:
                    logger.warning(f"Image analysis failed: {str(e)}")

            return {
                'title': title,
                'item_url': item_url,
                'price': price,
                'seller_id': seller_id,
                'category': category,
                'service_type': service_type,
                'thumbnail_url': image_urls[0] if image_urls else None,
                'larger_image_url': final_image_url,
                'image_analysis': image_analysis,
                'condition': {
                    'is_new': condition_info['is_new'],
                    'is_used': condition_info['is_used'],
                    'is_unopened': condition_info['is_unopened'],
                    'is_played': condition_info['is_played'],
                    'is_scratched': condition_info['is_scratched'],
                    'is_damaged': condition_info['is_damaged'],
                    'notes': condition_info['condition_notes'],
                    'summary': condition_info['condition_summary']
                }
            }
        except Exception as e:
            logger.error(f"Error parsing listing: {str(e)}")
            return None

    def get_item_details(self, item_url):
        """Fetch and parse details from an individual Buyee listing page."""
        logger.info(f"Fetching detailed information for item: {item_url}")
        
        html_content = self.get_page(item_url)
        if not html_content:
            logger.error(f"Failed to fetch item page: {item_url}")
            return {}
            
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            details = {}
            
            # Extract full description
            description_element = soup.find('div', {'class': 'item-description'})
            if description_element:
                details['full_description'] = description_element.get_text(separator=' ', strip=True)
                logger.info("Successfully extracted item description")
            else:
                logger.warning("Could not find item description element")
            
            # Extract all image URLs from Buyee
            image_urls = []
            
            # Look for image elements with Buyee URLs
            img_elements = soup.find_all('img', {'class': ['item-image', 'item-image-thumbnail', 'magnify-image']})
            for img in img_elements:
                src = img.get('src')
                if src and src.startswith(self.base_url):
                    image_urls.append(src)
                
                # Also check data attributes for magnified images
                data_src = img.get('data-src') or img.get('data-magnify-src')
                if data_src and data_src.startswith(self.base_url):
                    image_urls.append(data_src)
            
            # Look for magnify containers
            magnify_containers = soup.find_all(['div', 'span'], {'class': ['magnify-container', 'image-magnify']})
            for container in magnify_containers:
                data_src = container.get('data-src') or container.get('data-magnify-src')
                if data_src and data_src.startswith(self.base_url):
                    image_urls.append(data_src)
            
            # Remove duplicates while preserving order
            image_urls = list(dict.fromkeys(image_urls))
            
            if image_urls:
                details['all_images'] = image_urls
                logger.info(f"Found {len(image_urls)} images for item")
            else:
                logger.warning("No images found on item page")
            
            # Extract additional metadata
            metadata = {}
            
            # Try to find card-specific details
            card_details = soup.find('div', {'class': 'item-details'})
            if card_details:
                # Look for card name, edition, set number, etc.
                for detail in card_details.find_all(['div', 'span'], {'class': ['item-detail', 'item-detail-value']}):
                    text = detail.get_text(strip=True)
                    if ':' in text:
                        key, value = text.split(':', 1)
                        metadata[key.strip()] = value.strip()
            
            details['metadata'] = metadata
            
            # Extract seller information
            seller_info = {}
            seller_element = soup.find('div', {'class': 'seller-info'})
            if seller_element:
                seller_name = seller_element.find('span', {'class': 'seller-name'})
                if seller_name:
                    seller_info['name'] = seller_name.get_text(strip=True)
                
                seller_rating = seller_element.find('span', {'class': 'seller-rating'})
                if seller_rating:
                    seller_info['rating'] = seller_rating.get_text(strip=True)
            
            details['seller_info'] = seller_info
            
            # Extract condition information from description
            if 'full_description' in details:
                condition_info = self.extract_condition_from_description(details['full_description'])
                details['detailed_condition'] = condition_info
            
            return details
            
        except Exception as e:
            logger.error(f"Error parsing item details: {str(e)}")
            return {}

    def extract_condition_from_description(self, description):
        """Extract detailed condition information from item description."""
        condition_info = {
            'is_new': False,
            'is_used': False,
            'is_unopened': False,
            'is_played': False,
            'is_scratched': False,
            'is_damaged': False,
            'condition_notes': [],
            'specific_issues': []
        }
        
        # Convert to lowercase for case-insensitive matching
        desc_lower = description.lower()
        
        # Check for condition indicators
        condition_indicators = {
            'new': ['新品', '新規', '未使用', '未開封', 'new', 'unused', 'unopened', 'sealed', 'mint'],
            'used': ['中古', '使用済み', '使用感あり', 'used', 'secondhand', 'pre-owned'],
            'unopened': ['未開封', 'シール付き', 'パッケージ付き', 'unopened', 'sealed', 'packaged'],
            'played': ['プレイ済み', '使用済み', '遊んだ', 'played', 'used in play'],
            'scratched': ['傷あり', 'キズあり', '擦れあり', 'scratched', 'scuff', 'wear'],
            'damaged': ['傷あり', '汚れあり', '破れあり', '折れあり', 'damaged', 'tear', 'stain', 'bent']
        }
        
        # Check for each condition type
        for condition, indicators in condition_indicators.items():
            for indicator in indicators:
                if indicator.lower() in desc_lower:
                    condition_info[f'is_{condition}'] = True
                    condition_info['condition_notes'].append(f"{condition}: {indicator}")
        
        # Look for specific issues
        specific_issues = {
            'edge_wear': ['edge wear', 'edge damage', 'エッジ傷', 'エッジ擦れ'],
            'corner_damage': ['corner damage', 'corner wear', 'corner ding', '角傷', '角擦れ'],
            'surface_scratches': ['surface scratch', 'surface wear', '表面傷', '表面擦れ'],
            'holo_damage': ['holo damage', 'holo scratch', 'ホロ傷', 'ホロ擦れ'],
            'water_damage': ['water damage', 'water stain', '水傷', '水シミ'],
            'sun_damage': ['sun damage', 'sun fade', '日焼け', '退色']
        }
        
        for issue_type, indicators in specific_issues.items():
            for indicator in indicators:
                if indicator.lower() in desc_lower:
                    condition_info['specific_issues'].append(f"{issue_type}: {indicator}")
        
        return condition_info

    def scrape_listings(self, search_term, sort_by='popular'):
        """Scrape the main listings page for a given search term with sorting option."""
        logger.info(f"Starting to scrape Buyee listings for: {search_term} (sorted by: {sort_by})")
        
        # URL encode the search term
        encoded_term = quote(search_term)
        
        # Add sorting parameter
        sort_params = {
            'popular': 'popular',
            'newest': 'newest',
            'price_asc': 'price_asc',
            'price_desc': 'price_desc'
        }
        sort_value = sort_params.get(sort_by, 'popular')
        
        search_url = f"{self.base_url}/item/search/query/{encoded_term}?sort={sort_value}"
        
        html_content = self.get_page(search_url)
        if not html_content:
            return []

        # Extract data from Knockout.js
        items_data = self.extract_ko_data(html_content)
        logger.info(f"Found {len(items_data)} items in Knockout.js data")
        
        listings = []
        for item_data in items_data:
            # Get basic listing data
            listing_data = self.parse_listing(item_data)
            if listing_data:
                # Get detailed information from item page
                detailed_info = self.get_item_details(listing_data['item_url'])
                
                # Merge detailed info with basic listing data
                listing_data.update(detailed_info)
                
                # Add search term to the listing data
                listing_data['search_term'] = search_term
                listings.append(listing_data)
                logger.info(f"Scraped listing: {listing_data['title']}")

        return listings

    def save_to_json(self, data, filename='buyee_listings.json'):
        """Save scraped data to JSON file."""
        try:
            # Get absolute path for the file
            file_path = os.path.abspath(filename)
            logger.info(f"Attempting to save JSON data to: {file_path}")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # Verify file was created
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                logger.info(f"Successfully saved {len(data)} listings to {filename} (Size: {file_size} bytes)")
            else:
                logger.error(f"File {filename} was not created successfully")
                
        except Exception as e:
            logger.error(f"Error saving data to {filename}: {str(e)}")
            # Print the current working directory for debugging
            logger.error(f"Current working directory: {os.getcwd()}")

    def save_to_csv(self, data, filename='buyee_listings.csv'):
        """Save scraped data to CSV file."""
        try:
            # Get absolute path for the file
            file_path = os.path.abspath(filename)
            logger.info(f"Attempting to save CSV data to: {file_path}")
            
            import csv
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'search_term', 'title', 'item_url', 'price', 'seller_id', 
                    'category', 'service_type', 'thumbnail_url', 'larger_image_url', 
                    'image_analysis', 'condition_is_new', 'condition_is_used',
                    'condition_is_unopened', 'condition_is_played', 'condition_is_scratched',
                    'condition_is_damaged', 'condition_notes', 'condition_summary'
                ])
                writer.writeheader()
                for item in data:
                    # Flatten condition dictionary for CSV
                    row = item.copy()
                    if 'condition' in row:
                        row['condition_is_new'] = row['condition']['is_new']
                        row['condition_is_used'] = row['condition']['is_used']
                        row['condition_is_unopened'] = row['condition']['is_unopened']
                        row['condition_is_played'] = row['condition']['is_played']
                        row['condition_is_scratched'] = row['condition']['is_scratched']
                        row['condition_is_damaged'] = row['condition']['is_damaged']
                        row['condition_notes'] = '; '.join(row['condition']['notes'])
                        row['condition_summary'] = row['condition']['summary']
                        del row['condition']
                    writer.writerow(row)
            
            # Verify file was created
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                logger.info(f"Successfully saved {len(data)} listings to {filename} (Size: {file_size} bytes)")
            else:
                logger.error(f"File {filename} was not created successfully")
                
        except Exception as e:
            logger.error(f"Error saving data to {filename}: {str(e)}")
            # Print the current working directory for debugging
            logger.error(f"Current working directory: {os.getcwd()}")

def main():
    scraper = BuyeeScraper()
    
    # Check VPN requirement before starting
    scraper.check_vpn_requirement()
    
    all_listings = []
    
    for search_term in SEARCH_TERMS:
        logger.info(f"\nProcessing search term: {search_term}")
        # Try to get popular listings first
        listings = scraper.scrape_listings(search_term, sort_by='popular')
        if listings:
            all_listings.extend(listings)
            logger.info(f"Found {len(listings)} listings for {search_term}")
        else:
            logger.warning(f"No listings found for {search_term}")
        
        # Add a longer delay between different search terms
        time.sleep(random.uniform(5, 10))
    
    if all_listings:
        # Print current working directory
        logger.info(f"Current working directory: {os.getcwd()}")
        
        # Save in both formats
        logger.info(f"Attempting to save {len(all_listings)} total listings...")
        scraper.save_to_json(all_listings)
        scraper.save_to_csv(all_listings)
        
        # Verify files exist
        json_file = os.path.abspath('buyee_listings.json')
        csv_file = os.path.abspath('buyee_listings.csv')
        
        if os.path.exists(json_file) and os.path.exists(csv_file):
            logger.info(f"Successfully saved all listings to:\nJSON: {json_file}\nCSV: {csv_file}")
        else:
            logger.error("Failed to save one or both files")
            if not os.path.exists(json_file):
                logger.error(f"JSON file not found at: {json_file}")
            if not os.path.exists(csv_file):
                logger.error(f"CSV file not found at: {csv_file}")
    else:
        logger.error("No listings were scraped")

if __name__ == "__main__":
    main() 