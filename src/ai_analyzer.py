import os
import logging
import openai
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

class CardCondition(Enum):
    MINT = "Mint"
    NEAR_MINT = "Near Mint"
    EXCELLENT = "Excellent"
    GOOD = "Good"
    LIGHT_PLAYED = "Light Played"
    PLAYED = "Played"
    POOR = "Poor"

@dataclass
class CardAnalysis:
    card_name: str
    set_code: str
    card_number: str
    rarity: str
    edition: str
    region: str
    condition: CardCondition
    condition_notes: List[str]
    market_price: float
    profit_margin: float
    confidence: float
    recommendation: str
    notes: List[str]

class AIAnalyzer:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the AI analyzer with OpenAI API key."""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        openai.api_key = self.api_key
        
        # System prompt for card analysis
        self.system_prompt = """You are a collectible card buying assistant. Given a listing, analyze if it's worth buying based on price and condition.

Rules:
- Prefer cards in condition S or A (Mint or Near Mint)
- Do not buy if visible whitening, heavy scratches, or folds
- Look at eBay sold price and compare to Buyee price
- If Buyee price is less than 50% of eBay sold average, and condition is decent, recommend BUY
- Consider card rarity, edition, and region in your analysis

Example:
Listing: SDK-001 Blue Eyes
Condition: A
Price: ¥4800
eBay Sold: $130, $125, $140
→ BUY (Good condition, price is ~40% of market value)

Provide analysis in this format:
{
    "card_name": "string",
    "set_code": "string",
    "card_number": "string",
    "rarity": "string",
    "edition": "string",
    "region": "string",
    "condition": "Mint|Near Mint|Excellent|Good|Light Played|Played|Poor",
    "condition_notes": ["string"],
    "market_price": float,
    "profit_margin": float,
    "confidence": float,
    "recommendation": "BUY|PASS",
    "notes": ["string"]
}"""

    def analyze_card(self, 
                    title: str,
                    description: str,
                    price_yen: float,
                    image_url: Optional[str] = None,
                    ebay_prices: Optional[List[float]] = None) -> CardAnalysis:
        """
        Analyze a card listing using GPT-4 Vision and text analysis.
        
        Args:
            title: Card title
            description: Card description
            price_yen: Price in Japanese Yen
            image_url: URL of card image (optional)
            ebay_prices: List of recent eBay sold prices (optional)
            
        Returns:
            CardAnalysis object with detailed analysis
        """
        try:
            # Prepare the analysis prompt
            analysis_prompt = f"""
Title: {title}
Description: {description}
Price: ¥{price_yen:,}
eBay Sold Prices: {', '.join(f'${p:,.2f}' for p in ebay_prices) if ebay_prices else 'No data'}
"""

            # If we have an image, use GPT-4 Vision
            if image_url:
                # Download image
                import requests
                from io import BytesIO
                from PIL import Image
                
                response = requests.get(image_url)
                image = Image.open(BytesIO(response.content))
                
                # Convert image to base64
                import base64
                buffered = BytesIO()
                image.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                
                # Call GPT-4 Vision
                response = openai.ChatCompletion.create(
                    model="gpt-4-vision-preview",
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": analysis_prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{img_str}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=1000
                )
            else:
                # Use regular GPT-4 for text-only analysis
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": analysis_prompt}
                    ],
                    max_tokens=1000
                )
            
            # Parse the response
            analysis_text = response.choices[0].message.content
            import json
            analysis_data = json.loads(analysis_text)
            
            # Convert to CardAnalysis object
            return CardAnalysis(
                card_name=analysis_data["card_name"],
                set_code=analysis_data["set_code"],
                card_number=analysis_data["card_number"],
                rarity=analysis_data["rarity"],
                edition=analysis_data["edition"],
                region=analysis_data["region"],
                condition=CardCondition(analysis_data["condition"]),
                condition_notes=analysis_data["condition_notes"],
                market_price=analysis_data["market_price"],
                profit_margin=analysis_data["profit_margin"],
                confidence=analysis_data["confidence"],
                recommendation=analysis_data["recommendation"],
                notes=analysis_data["notes"]
            )
            
        except Exception as e:
            logging.error(f"Error in AI analysis: {str(e)}")
            return None

    def get_ebay_prices(self, card_name: str, set_code: str) -> List[float]:
        """
        Get recent eBay sold prices for a card.
        This is a placeholder - you'll need to implement actual eBay API or scraping.
        """
        # TODO: Implement eBay price scraping
        return []

    def save_analysis_example(self, analysis: CardAnalysis, decision: str) -> None:
        """
        Save an analysis example for training.
        This helps build up a dataset of your decisions.
        """
        example = {
            "card_name": analysis.card_name,
            "set_code": analysis.set_code,
            "card_number": analysis.card_number,
            "condition": analysis.condition.value,
            "condition_notes": analysis.condition_notes,
            "price_yen": analysis.market_price,
            "price_ebay": analysis.market_price,
            "decision": decision
        }
        
        # Save to JSON file
        import json
        from datetime import datetime
        
        filename = f"training_data/analysis_examples_{datetime.now().strftime('%Y%m%d')}.json"
        os.makedirs("training_data", exist_ok=True)
        
        try:
            # Load existing examples
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    examples = json.load(f)
            else:
                examples = []
            
            # Add new example
            examples.append(example)
            
            # Save updated examples
            with open(filename, 'w') as f:
                json.dump(examples, f, indent=2)
                
            logging.info(f"Saved analysis example to {filename}")
            
        except Exception as e:
            logging.error(f"Error saving analysis example: {str(e)}") 