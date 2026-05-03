"""
Embeddings service for RAG pipeline.
Generates and stores vector embeddings of transaction summaries.
"""
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.models import Merchant, Payment, Refund, Embedding
from app.core.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class EmbeddingsService:
    """Service for generating and querying embeddings."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._embedding_model = None  # Lazy load

    async def _get_embedding(self, text: str) -> list[float]:
        """Generate embedding for text using configured model."""
        # In production, use OpenAI or other embedding API
        # For now, return placeholder (will be replaced with actual API call)
        try:
            from langchain_openai import OpenAIEmbeddings
            
            if self._embedding_model is None:
                self._embedding_model = OpenAIEmbeddings(
                    model=settings.EMBEDDINGS_MODEL,
                    dimensions=settings.EMBEDDINGS_DIMENSION,
                )
            
            embedding = self._embedding_model.embed_query(text)
            return embedding
        except Exception as e:
            logger.warning("Embedding generation failed, using placeholder", error=str(e))
            # Return zero vector as fallback
            return [0.0] * settings.EMBEDDINGS_DIMENSION

    async def generate_period_summaries(
        self,
        merchant: Merchant,
        from_date: datetime,
        to_date: datetime,
    ) -> int:
        """
        Generate weekly summary embeddings for a date range.
        
        Each summary contains aggregated metrics for the period.
        """
        count = 0
        current_date = from_date

        while current_date < to_date:
            period_end = min(current_date + timedelta(days=7), to_date)

            # Generate summary for this period
            summary = await self._generate_weekly_summary(merchant, current_date, period_end)
            
            if summary:
                # Create embedding record
                embedding_vector = await self._get_embedding(summary)
                
                embedding = Embedding(
                    merchant_id=merchant.id,
                    content=summary,
                    embedding=embedding_vector,
                    period_start=current_date,
                    period_end=period_end,
                    metadata_json={
                        "type": "weekly_summary",
                        "generated_at": datetime.utcnow().isoformat(),
                    },
                )
                self.db.add(embedding)
                count += 1

            current_date = period_end

        await self.db.commit()
        logger.info("Generated period embeddings", merchant_id=merchant.id, count=count)
        return count

    async def _generate_weekly_summary(
        self,
        merchant: Merchant,
        start: datetime,
        end: datetime,
    ) -> Optional[str]:
        """Generate natural language summary of weekly metrics."""
        # Query payments for this period
        result = await self.db.execute(
            select(Payment)
            .where(Payment.merchant_id == merchant.id)
            .where(Payment.created_at >= start)
            .where(Payment.created_at < end)
        )
        payments = result.scalars().all()

        if not payments:
            return None

        # Calculate metrics
        total_amount = sum(p.amount for p in payments)
        successful = [p for p in payments if p.status == "captured"]
        failed = [p for p in payments if p.status == "failed"]
        success_rate = len(successful) / len(payments) * 100 if payments else 0
        avg_ticket = total_amount / len(payments) / 100 if payments else 0  # Convert to rupees

        # Group by payment method
        method_counts = {}
        for p in payments:
            method_counts[p.method] = method_counts.get(p.method, 0) + 1

        top_method = max(method_counts.items(), key=lambda x: x[1])[0] if method_counts else "unknown"

        # Query refunds
        refund_result = await self.db.execute(
            select(Refund)
            .where(Refund.merchant_id == merchant.id)
            .where(Refund.created_at >= start)
            .where(Refund.created_at < end)
        )
        refunds = refund_result.scalars().all()
        total_refund_amount = sum(r.amount for r in refunds)
        refund_rate = total_refund_amount / total_amount * 100 if total_amount > 0 else 0

        summary = (
            f"Week from {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}: "
            f"Processed {len(payments)} payments totaling ₹{total_amount/100:,.2f}. "
            f"Success rate was {success_rate:.1f}% ({len(successful)} successful, {len(failed)} failed). "
            f"Average ticket size was ₹{avg_ticket:.2f}. "
            f"Most used payment method was {top_method} ({method_counts.get(top_method, 0)} transactions). "
            f"Refunds totaled ₹{total_refund_amount/100:.2f} ({refund_rate:.2f}% of GMV)."
        )

        return summary

    async def similarity_search(
        self,
        merchant_id: str,
        query: str,
        k: int = 5,
    ) -> list[tuple[Embedding, float]]:
        """
        Find most similar embeddings for a query.
        
        Uses pgvector cosine similarity.
        """
        # Generate query embedding
        query_embedding = await self._get_embedding(query)

        # Use pgvector cosine similarity
        # Note: This requires pgvector extension installed
        from sqlalchemy import text
        
        embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
        
        stmt = text("""
            SELECT id, merchant_id, content, embedding, period_start, period_end, metadata_json,
                   1 - (embedding <=> :embedding::vector) as similarity
            FROM embeddings
            WHERE merchant_id = :merchant_id
            ORDER BY embedding <=> :embedding::vector
            LIMIT :k
        """)
        
        result = await self.db.execute(
            stmt,
            {"embedding": embedding_str, "merchant_id": merchant_id, "k": k}
        )
        
        results = []
        for row in result:
            embedding = Embedding(
                id=row[0],
                merchant_id=row[1],
                content=row[2],
                embedding=row[3],
                period_start=row[4],
                period_end=row[5],
                metadata_json=row[6],
            )
            similarity = float(row[7])
            results.append((embedding, similarity))

        return results

    async def delete_merchant_embeddings(self, merchant_id: str) -> None:
        """Delete all embeddings for a merchant."""
        await self.db.execute(
            delete(Embedding).where(Embedding.merchant_id == merchant_id)
        )
        await self.db.commit()
