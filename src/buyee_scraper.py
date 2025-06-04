from bs4 import BeautifulSoup
import re
import logging
from typing import List, Dict, Optional, Any
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time
import os
import csv
import json
from datetime import datetime

class BuyeeScraper:
    def __init__(self, headless: bool = True):
        # ... existing code ...
        
        # Search URL parameters
        self.search_params = {
            'sort': 'bids',  # Default to highest bid
            'order': 'd',    # Descending order
            'ranking': None, # Will be set to 'popular' if using popularity sort
            'translationType': '98',
            'page': '1'
        }

    def search_items(self, 
                    query: str,
                    sort_by: str = 'bids',  # 'bids' or 'popular'
                    max_pages: int = 1) -> List[Dict[str, Any]]:
        """
        Search for items on Buyee.
        
        Args:
            query: Search query string
            sort_by: Sort method ('bids' for highest bid or 'popular' for most popular)
            max_pages: Maximum number of pages to scrape
        """
        all_items = []
        
        # Update search parameters
        self.search_params['sort'] = sort_by
        if sort_by == 'popular':
            self.search_params['ranking'] = 'popular'
            self.search_params['order'] = None  # Remove order parameter for popularity sort
        else:
            self.search_params['ranking'] = None
            self.search_params['order'] = 'd'  # Descending order for bid sort
        
        for page in range(1, max_pages + 1):
            self.search_params['page'] = str(page)
            
            # Construct search URL
            search_url = f"https://buyee.jp/item/search/query/{quote(query)}"
            params = {k: v for k, v in self.search_params.items() if v is not None}
            search_url += '?' + '&'.join(f"{k}={v}" for k, v in params.items())
            
            logging.info(f"Searching page {page} with URL: {search_url}")
            
            try:
                self.driver.get(search_url)
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='itemCard']"))
                )
                
                # Get all item cards
                item_cards = self.driver.find_elements(By.CSS_SELECTOR, "div[class*='itemCard']")
                logging.info(f"Found {len(item_cards)} items on page {page}")
                
                for card in item_cards:
                    try:
                        # Extract item data
                        item_data = self._extract_item_data(card)
                        if item_data:
                            all_items.append(item_data)
                    except Exception as e:
                        logging.error(f"Error processing item card: {str(e)}")
                        continue
                
            except Exception as e:
                logging.error(f"Error searching page {page}: {str(e)}")
                break
        
        return all_items

    def _extract_item_data(self, card) -> Optional[Dict[str, Any]]:
        """Extract data from an item card."""
        try:
            # ... existing code ...
            
            # Extract bid count and popularity score if available
            bid_count = None
            popularity_score = None
            
            try:
                bid_element = card.find_element(By.CSS_SELECTOR, "span[class*='bidCount']")
                bid_count = int(bid_element.text.strip())
            except:
                pass
                
            try:
                score_element = card.find_element(By.CSS_SELECTOR, "span[class*='score']")
                popularity_score = int(score_element.text.strip())
            except:
                pass
            
            return {
                'title': title,
                'price_text': price_text,
                'price': price,
                'url': url,
                'image_url': image_url,
                'bid_count': bid_count,
                'popularity_score': popularity_score
            }
            
        except Exception as e:
            logging.error(f"Error extracting item data: {str(e)}")
            return None

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
                
                # Yu-Gi-Oh! specific keywords
                yugioh_keywords = [
                    '遊戯王', 'yugioh', 'yu-gi-oh', 'yu gi oh',
                    '青眼', 'blue-eyes', 'blue eyes',
                    'ブラック・マジシャン', 'black magician', 'dark magician',
                    'レッドアイズ', 'red-eyes', 'red eyes',
                    'エクゾディア', 'exodia',
                    'カオス', 'chaos',
                    'サイバー', 'cyber',
                    'エレメンタル・ヒーロー', 'elemental hero',
                    'デステニー・ヒーロー', 'destiny hero',
                    'ネオス', 'neos',
                    'スターダスト', 'stardust',
                    'ブラックローズ', 'black rose',
                    'アーカナイト', 'arcanite',
                    'シンクロ', 'synchro',
                    'エクシーズ', 'xyz',
                    'リンク', 'link',
                    'ペンデュラム', 'pendulum',
                    '融合', 'fusion',
                    '儀式', 'ritual',
                    '効果', 'effect',
                    '通常', 'normal',
                    '永続', 'continuous',
                    '速攻', 'quick-play',
                    '罠', 'trap',
                    '魔法', 'spell',
                    'モンスター', 'monster',
                    'カード', 'card',
                    'トレカ', 'trading card',
                    'レア', 'rare',
                    'スーパーレア', 'super rare',
                    'ウルトラレア', 'ultra rare',
                    'シークレットレア', 'secret rare',
                    'アルティメットレア', 'ultimate rare',
                    'ゴールドレア', 'gold rare',
                    'プラチナレア', 'platinum rare',
                    'パラレルレア', 'parallel rare',
                    'コレクターズレア', 'collector\'s rare',
                    'クォーターセンチュリー', 'quarter century',
                    '1st', 'first edition', '初版',
                    '限定', 'limited',
                    '特典', 'promo',
                    '大会', 'tournament',
                    'イベント', 'event',
                    'チャンピオンシップ', 'championship'
                ]
                
                # Check for Yu-Gi-Oh! keywords
                for keyword in yugioh_keywords:
                    if keyword.lower() in title_lower:
                        confidence += 0.1  # Small boost for each keyword match
                        matched_keywords.append(keyword)
                
                # Check for set codes (e.g., LOB-001, MRD-060)
                set_code_match = re.search(r'([A-Z]{2,4})-(\d{3})', title)
                if set_code_match:
                    confidence += 0.3  # Significant boost for set code
                    matched_keywords.append(set_code_match.group(0))
                
                # Check for condition keywords
                condition_keywords = {
                    'mint': ['mint', 'ミント'],
                    'near mint': ['near mint', 'nm', 'ニアミント'],
                    'excellent': ['excellent', 'ex', 'エクセレント'],
                    'good': ['good', 'gd', 'グッド'],
                    'light played': ['light played', 'lp', 'ライトプレイ'],
                    'played': ['played', 'pl', 'プレイ'],
                    'poor': ['poor', 'pr', 'プア']
                }
                
                for condition, keywords in condition_keywords.items():
                    if any(keyword.lower() in title_lower for keyword in keywords):
                        confidence += 0.2
                        matched_keywords.append(condition)
                
                # Check for rarity keywords
                rarity_keywords = {
                    'common': ['common', 'コモン'],
                    'rare': ['rare', 'レア'],
                    'super rare': ['super rare', 'sr', 'スーパーレア'],
                    'ultra rare': ['ultra rare', 'ur', 'ウルトラレア'],
                    'secret rare': ['secret rare', 'scr', 'シークレットレア'],
                    'ultimate rare': ['ultimate rare', 'utr', 'アルティメットレア'],
                    'ghost rare': ['ghost rare', 'gr', 'ゴーストレア'],
                    'platinum rare': ['platinum rare', 'plr', 'プラチナレア'],
                    'gold rare': ['gold rare', 'gld', 'ゴールドレア'],
                    'parallel rare': ['parallel rare', 'pr', 'パラレルレア'],
                    'collector\'s rare': ['collector\'s rare', 'cr', 'コレクターズレア'],
                    'quarter century': ['quarter century', 'qc', 'クォーターセンチュリー']
                }
                
                for rarity, keywords in rarity_keywords.items():
                    if any(keyword.lower() in title_lower for keyword in keywords):
                        confidence += 0.2
                        matched_keywords.append(rarity)
                
                # Check for edition keywords
                edition_keywords = {
                    '1st edition': ['1st', 'first edition', '初版'],
                    'unlimited': ['unlimited', '無制限', '再版']
                }
                
                for edition, keywords in edition_keywords.items():
                    if any(keyword.lower() in title_lower for keyword in keywords):
                        confidence += 0.15
                        matched_keywords.append(edition)
                
                # Check for region keywords
                region_keywords = {
                    'asia': ['asia', 'asian', 'アジア', 'アジア版'],
                    'english': ['english', '英', '英語版'],
                    'japanese': ['japanese', '日', '日本語版'],
                    'korean': ['korean', '韓', '韓国版']
                }
                
                for region, keywords in region_keywords.items():
                    if any(keyword.lower() in title_lower for keyword in keywords):
                        confidence += 0.15
                        matched_keywords.append(region)
                
                # Log detailed information about the item
                logging.info(f"\nAnalyzing item: {title}")
                logging.info(f"Price: {price}")
                logging.info(f"Matched keywords: {', '.join(matched_keywords)}")
                logging.info(f"Confidence score: {confidence:.2f}")
                
                # Lower confidence threshold to 0.1 (from 0.2)
                if confidence >= 0.1:
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

    def scrape_item_detail_page(self, html_content: str) -> Optional[Dict]:
        """Scrape detailed information from an item's detail page."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Save debug HTML
            debug_dir = "debug_html"
            os.makedirs(debug_dir, exist_ok=True)
            debug_file = os.path.join(debug_dir, f"detail_page_{int(time.time())}.html")
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            # Log the HTML structure for debugging
            logging.info("\nAnalyzing detail page structure:")
            logging.info(f"Title elements found: {len(soup.find_all(['h1', 'h2', 'h3']))}")
            logging.info(f"Description elements found: {len(soup.find_all(['div', 'section'], class_=lambda x: x and ('description' in x.lower() or 'detail' in x.lower() or 'content' in x.lower())))}")
            logging.info(f"Price elements found: {len(soup.find_all(['span', 'div'], class_=lambda x: x and ('price' in x.lower() or 'amount' in x.lower())))}")
            
            # Try multiple selectors for title (Buyee specific)
            title = None
            title_selectors = [
                'h1.item-name',
                'div.item-name',
                'h1[class*="item-name"]',
                'div[class*="item-name"]',
                'h1[class*="title"]',
                'div[class*="title"]',
                'h1[class*="product"]',
                'div[class*="product"]',
                'h1[class*="auction"]',
                'div[class*="auction"]',
                'h1[class*="item-title"]',
                'div[class*="item-title"]',
                'h1[class*="product-title"]',
                'div[class*="product-title"]',
                'h1[class*="auction-title"]',
                'div[class*="auction-title"]'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    logging.info(f"Found title using selector '{selector}': {title}")
                    break
            
            if not title:
                logging.warning("Could not find title element")
                return None
            
            # Try multiple selectors for price (Buyee specific)
            price = None
            price_selectors = [
                'span.price',
                'div.price',
                'span[class*="price"]',
                'div[class*="price"]',
                'span[class*="amount"]',
                'div[class*="amount"]',
                'span[class*="current"]',
                'div[class*="current"]',
                'span[class*="bid"]',
                'div[class*="bid"]',
                'span[class*="current-price"]',
                'div[class*="current-price"]',
                'span[class*="current-bid"]',
                'div[class*="current-bid"]',
                'span[class*="buy-now-price"]',
                'div[class*="buy-now-price"]'
            ]
            
            for selector in price_selectors:
                price_elem = soup.select_one(selector)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price_match = re.search(r'[\d,]+', price_text)
                    if price_match:
                        price = int(price_match.group().replace(',', ''))
                        logging.info(f"Found price using selector '{selector}': {price}")
                        break
            
            if not price:
                logging.warning("Could not find price element")
                return None
            
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
            
            # Try multiple selectors for condition (Buyee specific)
            condition = None
            condition_selectors = [
                'div.item-condition',
                'div[class*="condition"]',
                'div[class*="status"]',
                'div[class*="quality"]',
                'div[class*="rank"]',
                'div[class*="grade"]',
                'li:contains("Item Condition")',
                'li:contains("Condition")',
                'li:contains("Status")',
                'li:contains("Quality")',
                'div[class*="item-condition"]',
                'div[class*="product-condition"]',
                'div[class*="auction-condition"]',
                'div[class*="item-status"]',
                'div[class*="product-status"]',
                'div[class*="auction-status"]',
                'div[class*="item-quality"]',
                'div[class*="product-quality"]',
                'div[class*="auction-quality"]'
            ]
            
            for selector in condition_selectors:
                condition_elem = soup.select_one(selector)
                if condition_elem:
                    condition = condition_elem.get_text(strip=True)
                    logging.info(f"Found condition using selector '{selector}': {condition}")
                    break
            
            # Try multiple selectors for seller (Buyee specific)
            seller = None
            seller_selectors = [
                'div.seller-name',
                'div[class*="seller"]',
                'div[class*="vendor"]',
                'div[class*="shop"]',
                'div[class*="store"]',
                'div[class*="user"]',
                'li:contains("Seller")',
                'li:contains("Vendor")',
                'li:contains("Shop")',
                'li:contains("Store")',
                'div[class*="seller-name"]',
                'div[class*="vendor-name"]',
                'div[class*="shop-name"]',
                'div[class*="store-name"]',
                'div[class*="user-name"]',
                'div[class*="seller-info"]',
                'div[class*="vendor-info"]',
                'div[class*="shop-info"]',
                'div[class*="store-info"]',
                'div[class*="user-info"]'
            ]
            
            for selector in seller_selectors:
                seller_elem = soup.select_one(selector)
                if seller_elem:
                    seller = seller_elem.get_text(strip=True)
                    logging.info(f"Found seller using selector '{selector}': {seller}")
                    break
            
            # Try multiple selectors for images (Buyee specific)
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
                    src = img.get('src', '')
                    if src:
                        images.append(src)
                        logging.info(f"Found image using selector '{selector}': {src}")
            
            # Extract card-specific information
            card_info = {}
            
            # Try to find set code and card number
            set_code_match = re.search(r'([A-Z]{2,4})-(\d{3})', title)
            if set_code_match:
                card_info['set_code'] = set_code_match.group(1)
                card_info['card_number'] = set_code_match.group(2)
                logging.info(f"Found set code and number: {card_info['set_code']}-{card_info['card_number']}")
            
            # Try to find edition
            edition_keywords = {
                '1st edition': ['1st', 'first edition', '初版'],
                'unlimited': ['unlimited', '無制限', '再版']
            }
            
            for edition, keywords in edition_keywords.items():
                if any(keyword.lower() in title.lower() for keyword in keywords):
                    card_info['edition'] = edition
                    logging.info(f"Found edition: {edition}")
                    break
            
            # Try to find rarity
            rarity_keywords = {
                'common': ['common', 'コモン'],
                'rare': ['rare', 'レア'],
                'super rare': ['super rare', 'sr', 'スーパーレア'],
                'ultra rare': ['ultra rare', 'ur', 'ウルトラレア'],
                'secret rare': ['secret rare', 'scr', 'シークレットレア'],
                'ultimate rare': ['ultimate rare', 'utr', 'アルティメットレア'],
                'ghost rare': ['ghost rare', 'gr', 'ゴーストレア'],
                'platinum rare': ['platinum rare', 'plr', 'プラチナレア'],
                'gold rare': ['gold rare', 'gld', 'ゴールドレア'],
                'parallel rare': ['parallel rare', 'pr', 'パラレルレア'],
                'collector\'s rare': ['collector\'s rare', 'cr', 'コレクターズレア'],
                'quarter century': ['quarter century', 'qc', 'クォーターセンチュリー']
            }
            
            for rarity, keywords in rarity_keywords.items():
                if any(keyword.lower() in title.lower() for keyword in keywords):
                    card_info['rarity'] = rarity
                    logging.info(f"Found rarity: {rarity}")
                    break
            
            # Try to find region
            region_keywords = {
                'asia': ['asia', 'asian', 'アジア', 'アジア版'],
                'english': ['english', '英', '英語版'],
                'japanese': ['japanese', '日', '日本語版'],
                'korean': ['korean', '韓', '韓国版']
            }
            
            for region, keywords in region_keywords.items():
                if any(keyword.lower() in title.lower() for keyword in keywords):
                    card_info['region'] = region
                    logging.info(f"Found region: {region}")
                    break
            
            # Log detailed information about the scraped data
            logging.info(f"\nScraped detail page for: {title}")
            logging.info(f"Price: {price}")
            logging.info(f"Condition: {condition}")
            logging.info(f"Seller: {seller}")
            logging.info(f"Number of images: {len(images)}")
            logging.info(f"Card info: {card_info}")
            
            return {
                'title': title,
                'price': price,
                'description': description,
                'condition': condition,
                'seller': seller,
                'images': images,
                'card_info': card_info
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
                .yahoo-link { color: blue; text-decoration: underline; }
                .buyee-link { color: green; text-decoration: underline; }
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
                    <th>Price</th>
                    <th>Confidence</th>
                    <th>Matched Keywords</th>
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
                    <td>¥{price:,}</td>
                    <td class="{confidence_class}">{confidence:.2f}</td>
                    <td>{', '.join(matched_keywords)}</td>
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
            writer.writerow(['Title (JP)', 'Title (EN)', 'Price', 'Confidence', 'Matched Keywords', 'Buyee URL', 'Yahoo URL', 'Thumbnail URL'])
            for summary in summaries:
                title = summary.get('title', '')
                title_parts = title.split('|')
                title_jp = title_parts[0].strip()
                title_en = title_parts[1].strip() if len(title_parts) > 1 else ''
                writer.writerow([
                    title_jp,
                    title_en,
                    summary.get('price', 0),
                    summary.get('analysis', {}).get('confidence_score', 0),
                    ','.join(summary.get('analysis', {}).get('matched_keywords', [])),
                    summary.get('url', ''),
                    summary.get('yahoo_url', ''),
                    summary.get('thumbnail_url', '')
                ])
        logging.info(f"Saved CSV report to: {csv_path}")

        # Save JSON (for programmatic access)
        json_path = os.path.join(self.output_dir, f"{base_filename}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(summaries, f, ensure_ascii=False, indent=2)
        logging.info(f"Saved JSON report to: {json_path}") 