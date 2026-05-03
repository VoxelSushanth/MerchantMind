"""
Data ingestion service for syncing Razorpay data.
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.models import Merchant, Payment, Refund, Embedding
from app.services.razorpay_client import RazorpayClient

logger = get_logger(__name__)


class DataIngestionService:
    """Service for syncing data from Razorpay API to local database."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def sync_merchant_data(
        self,
        merchant: Merchant,
        razorpay_client: RazorpayClient,
        days: int = 90,
    ) -> dict[str, int]:
        """
        Sync payments and refunds for a merchant.
        
        Returns counts of synced records.
        """
        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=days)

        logger.info(
            "Starting data sync",
            merchant_id=merchant.id,
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
        )

        # Sync payments
        payments_count = await self._sync_payments(merchant, razorpay_client, from_date, to_date)

        # Sync refunds
        refunds_count = await self._sync_refunds(merchant, razorpay_client)

        # Update last_synced_at
        merchant.last_synced_at = datetime.utcnow()
        await self.db.merge(merchant)
        await self.db.commit()

        # Generate embeddings for the synced period
        await self._generate_periodic_embeddings(merchant, from_date, to_date)

        logger.info(
            "Data sync completed",
            merchant_id=merchant.id,
            payments_count=payments_count,
            refunds_count=refunds_count,
        )

        return {
            "payments": payments_count,
            "refunds": refunds_count,
        }

    async def _sync_payments(
        self,
        merchant: Merchant,
        client: RazorpayClient,
        from_date: datetime,
        to_date: datetime,
    ) -> int:
        """Sync payments from Razorpay API."""
        raw_payments = await client.fetch_payments(from_date, to_date)

        count = 0
        for raw_payment in raw_payments:
            payment_id = raw_payment.get("id")

            # Check if already exists
            existing = await self.db.execute(
                select(Payment).where(Payment.razorpay_id == payment_id)
            )
            if existing.scalar_one_or_none():
                continue

            # Create payment record
            payment = Payment(
                merchant_id=merchant.id,
                razorpay_id=payment_id,
                amount=raw_payment.get("amount", 0),
                status=raw_payment.get("status", "unknown"),
                method=raw_payment.get("method", "unknown"),
                created_at=datetime.fromtimestamp(raw_payment.get("created_at", 0)),
                settled_at=(
                    datetime.fromtimestamp(raw_payment["settled_at"])
                    if raw_payment.get("settled_at")
                    else None
                ),
                fees=raw_payment.get("fee"),
                tax=raw_payment.get("tax"),
                currency=raw_payment.get("currency", "INR"),
                description=raw_payment.get("description"),
                metadata_json=raw_payment.get("metadata"),
            )
            self.db.add(payment)
            count += 1

            # Flush every 100 records
            if count % 100 == 0:
                await self.db.flush()

        await self.db.commit()
        return count

    async def _sync_refunds(
        self,
        merchant: Merchant,
        client: RazorpayClient,
    ) -> int:
        """Sync refunds from Razorpay API."""
        raw_refunds = await client.fetch_refunds()

        count = 0
        for raw_refund in raw_refunds:
            refund_id = raw_refund.get("id")
            payment_id = raw_refund.get("payment_id")

            # Check if already exists
            existing = await self.db.execute(
                select(Refund).where(Refund.razorpay_id == refund_id)
            )
            if existing.scalar_one_or_none():
                continue

            # Find associated payment
            payment = None
            if payment_id:
                payment_result = await self.db.execute(
                    select(Payment).where(Payment.razorpay_id == payment_id)
                )
                payment = payment_result.scalar_one_or_none()

            # Create refund record
            refund = Refund(
                payment_id=payment.id if payment else None,
                merchant_id=merchant.id,
                razorpay_id=refund_id,
                amount=raw_refund.get("amount", 0),
                reason=raw_refund.get("reason"),
                status=raw_refund.get("status", "unknown"),
                created_at=datetime.fromtimestamp(raw_refund.get("created_at", 0)),
            )
            self.db.add(refund)
            count += 1

            # Flush every 50 records
            if count % 50 == 0:
                await self.db.flush()

        await self.db.commit()
        return count

    async def _generate_periodic_embeddings(
        self,
        merchant: Merchant,
        from_date: datetime,
        to_date: datetime,
    ) -> None:
        """
        Generate summary embeddings for time periods.
        Creates weekly rollups for efficient RAG retrieval.
        """
        # This will be implemented with LangChain embeddings
        # For now, create placeholder summaries
        from app.services.embeddings_service import EmbeddingsService

        embedding_service = EmbeddingsService(self.db)
        await embedding_service.generate_period_summaries(merchant, from_date, to_date)
