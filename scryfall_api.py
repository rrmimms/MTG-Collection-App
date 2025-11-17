"""
Scryfall API Integration Module
Handles communication with Scryfall's API for card data and pricing
"""

import requests
import time
from typing import Dict, List, Optional


class ScryfallAPI:
    """Wrapper for Scryfall API interactions"""
    
    BASE_URL = "https://api.scryfall.com"
    
    def __init__(self):
        self.session = requests.Session()
        self.last_request_time = 0
        self.min_request_interval = 0.1  # Scryfall requests 50-100ms between requests
    
    def _rate_limit(self):
        """Ensure we don't exceed Scryfall's rate limit"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make a request to Scryfall API with rate limiting"""
        self._rate_limit()
        url = f"{self.BASE_URL}{endpoint}"
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def search_cards(self, query: str, unique: str = "cards") -> List[Dict]:
        """
        Search for cards by name or other criteria
        
        Args:
            query: Search query (e.g., card name)
            unique: Type of uniqueness ('cards', 'art', 'prints')
        
        Returns:
            List of card data dictionaries
        """
        try:
            endpoint = "/cards/search"
            params = {"q": query, "unique": unique}
            data = self._make_request(endpoint, params)
            return data.get("data", [])
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return []
            raise
    
    def get_all_printings(self, card_name: str) -> List[Dict]:
        """
        Get all printings of a specific card
        
        Args:
            card_name: Exact card name
        
        Returns:
            List of all printings of the card
        """
        try:
            # Search for all printings (unique=prints)
            endpoint = "/cards/search"
            params = {
                "q": f'!"{card_name}"',
                "unique": "prints",
                "order": "released"
            }
            data = self._make_request(endpoint, params)
            return data.get("data", [])
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return []
            raise
    
    def get_card_by_name(self, name: str, set_code: Optional[str] = None) -> Optional[Dict]:
        """
        Get a specific card by exact name
        
        Args:
            name: Exact card name
            set_code: Optional set code to specify a particular printing
        
        Returns:
            Card data dictionary or None if not found
        """
        try:
            endpoint = "/cards/named"
            params = {"exact": name}
            if set_code:
                params["set"] = set_code
            return self._make_request(endpoint, params)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    def get_card_by_id(self, scryfall_id: str) -> Optional[Dict]:
        """
        Get a card by its Scryfall ID
        
        Args:
            scryfall_id: Scryfall UUID
        
        Returns:
            Card data dictionary or None if not found
        """
        try:
            endpoint = f"/cards/{scryfall_id}"
            return self._make_request(endpoint)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    def autocomplete(self, query: str) -> List[str]:
        """
        Get autocomplete suggestions for card names
        
        Args:
            query: Partial card name
        
        Returns:
            List of suggested card names
        """
        try:
            endpoint = "/cards/autocomplete"
            params = {"q": query}
            data = self._make_request(endpoint, params)
            return data.get("data", [])
        except requests.exceptions.HTTPError:
            return []
    
    @staticmethod
    def extract_card_info(card_data: Dict) -> Dict:
        """
        Extract relevant information from Scryfall card data
        
        Args:
            card_data: Raw card data from Scryfall
        
        Returns:
            Simplified card information dictionary
        """
        # Handle double-faced cards
        image_uris = card_data.get("image_uris", {})
        if not image_uris and "card_faces" in card_data:
            image_uris = card_data["card_faces"][0].get("image_uris", {})
        
        # Extract pricing information
        prices = card_data.get("prices", {})
        usd_price = prices.get("usd") or prices.get("usd_foil")
        
        return {
            "scryfall_id": card_data.get("id"),
            "name": card_data.get("name"),
            "set_code": card_data.get("set"),
            "set_name": card_data.get("set_name"),
            "collector_number": card_data.get("collector_number"),
            "rarity": card_data.get("rarity"),
            "mana_cost": card_data.get("mana_cost", ""),
            "cmc": card_data.get("cmc", 0),
            "type_line": card_data.get("type_line"),
            "oracle_text": card_data.get("oracle_text", ""),
            "colors": ",".join(card_data.get("colors", [])),
            "color_identity": ",".join(card_data.get("color_identity", [])),
            "image_small": image_uris.get("small"),
            "image_normal": image_uris.get("normal"),
            "image_large": image_uris.get("large"),
            "image_art_crop": image_uris.get("art_crop"),
            "price_usd": usd_price,
            "price_usd_foil": prices.get("usd_foil"),
            "scryfall_uri": card_data.get("scryfall_uri"),
        }
