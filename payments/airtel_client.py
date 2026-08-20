"""
Airtel Money (Airtel Africa Openweb Collections API) client.
Docs: https://developers.airtel.africa

Same request-callback shape as MTN MoMo, different envelope:
  1. get_access_token()   - OAuth2 client_credentials -> Bearer token
  2. request_to_pay(...)  - POST /merchant/v1/payments/ prompts the payer
  3. get_transaction_status(...) - GET /standard/v1/payments/{id}
     Airtel's status codes: TS = success, TF = failed, TIP = in progress.
"""

import uuid

import requests
from django.conf import settings


class AirtelAPIError(Exception):
    def __init__(self, message, status_code=None, response_body=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class AirtelClient:
    def __init__(self):
        self.base_url = settings.AIRTEL_BASE_URL.rstrip("/")
        self.client_id = settings.AIRTEL_CLIENT_ID
        self.client_secret = settings.AIRTEL_CLIENT_SECRET
        self.country = settings.AIRTEL_COUNTRY
        self.currency = settings.AIRTEL_CURRENCY

    def get_access_token(self) -> str:
        url = f"{self.base_url}/auth/oauth2/token"
        try:
            response = requests.post(
                url,
                headers={"Content-Type": "application/json", "Accept": "*/*"},
                json={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
                timeout=15,
            )
        except requests.exceptions.RequestException as exc:
            raise AirtelAPIError(f"Could not reach Airtel Money: {exc}")
        if not response.ok:
            raise AirtelAPIError("Airtel token request failed", response.status_code, response.text)
        return response.json()["access_token"]

    def _headers(self, token: str) -> dict:
        return {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Authorization": f"Bearer {token}",
            "X-Country": self.country,
            "X-Currency": self.currency,
        }

    def request_to_pay(self, amount: str, msisdn: str, external_id: str) -> str:
        """
        POST /merchant/v1/payments/
        Returns our own transaction id (used later to poll status) - Airtel
        also returns a `reference`/`transactionId` in the body but the id
        we generate here is what we send as `transaction.id`, so it's the
        one we poll on.
        """
        token = self.get_access_token()
        transaction_id = str(uuid.uuid4())
        url = f"{self.base_url}/merchant/v1/payments/"
        payload = {
            "reference": f"Bestie Books order {external_id}",
            "subscriber": {
                "country": self.country,
                "currency": self.currency,
                "msisdn": _normalize_msisdn(msisdn),
            },
            "transaction": {
                "amount": str(amount),
                "country": self.country,
                "currency": self.currency,
                "id": transaction_id,
            },
        }
        try:
            response = requests.post(url, json=payload, headers=self._headers(token), timeout=15)
        except requests.exceptions.RequestException as exc:
            raise AirtelAPIError(f"Could not reach Airtel Money: {exc}")
        if not response.ok:
            raise AirtelAPIError("Airtel requesttopay failed", response.status_code, response.text)
        return transaction_id

    def get_transaction_status(self, transaction_id: str) -> dict:
        token = self.get_access_token()
        url = f"{self.base_url}/standard/v1/payments/{transaction_id}"
        try:
            response = requests.get(url, headers=self._headers(token), timeout=15)
        except requests.exceptions.RequestException as exc:
            raise AirtelAPIError(f"Could not reach Airtel Money: {exc}")
        if not response.ok:
            raise AirtelAPIError("Airtel status check failed", response.status_code, response.text)
        return response.json()


def _normalize_msisdn(phone_number: str) -> str:
    return phone_number.lstrip("+").replace(" ", "")
