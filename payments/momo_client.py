"""
MTN MoMo Collections API client (sandbox + production).
Docs: https://momodeveloper.mtn.com

Flow implemented (the standard MoMo Collections "request to pay" pattern):
  1. get_access_token()      - Basic auth (API user + API key) -> Bearer token
  2. request_to_pay(...)     - kick off a payment prompt on the payer's phone
  3. get_transaction_status(reference_id) - poll until PENDING resolves to
     SUCCESSFUL / FAILED (or let MTN push the result to a callback URL)

This client raises MomoAPIError on any non-2xx response so callers don't
have to inspect status codes themselves.
"""

import uuid

import requests
from django.conf import settings


class MomoAPIError(Exception):
    def __init__(self, message, status_code=None, response_body=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class MomoClient:
    def __init__(self):
        self.base_url = settings.MOMO_BASE_URL.rstrip("/")
        self.subscription_key = settings.MOMO_SUBSCRIPTION_KEY
        self.api_user = settings.MOMO_API_USER
        self.api_key = settings.MOMO_API_KEY
        self.target_environment = settings.MOMO_TARGET_ENVIRONMENT
        self.callback_url = settings.MOMO_CALLBACK_URL

    def _headers(self, extra=None):
        headers = {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Content-Type": "application/json",
        }
        if extra:
            headers.update(extra)
        return headers

    def get_access_token(self) -> str:
        """POST /collection/token/ using Basic auth (api_user:api_key)."""
        url = f"{self.base_url}/collection/token/"
        try:
            response = requests.post(
                url,
                headers=self._headers(),
                auth=(self.api_user, self.api_key),
                timeout=15,
            )
        except requests.exceptions.RequestException as exc:
            raise MomoAPIError(f"Could not reach MTN MoMo: {exc}")
        if not response.ok:
            raise MomoAPIError(
                "MTN MoMo token request failed", response.status_code, response.text
            )
        return response.json()["access_token"]

    def request_to_pay(self, amount: str, currency: str, msisdn: str,
                        external_id: str, payer_message: str = "", payee_note: str = "") -> str:
        """
        POST /collection/v1_0/requesttopay
        Returns the X-Reference-Id (UUID) we generated - use it to poll status.
        This does NOT confirm payment; MTN prompts the payer's phone and the
        transaction stays PENDING until they approve or decline it.
        """
        token = self.get_access_token()
        reference_id = str(uuid.uuid4())

        url = f"{self.base_url}/collection/v1_0/requesttopay"
        headers = self._headers({
            "Authorization": f"Bearer {token}",
            "X-Reference-Id": reference_id,
            "X-Target-Environment": self.target_environment,
        })
        if self.callback_url:
            headers["X-Callback-Url"] = self.callback_url

        payload = {
            "amount": str(amount),
            "currency": currency,
            "externalId": external_id,
            "payer": {"partyIdType": "MSISDN", "partyId": _normalize_msisdn(msisdn)},
            "payerMessage": payer_message[:160],
            "payeeNote": payee_note[:160],
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
        except requests.exceptions.RequestException as exc:
            raise MomoAPIError(f"Could not reach MTN MoMo: {exc}")
        if response.status_code != 202:
            raise MomoAPIError(
                "MTN MoMo requesttopay failed", response.status_code, response.text
            )
        return reference_id

    def get_transaction_status(self, reference_id: str) -> dict:
        """
        GET /collection/v1_0/requesttopay/{reference_id}
        Returns MTN's raw JSON, e.g. {"status": "SUCCESSFUL", "financialTransactionId": "..."}
        status is one of PENDING, SUCCESSFUL, FAILED.
        """
        token = self.get_access_token()
        url = f"{self.base_url}/collection/v1_0/requesttopay/{reference_id}"
        headers = self._headers({
            "Authorization": f"Bearer {token}",
            "X-Target-Environment": self.target_environment,
        })
        try:
            response = requests.get(url, headers=headers, timeout=15)
        except requests.exceptions.RequestException as exc:
            raise MomoAPIError(f"Could not reach MTN MoMo: {exc}")
        if not response.ok:
            raise MomoAPIError(
                "MTN MoMo status check failed", response.status_code, response.text
            )
        return response.json()


def _normalize_msisdn(phone_number: str) -> str:
    """MTN expects MSISDN without a leading '+' (e.g. 250788000000)."""
    return phone_number.lstrip("+").replace(" ", "")
