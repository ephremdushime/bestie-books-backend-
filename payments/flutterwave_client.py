"""
Flutterwave Standard (v3) client - hosted checkout covering cards, bank
transfer, and mobile money in one integration.
Docs: https://developer.flutterwave.com/docs/flutterwave-standard-1

Unlike MTN MoMo / Airtel Money (which push a prompt to the payer's
phone), Flutterwave Standard is redirect-based: we ask for a checkout
`link`, send the payer there, and they come back to `redirect_url`
afterwards. The redirect alone is never trusted as proof of payment -
see verify_by_reference, which is the actual source of truth (matches
Flutterwave's own guidance: closing the checkout page still returns a
"cancelled"-looking redirect, so the verify call is mandatory).
"""

import requests
from django.conf import settings


class FlutterwaveAPIError(Exception):
    def __init__(self, message, status_code=None, response_body=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class FlutterwaveClient:
    def __init__(self):
        self.base_url = settings.FLUTTERWAVE_BASE_URL.rstrip("/")
        self.secret_key = settings.FLUTTERWAVE_SECRET_KEY

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    def initiate_payment(
        self, tx_ref: str, amount: str, currency: str, redirect_url: str,
        email: str, phone_number: str = "", name: str = "",
    ) -> str:
        """
        POST /v3/payments - returns the hosted checkout URL to send the
        payer to. tx_ref must be unique per attempt; we generate it from
        the Payment's own id so verification can look it back up.
        """
        url = f"{self.base_url}/v3/payments"
        payload = {
            "tx_ref": tx_ref,
            "amount": str(amount),
            "currency": currency,
            "redirect_url": redirect_url,
            "customer": {"email": email, "phonenumber": phone_number, "name": name},
            "payment_options": "card,mobilemoneyrwanda,banktransfer",
        }
        try:
            response = requests.post(url, json=payload, headers=self._headers(), timeout=15)
        except requests.exceptions.RequestException as exc:
            raise FlutterwaveAPIError(f"Could not reach Flutterwave: {exc}")
        if not response.ok:
            raise FlutterwaveAPIError("Flutterwave payment init failed", response.status_code, response.text)

        body = response.json()
        link = body.get("data", {}).get("link")
        if not link:
            raise FlutterwaveAPIError("Flutterwave response had no checkout link", response.status_code, response.text)
        return link

    def verify_by_reference(self, tx_ref: str) -> dict:
        """
        GET /v3/transactions/verify_by_reference?tx_ref=...
        Returns Flutterwave's raw data dict, whose `status` is one of
        "successful", "failed", or "pending" (or similar in-progress states).
        This - not the redirect - is what confirm/fail_payment should act on.
        """
        url = f"{self.base_url}/v3/transactions/verify_by_reference"
        try:
            response = requests.get(
                url, params={"tx_ref": tx_ref}, headers=self._headers(), timeout=15
            )
        except requests.exceptions.RequestException as exc:
            raise FlutterwaveAPIError(f"Could not reach Flutterwave: {exc}")
        if not response.ok:
            raise FlutterwaveAPIError("Flutterwave verify failed", response.status_code, response.text)
        return response.json().get("data", {})
