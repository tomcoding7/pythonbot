from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
import re
import logging

class CardCondition(Enum):
    UNKNOWN = "unknown"
    MINT = "mint"
    NEAR_MINT = "near_mint"
    EXCELLENT = "excellent"
    GOOD = "good"
    LIGHT_PLAYED = "light_played"
    PLAYED = "played"
    POOR = "poor"

class CardInfo:
    def __init__(self, 
                 title: str,
                 price: float,
                 condition: CardCondition,
                 rarity: Optional[str],
                 set_code: Optional[str],
                 card_number: Optional[str],
                 edition: Optional[str],
                 region: Optional[str],
                 is_valuable: bool,
                 confidence_score: float,
                 matched_keywords: List[str],
                 description: Optional[str] = None):
        self.title = title
        self.price = price
        self.condition = condition
        self.rarity = rarity
        self.set_code = set_code
        self.card_number = card_number
        self.edition = edition
        self.region = region
        self.is_valuable = is_valuable
        self.confidence_score = confidence_score
        self.matched_keywords = matched_keywords
        self.description = description

class CardAnalyzer:
    def __init__(self):
        # Card name patterns (both English and Japanese)
        self.card_name_patterns = [
            r'Blue-Eyes White Dragon|青眼の白龍',
            r'Dark Magician|ブラック・マジシャン',
            r'Red-Eyes Black Dragon|レッドアイズ・ブラックドラゴン',
            r'Exodia|エクゾディア',
            r'Black Luster Soldier|カオス・ソルジャー',
            r'Chaos Emperor Dragon|カオス・エンペラー・ドラゴン',
            r'Cyber Dragon|サイバー・ドラゴン',
            r'Elemental Hero|エレメンタル・ヒーロー',
            r'Destiny Hero|デステニー・ヒーロー',
            r'Neos|ネオス',
            r'Stardust Dragon|スターダスト・ドラゴン',
            r'Black Rose Dragon|ブラックローズ・ドラゴン',
            r'Arcanite Magician|アーカナイト・マジシャン'
        ]
        
        # Valuable cards with their known valuable set codes
        self.valuable_cards = {
            "Blue-Eyes White Dragon": ["LOB", "SDK", "SKE", "MVP1"],
            "Dark Magician": ["LOB", "SDY", "SYE", "MVP1"],
            "Red-Eyes Black Dragon": ["LOB", "SDJ", "SJ2"],
            "Exodia the Forbidden One": ["LOB", "MC1"],
            "Black Luster Soldier": ["SYE", "YGLD"],
            "Chaos Emperor Dragon": ["IOC", "DR1"],
            "Cyber Dragon": ["CRV", "RYMP"],
            "Elemental Hero Neos": ["STON", "RYMP"],
            "Stardust Dragon": ["TDGS", "CT05"],
            "Black Rose Dragon": ["CSOC", "CT05"],
            "Arcanite Magician": ["CRMS", "CT07"]
        }
        
        # High-value rarity keywords
        self.high_value_rarities = [
            "ghost rare", "ultimate rare", "starlight rare", "quarter century",
            "secret rare", "collector's rare", "prismatic secret rare"
        ]
        
        # Set code pattern (e.g., LOB-001, MRD-060)
        self.set_code_pattern = r'([A-Z]{2,4})-(\d{3})'
        
        # Rarity keywords (both English and Japanese)
        self.rarity_keywords = {
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
        
        # Edition keywords (both English and Japanese)
        self.edition_keywords = {
            '1st edition': ['1st', 'first edition', '初版'],
            'unlimited': ['unlimited', '無制限', '再版']
        }
        
        # Region keywords (both English and Japanese)
        self.region_keywords = {
            'asia': ['asia', 'asian', 'アジア', 'アジア版'],
            'english': ['english', '英', '英語版'],
            'japanese': ['japanese', '日', '日本語版'],
            'korean': ['korean', '韓', '韓国版']
        }
        
        # Structured data fields for LLM analysis
        self.llm_analysis_fields = {
            'card_name': None,
            'set_name': None,
            'set_code': None,
            'card_number': None,
            'rarity': None,
            'edition': None,
            'region': None,
            'condition_notes': [],
            'damage_notes': [],
            'special_notes': [],
            'grading_info': None,
            'auction_details': None
        }
        
        # Enhanced condition keywords with more Japanese terms and context
        self.condition_keywords = {
            'mint': {
                'keywords': ['mint', 'ミント', '未使用', '完全美品', '新品同様', '初期傷なし', 'パーフェクト'],
                'context': ['perfect', 'no damage', 'no wear', 'no scratches', 'pristine'],
                'weight': 1.0
            },
            'near_mint': {
                'keywords': ['near mint', 'nm', 'ニアミント', '新品同様', '美品', 'ほぼ新品', '極美品'],
                'context': ['almost perfect', 'minor wear', 'slight wear', 'minimal damage'],
                'weight': 0.9
            },
            'excellent': {
                'keywords': ['excellent', 'ex', 'エクセレント', '美品', '良品', '状態良好'],
                'context': ['very good', 'light wear', 'minor damage', 'slight damage'],
                'weight': 0.8
            },
            'good': {
                'keywords': ['good', 'gd', 'グッド', '良品', '使用感あり', '経年変化あり'],
                'context': ['moderate wear', 'some damage', 'visible wear', 'used'],
                'weight': 0.6
            },
            'light_played': {
                'keywords': ['light played', 'lp', 'ライトプレイ', '軽度使用', '軽い使用感', '微傷あり'],
                'context': ['played', 'moderate damage', 'visible damage', 'wear'],
                'weight': 0.4
            },
            'played': {
                'keywords': ['played', 'pl', 'プレイ', '使用済み', '使用感あり', '傷あり'],
                'context': ['heavily played', 'significant damage', 'major wear', 'damaged'],
                'weight': 0.2
            },
            'poor': {
                'keywords': ['poor', 'pr', 'プア', '傷あり', '状態悪い', '破損あり'],
                'context': ['damaged', 'heavily damaged', 'severe wear', 'destroyed'],
                'weight': 0.1
            }
        }
        
        # High-value condition indicators
        self.high_value_conditions = [
            'perfect', 'パーフェクト', 'gem mint', 'ジェムミント',
            'no scratches', '傷なし', 'no wear', '摩耗なし',
            '初期傷なし', '完全美品', '新品同様'
        ]

    def analyze_card(self, 
                    item_data: Dict[str, Any],
                    rank_analysis_results: Optional[Dict] = None,
                    llm_analysis_results: Optional[Dict] = None) -> CardInfo:
        """Analyze a card listing using both title and description data, with optional LLM analysis."""
        title = item_data.get('title', '')
        price = self._extract_price(item_data.get('price_text', '0'))
        description = item_data.get('description', '')
        
        # Get condition from rank analysis, LLM analysis, or text
        condition = CardCondition.UNKNOWN
        if rank_analysis_results and rank_analysis_results.get('condition') != CardCondition.UNKNOWN:
            condition = rank_analysis_results['condition']
        elif llm_analysis_results and llm_analysis_results.get('condition'):
            condition = CardCondition(llm_analysis_results['condition'])
        else:
            condition = self._determine_condition(title, description)
        
        # Extract other attributes from LLM analysis or text
        if llm_analysis_results:
            rarity = llm_analysis_results.get('rarity')
            set_code = llm_analysis_results.get('set_code')
            card_number = llm_analysis_results.get('card_number')
            edition = llm_analysis_results.get('edition')
            region = llm_analysis_results.get('region')
        else:
            rarity = self._determine_rarity(title, description)
            set_info = self._extract_set_info(title, description)
            set_code = set_info[0]
            card_number = set_info[1]
            edition = self._determine_edition(title, description)
            region = self._determine_region(title, description)
        
        # Extract all matched keywords
        matched_keywords = self._extract_keywords(title, description)
        
        # Add any special notes from LLM analysis
        if llm_analysis_results and llm_analysis_results.get('special_notes'):
            matched_keywords.extend(llm_analysis_results['special_notes'])
        
        # Determine if card is valuable
        is_valuable = self._is_valuable_card(
            title=title,
            description=description,
            set_code=set_code,
            rarity=rarity,
            edition=edition,
            matched_keywords=matched_keywords,
            llm_analysis=llm_analysis_results
        )
        
        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(
            condition=condition,
            rarity=rarity,
            set_code=set_code,
            card_number=card_number,
            edition=edition,
            region=region,
            matched_keywords=matched_keywords,
            llm_analysis=llm_analysis_results
        )
        
        return CardInfo(
            title=title,
            price=price,
            condition=condition,
            rarity=rarity,
            set_code=set_code,
            card_number=card_number,
            edition=edition,
            region=region,
            is_valuable=is_valuable,
            confidence_score=confidence_score,
            matched_keywords=matched_keywords,
            description=description
        )

    def _extract_price(self, price_text: str) -> float:
        """Extract price from text."""
        try:
            # Remove currency symbols and commas
            price_text = re.sub(r'[^\d.]', '', price_text)
            return float(price_text)
        except (ValueError, TypeError):
            return 0.0

    def _determine_condition(self, title: str, description: str = '') -> CardCondition:
        """Determine card condition from text."""
        text_to_search = f"{title} {description}".lower()
        for condition, keywords in self.condition_keywords.items():
            if any(keyword.lower() in text_to_search for keyword in keywords['keywords']):
                return CardCondition(condition)
        return CardCondition.UNKNOWN

    def _determine_rarity(self, title: str, description: str = '') -> Optional[str]:
        """Determine card rarity from text."""
        text_to_search = f"{title} {description}".lower()
        for rarity, keywords in self.rarity_keywords.items():
            if any(keyword.lower() in text_to_search for keyword in keywords):
                return rarity
        return None

    def _extract_set_info(self, title: str, description: str = '') -> Tuple[Optional[str], Optional[str]]:
        """Extract set code and card number from text."""
        text_to_search = f"{title} {description}"
        match = re.search(self.set_code_pattern, text_to_search)
        if match:
            return match.group(1), match.group(2)
        return None, None

    def _determine_edition(self, title: str, description: str = '') -> Optional[str]:
        """Determine card edition from text."""
        text_to_search = f"{title} {description}".lower()
        for edition, keywords in self.edition_keywords.items():
            if any(keyword.lower() in text_to_search for keyword in keywords):
                return edition
        return None

    def _determine_region(self, title: str, description: str = '') -> Optional[str]:
        """Determine card region from text."""
        text_to_search = f"{title} {description}".lower()
        for region, keywords in self.region_keywords.items():
            if any(keyword.lower() in text_to_search for keyword in keywords):
                return region
        return None

    def _extract_keywords(self, title: str, description: str = '') -> List[str]:
        """Extract all relevant keywords from text."""
        keywords = []
        text_to_search = f"{title} {description}".lower()
        
        # Check for valuable card names
        for card_name in self.valuable_cards.keys():
            if card_name.lower() in text_to_search:
                keywords.append(card_name)
        
        # Check for high-value rarities
        for rarity in self.high_value_rarities:
            if rarity.lower() in text_to_search:
                keywords.append(rarity)
        
        # Check for edition keywords
        for edition, keywords_list in self.edition_keywords.items():
            if any(keyword.lower() in text_to_search for keyword in keywords_list):
                keywords.append(edition)
        
        # Check for region keywords
        for region, keywords_list in self.region_keywords.items():
            if any(keyword.lower() in text_to_search for keyword in keywords_list):
                keywords.append(region)
        
        # Check for condition keywords
        for condition, keywords_dict in self.condition_keywords.items():
            if any(keyword.lower() in text_to_search for keyword in keywords_dict['keywords']):
                keywords.append(condition)
        
        # Check for value indicators
        for indicator in self.value_indicators:
            if indicator.lower() in text_to_search:
                keywords.append(indicator)
        
        return keywords

    def _is_valuable_card(self,
                         title: str,
                         description: str,
                         set_code: Optional[str],
                         rarity: Optional[str],
                         edition: Optional[str],
                         matched_keywords: List[str],
                         llm_analysis: Optional[Dict] = None) -> bool:
        """Determine if a card is valuable based on multiple criteria."""
        text_to_search = f"{title} {description}".lower()
        
        # Check if it's a known valuable card
        for card_name, valuable_sets in self.valuable_cards.items():
            if card_name.lower() in text_to_search:
                # If set code is known, check if it's a valuable set
                if set_code and valuable_sets:
                    if set_code in valuable_sets:
                        return True
                # If no set code but it's a valuable card, still consider it
                elif not set_code:
                    return True
        
        # Check for high-value rarities
        if rarity and rarity.lower() in [r.lower() for r in self.high_value_rarities]:
            return True
        
        # Check for 1st edition
        if edition == '1st edition':
            return True
        
        # Check for tournament/event cards
        tournament_keywords = ['tournament', 'championship', 'event', 'promo', 'limited']
        if any(keyword in text_to_search for keyword in tournament_keywords):
            return True
        
        # Check for high-value condition indicators
        if any(indicator in text_to_search for indicator in self.high_value_conditions):
            return True
        
        # Check for grading indicators
        grading_keywords = ['psa', 'bgs', 'cgc', 'graded', 'グレード', '鑑定済み']
        if any(keyword in text_to_search for keyword in grading_keywords):
            return True
        
        # Check for special printings
        special_printing_keywords = ['misprint', 'ミスプリント', 'test print', 'テスト版', 'sample', 'サンプル']
        if any(keyword in text_to_search for keyword in special_printing_keywords):
            return True
        
        # Check LLM analysis results if available
        if llm_analysis:
            # Check for high condition rating
            if llm_analysis.get('condition_rating', 0) >= 0.8:  # 80% or higher condition
                return True
            
            # Check for special notes indicating value
            special_notes = llm_analysis.get('special_notes', [])
            if any(note.lower() in ['error', 'misprint', 'test print', 'prototype', 'sample'] 
                  for note in special_notes):
                return True
            
            # Check for grading information
            if llm_analysis.get('grading_info'):
                grade = llm_analysis['grading_info'].get('grade', '').lower()
                if any(high_grade in grade for high_grade in ['10', '9', 'gem']):
                    return True
        
        return False

    def _calculate_confidence_score(self,
                                  condition: CardCondition,
                                  rarity: Optional[str],
                                  set_code: Optional[str],
                                  card_number: Optional[str],
                                  edition: Optional[str],
                                  region: Optional[str],
                                  matched_keywords: List[str],
                                  llm_analysis: Optional[Dict] = None) -> float:
        """Calculate confidence score based on multiple factors."""
        score = 0.0
        
        # Condition score (enhanced weights)
        if condition == CardCondition.MINT:
            score += 0.35  # Increased weight for mint condition
        elif condition == CardCondition.NEAR_MINT:
            score += 0.3   # Increased weight for near mint
        elif condition == CardCondition.EXCELLENT:
            score += 0.25  # Increased weight for excellent
        elif condition == CardCondition.GOOD:
            score += 0.15
        elif condition == CardCondition.LIGHT_PLAYED:
            score += 0.1
        elif condition == CardCondition.PLAYED:
            score += 0.05
        
        # Rarity score (enhanced weights)
        if rarity:
            if rarity.lower() in ["ghost rare", "ultimate rare", "starlight rare", "quarter century"]:
                score += 0.3  # Increased weight for highest rarities
            elif rarity.lower() in ["secret rare", "collector's rare", "prismatic secret rare"]:
                score += 0.25  # Increased weight for high rarities
            elif rarity.lower() in ["ultra rare", "gold rare", "platinum rare"]:
                score += 0.2
            elif rarity.lower() in ["super rare", "parallel rare"]:
                score += 0.15
            elif rarity.lower() == "rare":
                score += 0.1
        
        # Set code and card number score
        if set_code and card_number:
            score += 0.2  # Increased weight for complete set information
        
        # Edition score
        if edition == '1st edition':
            score += 0.2  # Increased weight for 1st edition
        
        # Region score
        if region:
            if region.lower() in ['japanese', 'asia']:
                score += 0.15  # Increased weight for Japanese/Asian cards
            else:
                score += 0.1
        
        # Matched keywords bonus (enhanced scoring)
        if len(matched_keywords) >= 4:
            score += 0.15  # Increased bonus for many matched keywords
        elif len(matched_keywords) >= 3:
            score += 0.1
        elif len(matched_keywords) >= 2:
            score += 0.05
        
        # Special condition indicators bonus
        if any(indicator in ' '.join(matched_keywords).lower() for indicator in self.high_value_conditions):
            score += 0.1  # Bonus for perfect condition indicators
        
        # Grading indicators bonus
        if any(keyword in ' '.join(matched_keywords).lower() for keyword in ['psa', 'bgs', 'cgc', 'graded']):
            score += 0.15  # Bonus for graded cards
        
        # LLM analysis bonus if available
        if llm_analysis:
            # Add bonus for high confidence LLM analysis
            if llm_analysis.get('confidence', 0) > 0.8:
                score += 0.1
            
            # Add bonus for detailed condition notes
            if llm_analysis.get('condition_notes'):
                score += 0.05
            
            # Add bonus for grading information
            if llm_analysis.get('grading_info'):
                score += 0.1
        
        return min(score, 1.0)  # Cap at 1.0 