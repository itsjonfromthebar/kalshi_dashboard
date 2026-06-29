import base64
import datetime as dt
from pathlib import Path
from urllib.parse import urlencode, urlparse

import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


class KalshiClient:
    def __init__(self, base_url: str, api_key_id: str | None = None, private_key_path: str | None = None):
        self.base_url = base_url.rstrip('/')
        self.api_key_id = api_key_id
        self.private_key_path = private_key_path
        self._private_key = None

    def _load_private_key(self):
        if self._private_key is not None:
            return self._private_key
        if not self.private_key_path:
            raise ValueError('KALSHI_PRIVATE_KEY_PATH is required for authenticated endpoints')
        key_path = Path(self.private_key_path)
        with key_path.open('rb') as f:
            self._private_key = serialization.load_pem_private_key(
                f.read(), password=None, backend=default_backend()
            )
        return self._private_key

    def _signature(self, timestamp: str, method: str, path: str) -> str:
        private_key = self._load_private_key()
        path_without_query = path.split('?')[0]
        message = f'{timestamp}{method.upper()}{path_without_query}'.encode('utf-8')
        signature = private_key.sign(
            message,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode('utf-8')

    def _headers(self, method: str, endpoint: str) -> dict[str, str]:
        if not self.api_key_id:
            return {}
        timestamp = str(int(dt.datetime.now().timestamp() * 1000))
        sign_path = urlparse(self.base_url + endpoint).path
        return {
            'KALSHI-ACCESS-KEY': self.api_key_id,
            'KALSHI-ACCESS-SIGNATURE': self._signature(timestamp, method, sign_path),
            'KALSHI-ACCESS-TIMESTAMP': timestamp,
        }

    def request(self, method: str, endpoint: str, params: dict | None = None, auth: bool = False) -> dict:
        endpoint = endpoint if endpoint.startswith('/') else '/' + endpoint
        url = self.base_url + endpoint
        headers = self._headers(method, endpoint) if auth else {}
        response = requests.request(method, url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_markets(
        self,
        status: str = 'open',
        limit: int = 200,
        cursor: str | None = None,
        mve_filter: str | None = None,
    ) -> dict:
        params = {'status': status, 'limit': limit}
        if cursor:
            params['cursor'] = cursor
        if mve_filter:
            params['mve_filter'] = mve_filter
        return self.request('GET', '/markets', params=params)

    def get_market(self, ticker: str) -> dict:
        return self.request('GET', f'/markets/{ticker}')

    def get_orderbook(self, ticker: str, depth: int = 20) -> dict:
        return self.request('GET', f'/markets/{ticker}/orderbook', params={'depth': depth}, auth=True)

    def get_balance(self) -> dict:
        return self.request('GET', '/portfolio/balance', auth=True)

    def get_positions(self) -> dict:
        return self.request('GET', '/portfolio/positions', auth=True)

    def get_orders(self, limit: int = 100) -> dict:
        return self.request('GET', '/portfolio/orders', params={'limit': limit}, auth=True)
