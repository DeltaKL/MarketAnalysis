from datetime import date
from pprint import pprint
from typing import Dict, Any

from degiro_connector.trading.api import API as TradingAPI
from degiro_connector.trading.models.credentials import Credentials
from degiro_connector.core.exceptions import DeGiroConnectionError

import json

class DegiroConnector:
    def __init__(self, username: str, password: str, totp_secret_key: str):
        self.credentials = Credentials(
            username=username,
            password=password,
            totp_secret_key=totp_secret_key
        )
        self.trading_api = TradingAPI(credentials=self.credentials)
        self.session_id = None

    def connect(self) -> bool:
        try:
            self.trading_api.connect()
            self.session_id = self.trading_api.connection_storage.session_id
            print(f"Connected successfully. Session ID: {self.session_id}")
            return True
        except DeGiroConnectionError as degiro_error:
            print(f"Error logging in to Degiro: {degiro_error}")
            if degiro_error.error_details:
                print(degiro_error.error_details)
        except ConnectionError as connection_error:
            print(f"ConnectionError: {connection_error}")
        return False

    def disconnect(self):
        if self.trading_api:
            self.trading_api.logout()
            print("Logged out successfully")

    def get_company_profile(self, isin: str) -> Dict[str, Any]:
        return self.trading_api.get_company_profile(product_isin=isin)

    def get_company_ratios(self, isin: str, raw: bool = True) -> Dict[str, Any]:
        return self.trading_api.get_company_ratios(product_isin=isin, raw=raw)

    def fetch_data(self, isin_codes: list[str]):
        results = {}
        for isin in isin_codes:
            results[isin] = {
                'profile': self.get_company_profile(isin).__dict__,
                'ratios': self.get_company_ratios(isin)
            }
        return results



def main():
    connector = DegiroConnector(
        username="DaanvanK",
        password="4y@tibrZr_KC9Xh",
        totp_secret_key="LKXJFAJQB3LDC74ST5BEUJM2KXHKWJCJ"
    )

    if connector.connect():
        isin_codes = ["US7731221062"]
        data = connector.fetch_data(isin_codes)
        with open('company_data.json', 'w') as json_file:
            json.dump(data, json_file, indent=4)

        print("Data saved to company_data.json")
        connector.disconnect()

if __name__ == "__main__":
    main()