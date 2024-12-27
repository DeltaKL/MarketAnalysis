import logging
import os
logging.basicConfig(filename='financial_report_app.log', level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
from typing import Dict, Any, List
from degiro_connector.trading.api import API as TradingAPI
from degiro_connector.trading.models.credentials import Credentials
from degiro_connector.core.exceptions import DeGiroConnectionError
from degiro_connector.trading.api import API
from degiro_connector.trading.actions.action_connect import ActionConnect
from degiro_connector.trading.models.product_search import LookupRequest


class DegiroConnector:
    def __init__(self, prompt_for_2fa_callback=None):
        self.trading_api = None
        self.session_id = None
        self.prompt_for_2fa_callback = prompt_for_2fa_callback

    def connect(self, username, password):
        try:
            credentials = Credentials(
                username=username,
                password=password
            )

            self.trading_api = TradingAPI(credentials=credentials)

            # First, attempt to connect without 2FA
            try:
                self.trading_api.connect()
                self.session_id = self.trading_api.connection_storage.session_id
                logger.info("Connected successfully without 2FA")
                return True
            except DeGiroConnectionError as e:
                # Check if the error is due to 2FA being required
                if "2fa" in str(e).lower():
                    # Prompt for 2FA code using the callback
                    if self.prompt_for_2fa_callback:
                        two_factor_code = self.prompt_for_2fa_callback()
                        if two_factor_code:
                            credentials.one_time_password = two_factor_code
                            self.trading_api = TradingAPI(credentials=credentials)
                            self.trading_api.connect()
                            self.session_id = self.trading_api.connection_storage.session_id
                            logger.info("Connected successfully with 2FA")
                            return True
                        else:
                            logger.error("2FA code not provided")
                            return False
                    else:
                        logger.error("2FA required but no prompt method provided")
                        return False
                else:
                    raise  # Re-raise if it's not a 2FA-related error

        except DeGiroConnectionError as degiro_error:
            logger.error(f"Error logging in to Degiro: {degiro_error}")
            if degiro_error.error_details:
                logger.error(f"Degiro error details: {degiro_error.error_details}")
        except ConnectionError as connection_error:
            logger.error(f"ConnectionError: {connection_error}")

        return False

    def prompt_for_2fa(self):
        # This method should be implemented in the GUI to prompt the user for the 2FA code
        # For now, we'll use a simple input (you should replace this with a GUI prompt)
        return input("Enter your 2FA code: ")

    def disconnect(self):
        if self.trading_api:
            self.trading_api.logout()
            logger.info("Logged out successfully")

    def get_company_profile(self, isin: str) -> Dict[str, Any]:
        try:
            profile = self.trading_api.get_company_profile(product_isin=isin)
            return profile.dict() if profile else {}
        except Exception as e:
            logger.error(f"Error fetching company profile: {str(e)}")
            return {}

    def fetch_data(self, isin_codes: List[str]) -> Dict[str, Dict[str, Any]]:
        results = {}
        for isin in isin_codes:
            results[isin] = {
                'profile': self.get_company_profile(isin),
                'ratios': self.get_company_ratios(isin)
            }
        return results

    def get_company_ratios(self, isin: str, raw: bool = True) -> Dict[str, Any]:
        return self.trading_api.get_company_ratios(product_isin=isin, raw=raw)

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