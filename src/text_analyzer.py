from typing import Dict, Any, Optional, List, Tuple
import re
import logging

class TextAnalyzer:
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
        
        # Condition keywords (both English and Japanese)
        self.condition_keywords = {
            'mint': ['mint', 'ミント', '未使用'],
            'near mint': ['near mint', 'nm', 'ニアミント', '新品同様'],
            'excellent': ['excellent', 'ex', 'エクセレント', '美品'],
            'good': ['good', 'gd', 'グッド', '良品'],
            'light played': ['light played', 'lp', 'ライトプレイ', '軽度使用'],
            'played': ['played', 'pl', 'プレイ', '使用済み'],
            'poor': ['poor', 'pr', 'プア', '傷あり']
        }
        
        # Special keywords that might indicate value
        self.value_indicators = [
            'limited', '限定', 'promo', '特典', 'tournament', '大会',
            'championship', 'チャンピオンシップ', 'event', 'イベント',
            'sealed', '未開封', 'unopened', '初期', 'shoki', '旧アジア',
            'kyuu-ajia', 'PSA', 'BGS', 'エラーカード', 'error card'
        ]

    def analyze_text(self, title: str, description: str = '') -> Dict[str, Any]:
        """Analyze text to extract card information."""
        # Combine title and description for analysis
        full_text = f"{title} {description}".lower()
        
        # Extract card name
        card_name = self._extract_card_name(full_text)
        
        # Extract set code and card number
        set_code, card_number = self._extract_set_info(full_text)
        
        # Extract rarity
        rarity = self._extract_rarity(full_text)
        
        # Extract edition
        edition = self._extract_edition(full_text)
        
        # Extract region
        region = self._extract_region(full_text)
        
        # Extract condition keywords
        condition_keywords = self._extract_condition_keywords(full_text)
        
        # Extract value indicators
        value_indicators = self._extract_value_indicators(full_text)
        
        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(
            card_name=card_name,
            set_code=set_code,
            card_number=card_number,
            rarity=rarity,
            edition=edition,
            region=region,
            condition_keywords=condition_keywords,
            value_indicators=value_indicators
        )
        
        # Log the analysis results
        logging.info("\nText Analysis Results:")
        logging.info(f"Card Name: {card_name}")
        logging.info(f"Set Code: {set_code}")
        logging.info(f"Card Number: {card_number}")
        logging.info(f"Rarity: {rarity}")
        logging.info(f"Edition: {edition}")
        logging.info(f"Region: {region}")
        logging.info(f"Condition Keywords: {condition_keywords}")
        logging.info(f"Value Indicators: {value_indicators}")
        logging.info(f"Confidence Score: {confidence_score:.2f}")
        
        return {
            'card_name': card_name,
            'set_code': set_code,
            'card_number': card_number,
            'rarity': rarity,
            'edition': edition,
            'region': region,
            'condition_keywords': condition_keywords,
            'value_indicators': value_indicators,
            'confidence_score': confidence_score
        }

    def _extract_card_name(self, text: str) -> Optional[str]:
        """Extract card name from text."""
        for pattern in self.card_name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        return None

    def _extract_set_info(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract set code and card number from text."""
        match = re.search(self.set_code_pattern, text)
        if match:
            return match.group(1), match.group(2)
        return None, None

    def _extract_rarity(self, text: str) -> Optional[str]:
        """Extract rarity from text."""
        for rarity, keywords in self.rarity_keywords.items():
            if any(keyword.lower() in text.lower() for keyword in keywords):
                return rarity
        return None

    def _extract_edition(self, text: str) -> Optional[str]:
        """Extract edition from text."""
        for edition, keywords in self.edition_keywords.items():
            if any(keyword.lower() in text.lower() for keyword in keywords):
                return edition
        return None

    def _extract_region(self, text: str) -> Optional[str]:
        """Extract region from text."""
        for region, keywords in self.region_keywords.items():
            if any(keyword.lower() in text.lower() for keyword in keywords):
                return region
        return None

    def _extract_condition_keywords(self, text: str) -> List[str]:
        """Extract condition keywords from text."""
        found_keywords = []
        for condition, keywords in self.condition_keywords.items():
            if any(keyword.lower() in text.lower() for keyword in keywords):
                found_keywords.append(condition)
        return found_keywords

    def _extract_value_indicators(self, text: str) -> List[str]:
        """Extract value indicators from text."""
        return [indicator for indicator in self.value_indicators 
                if indicator.lower() in text.lower()]

    def _calculate_confidence_score(self,
                                  card_name: Optional[str],
                                  set_code: Optional[str],
                                  card_number: Optional[str],
                                  rarity: Optional[str],
                                  edition: Optional[str],
                                  region: Optional[str],
                                  condition_keywords: List[str],
                                  value_indicators: List[str]) -> float:
        """Calculate confidence score based on extracted information."""
        score = 0.0
        
        # Card name score
        if card_name:
            score += 0.2
        
        # Set code and card number score
        if set_code and card_number:
            score += 0.15
        
        # Rarity score
        if rarity:
            if rarity.lower() in ['ghost rare', 'ultimate rare', 'starlight rare', 'quarter century']:
                score += 0.15
            elif rarity.lower() in ['secret rare', 'collector\'s rare', 'prismatic secret rare']:
                score += 0.1
            elif rarity.lower() in ['ultra rare', 'gold rare', 'platinum rare']:
                score += 0.08
            elif rarity.lower() in ['super rare', 'parallel rare']:
                score += 0.05
            elif rarity.lower() == 'rare':
                score += 0.03
        
        # Edition score
        if edition == '1st edition':
            score += 0.1
        
        # Region score
        if region:
            if region.lower() in ['japanese', 'asia']:
                score += 0.08
            else:
                score += 0.05
        
        # Condition keywords score
        if len(condition_keywords) >= 2:
            score += 0.1
        elif len(condition_keywords) == 1:
            score += 0.05
        
        # Value indicators score
        if len(value_indicators) >= 2:
            score += 0.1
        elif len(value_indicators) == 1:
            score += 0.05
        
        return min(score, 1.0)  # Cap at 1.0 