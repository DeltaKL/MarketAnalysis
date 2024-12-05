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
    def __init__(self):
        self.trading_api = None
        self.session_id = None

    def connect(self, username, password, two_factor_code):
        try:
            credentials = Credentials(
                username=username,
                password=password,
                one_time_password=two_factor_code,
            )
            self.trading_api = TradingAPI(credentials=credentials)
            self.trading_api.connect()

            # After successful connection, set the two-factor code
            self.trading_api.connection_storage.two_factor_code = two_factor_code

            self.session_id = self.trading_api.connection_storage.session_id
            logger.info("Connected successfully")
            return True
        except DeGiroConnectionError as degiro_error:
            logger.error(f"Error logging in to Degiro: {degiro_error}")
            if degiro_error.error_details:
                logger.error(f"Degiro error details: {degiro_error.error_details}")
        except ConnectionError as connection_error:
            logger.error(f"ConnectionError: {connection_error}")
        return False

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