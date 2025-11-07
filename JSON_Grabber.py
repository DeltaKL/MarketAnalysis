import logging
import os
logging.basicConfig(filename='financial_report_app.log', level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
from typing import Dict, Any, List
from degiro_connector.trading.api import API as TradingAPI
from degiro_connector.trading.models.credentials import Credentials
from degiro_connector.core.exceptions import DeGiroConnectionError
# from degiro_connector.trading.api import API
# from degiro_connector.trading.actions.action_connect import ActionConnect
from degiro_connector.trading.models.product_search import LookupRequest


class DegiroConnector:
    def __init__(self, prompt_for_2fa_callback=None):
        self.trading_api = None
        self.session_id = None
        self.prompt_for_2fa_callback = prompt_for_2fa_callback

    # Updated connect() method in JSON_Grabber.py
    def connect(self, username: str, password: str) -> bool:
        credentials = Credentials(
            username=username,
            password=password,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            # Critical browser header
        )

        self.trading_api = TradingAPI(credentials=credentials)

        try:
            # First connection attempt
            connect_result = self.trading_api.connect()
            if not connect_result:
                raise DeGiroConnectionError("Initial connection failed")

            # Get fresh config table after connection
            self.config_table = self.trading_api.get_config()
            return True

        except DeGiroConnectionError as e:
            if "2fa" in str(e).lower() and self.prompt_for_2fa_callback:
                code = self.prompt_for_2fa_callback()
                if code:
                    credentials.one_time_password = code
                    self.trading_api = TradingAPI(credentials=credentials)
                    return self.trading_api.connect()
            return False

    def prompt_for_2fa(self):
        return input("Enter your 2FA code: ")

    def disconnect(self):
        if self.trading_api:
            self.trading_api.logout()
            logger.info("Logged out successfully")

    def get_company_profile(self, isin: str) -> Dict[str, Any]:
        try:
            if not hasattr(self, 'config_table') or self.config_table is None:
                raise AttributeError("config_table is not initialized. Call connect() first.")
            profile_url = self.config_table.get("refinitivCompanyProfileUrl")
            response = self.trading_api.request(
                url=f"{profile_url}/{isin}", method="GET"
            )
            return response.json() if response.status_code == 200 else {}
        except Exception as e:
            logger.error(f"Profile error: {str(e)}")
            return {}

    def get_company_ratios(self, isin: str) -> Dict[str, Any]:
        try:
            # Defensive check: ensure config_table is initialized
            if not hasattr(self, 'config_table') or self.config_table is None:
                raise AttributeError("config_table is not initialized. Call connect() first.")

            ratios_url = self.config_table.get("refinitivCompanyRatiosUrl")
            if not ratios_url:
                raise ValueError("refinitivCompanyRatiosUrl not found in config_table.")

            response = self.trading_api.request(
                url=f"{ratios_url}/{isin}",
                method="GET"
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to fetch ratios for {isin}: HTTP {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"Ratios error: {str(e)}")
            return {}

    def fetch_data(self, isin_codes: List[str]) -> Dict[str, Dict[str, Any]]:
        results = {}
        for isin in isin_codes:
            results[isin] = {
                'profile': self.get_company_profile(isin),
                'ratios': self.get_company_ratios(isin)
            }
        return results


    def search_companies(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        product_request = LookupRequest(
            search_text=query,
            limit=limit,
            offset=0,
            product_type_id=1,  # Assuming 1 is for stocks, adjust if needed
        )
        products_lookup = self.trading_api.product_search(product_request=product_request)

        if products_lookup and hasattr(products_lookup, 'products') and products_lookup.products:
            return [
                {
                    'name': product['name'],
                    'isin': product['isin'],
                    'symbol': product['symbol'],
                    'exchange': product['exchangeId']
                }
                for product in products_lookup.products
            ]
        else:
            return []  # Return an empty list if no results are found