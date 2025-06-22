import logging
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
from dataclasses import dataclass
from src.rank_analyzer import RankAnalyzer, CardCondition
from src.search_terms import SEARCH_TERMS

logger = logging.getLogger(__name__)

@dataclass
class CardAnalysisResult:
    title: str
    price: float
    url: str
    image_url: Optional[str]
    condition: Optional[str]
    is_valuable: bool
    rarity: Optional[str]
    set_code: Optional[str]
    card_number: Optional[str]
    edition: Optional[str]
    region: Optional[str]
    confidence_score: float
    profit_potential: Optional[float] = None
    recommendation: Optional[str] = None
    market_price: Optional[float] = None
    analysis_tier: int = 1
    reason: Optional[str] = None

class AnalysisManager:
    def __init__(self):
        # Merge all valuable keywords, rarity, edition, region, and condition logic
        self.rank_analyzer = RankAnalyzer()
        self.non_card_keywords = [
            'playmat', 'プレイマット', 'sleeve', 'スリーブ', 'deck box', 'deck case', 'box', 'ボックス', '未開封'
        ]
        # Add more as needed
        self.valuable_keywords = SEARCH_TERMS
        # Add more valuable card names/sets from analyzers if needed
        self.rarity_keywords = {
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
        self.edition_keywords = {
            '1st Edition': ['1st', 'first edition', '初版', '初刷'],
            'Unlimited': ['unlimited', '無制限', '再版', '再刷']
        }
        self.region_keywords = {
            'Asia': ['asia', 'asian', 'アジア', 'アジア版'],
            'English': ['english', '英', '英語版'],
            'Japanese': ['japanese', '日', '日本語版'],
            'Korean': ['korean', '韓', '韓国版']
        }

    def fast_rule_filter(self, title: str) -> Tuple[bool, Optional[str]]:
        """Tier 1: Quickly filter out non-card items and obvious misses."""
        title_lower = title.lower()
        for keyword in self.non_card_keywords:
            if keyword in title_lower:
                return False, f"Filtered by non-card keyword: {keyword}"
        # Optionally, filter by valuable keywords
        if not any(term in title_lower for term in self.valuable_keywords):
            return False, "No valuable keyword found"
        return True, None

    def extract_basic_info(self, title: str) -> Dict[str, Any]:
        """Extracts rarity, edition, region, etc. from the title."""
        info = {
            'rarity': None,
            'edition': None,
            'region': None
        }
        title_lower = title.lower()
        for rarity, keywords in self.rarity_keywords.items():
            if any(k in title_lower for k in keywords):
                info['rarity'] = rarity
                break
        for edition, keywords in self.edition_keywords.items():
            if any(k in title_lower for k in keywords):
                info['edition'] = edition
                break
        for region, keywords in self.region_keywords.items():
            if any(k in title_lower for k in keywords):
                info['region'] = region
                break
        return info

    def analyze_listing(self, item_data: Dict[str, Any], detail_data: Optional[Dict[str, Any]] = None, image_analysis: Optional[Dict[str, Any]] = None, ai_analysis: Optional[Dict[str, Any]] = None, tier: int = 1) -> CardAnalysisResult:
        """Unified analysis method for a listing. Handles all tiers."""
        title = item_data.get('title', '')
        price = item_data.get('price', 0)
        url = item_data.get('url', '')
        image_url = item_data.get('thumbnail_url') or (detail_data.get('images')[0] if detail_data and detail_data.get('images') else None)
        # Tier 1: Fast filter
        passed, reason = self.fast_rule_filter(title)
        if not passed:
            return CardAnalysisResult(
                title=title, price=price, url=url, image_url=image_url,
                condition=None, is_valuable=False, rarity=None, set_code=None, card_number=None,
                edition=None, region=None, confidence_score=0.0, analysis_tier=1, reason=reason
            )
        # Tier 2: Use detail page for more info
        if detail_data:
            description = detail_data.get('description', '')
            # Use rank analyzer for condition
            seller_condition = description
            rank_result = self.rank_analyzer.analyze_condition(description, seller_condition)
            condition = rank_result['condition'].value if rank_result['condition'] else None
            confidence = rank_result['confidence']
        else:
            condition = None
            confidence = 0.0
        # Extract basic info
        info = self.extract_basic_info(title)
        # Tier 3: AI/Image analysis (stubbed if no API key)
        profit_potential = None
        recommendation = None
        market_price = None
        if ai_analysis:
            # Use AI result if available
            recommendation = ai_analysis.get('recommendation')
            profit_potential = ai_analysis.get('profit_potential')
            market_price = ai_analysis.get('market_price')
        elif image_analysis:
            # Use image analysis if available
            pass  # Add logic as needed
        # Determine if valuable (simple rule: has rarity or edition or region info)
        is_valuable = bool(info['rarity'] or info['edition'] or info['region'])
        return CardAnalysisResult(
            title=title, price=price, url=url, image_url=image_url,
            condition=condition, is_valuable=is_valuable, rarity=info['rarity'], set_code=None, card_number=None,
            edition=info['edition'], region=info['region'], confidence_score=confidence,
            profit_potential=profit_potential, recommendation=recommendation, market_price=market_price,
            analysis_tier=tier, reason=None
        )

    # Stub for AI analysis (can be replaced with Gemini/OpenAI logic)
    def ai_analyze(self, title: str, description: str, price: float, image_url: Optional[str] = None) -> Dict[str, Any]:
        # This is a stub. Replace with real AI call if API key is available.
        return {
            'recommendation': 'PASS',
            'profit_potential': 0.0,
            'market_price': None
        }

    # Stub for image analysis (can be replaced with Gemini/OpenAI logic)
    def image_analyze(self, image_url: str) -> Dict[str, Any]:
        # This is a stub. Replace with real image analysis if API key is available.
        return {
            'analysis': 'No visible damage',
            'is_damaged': False
        } 