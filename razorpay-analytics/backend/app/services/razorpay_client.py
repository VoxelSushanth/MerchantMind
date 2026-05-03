"""
Razorpay API client for fetching payments, refunds, and settlements.
"""
import base64
from datetime import datetime
from typing import Any, Optional

import httpx
from structlog import get_logger

from app.core.config import get_settings
from app.core.security import decrypt_token

logger = get_logger(__name__)
settings = get_settings()


class RazorpayClient:
    """Async client for Razorpay API."""

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = settings.RAZORPAY_BASE_URL
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "RazorpayClient":
        auth_header = f"Basic {base64.b64encode(f'{self.access_token}:'.encode()).decode()}"
        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "User-Agent": "RazorpayAnalytics/1.0",
        }
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=30.0,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()

    async def _request(self, method: str, endpoint: str, params: Optional[dict] = None) -> dict[str, Any]:
        """Make authenticated request to Razorpay API."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        try:
            response = await self._client.request(method, endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error("Razorpay API error", status_code=e.response.status_code, body=e.response.text)
            raise
        except httpx.RequestError as e:
            logger.error("Razorpay request failed", error=str(e))
            raise

    async def fetch_payments(
        self,
        from_date: datetime,
        to_date: datetime,
        count: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch payments within date range."""
        all_payments = []
        skip = 0

        while True:
            params = {
                "from": int(from_date.timestamp()),
                "to": int(to_date.timestamp()),
                "count": min(count, 100),
                "skip": skip,
            }
            result = await self._request("GET", "/payments", params=params)
            payments = result.get("items", [])
            all_payments.extend(payments)

            if len(payments) < count or len(payments) < 100:
                break

            skip += count

        return all_payments

    async def fetch_payment_details(self, payment_id: str) -> dict[str, Any]:
        """Fetch detailed payment information."""
        return await self._request("GET", f"/payments/{payment_id}")

    async def fetch_refunds(self, payment_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Fetch refunds, optionally filtered by payment_id."""
        endpoint = "/refunds"
        params = {"count": 100}
        if payment_id:
            endpoint = f"/payments/{payment_id}/refunds"

        result = await self._request("GET", endpoint, params=params)
        return result.get("items", [])

    async def fetch_settlements(
        self,
        from_date: datetime,
        to_date: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch settlements within date range."""
        params = {
            "from": int(from_date.timestamp()),
            "to": int(to_date.timestamp()),
            "count": 100,
        }
        result = await self._request("GET", "/settlements", params=params)
        return result.get("items", [])

    async def fetch_merchant_profile(self) -> dict[str, Any]:
        """Fetch merchant account profile."""
        return await self._request("GET", "/account")


async def get_razorpay_client(access_token_encrypted: str) -> RazorpayClient:
    """Factory to create Razorpay client with decrypted token."""
    access_token = decrypt_token(access_token_encrypted)
    return RazorpayClient(access_token)
