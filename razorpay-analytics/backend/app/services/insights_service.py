"""
Insights service for auto-generating weekly narratives.
"""
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.api.schemas import WeeklyInsight, InsightMetric
from app.models import Merchant, Payment, Refund

logger = get_logger(__name__)


class InsightsService:
    """Service for generating automated insights."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_weekly_insights(
        self,
        merchant: Merchant,
        weeks: int = 4,
    ) -> list[WeeklyInsight]:
        """Generate weekly insights for the past N weeks."""
        insights = []
        now = datetime.utcnow()
        
        for week_offset in range(weeks):
            period_end = now - timedelta(weeks=week_offset)
            period_start = period_end - timedelta(weeks=1)
            
            insight = await self._generate_single_insight(
                merchant, period_start, period_end
            )
            if insight:
                insights.append(insight)
        
        return insights

    async def _generate_single_insight(
        self,
        merchant: Merchant,
        period_start: datetime,
        period_end: datetime,
    ) -> WeeklyInsight | None:
        """Generate insight for a single week."""
        # Fetch metrics
        metrics_data = await self._calculate_weekly_metrics(merchant, period_start, period_end)
        
        if not metrics_data or metrics_data.get("total_payments", 0) == 0:
            return None
        
        # Generate narrative using LLM
        summary = await self._generate_narrative(metrics_data)
        
        # Detect anomalies
        anomalies = await self._detect_anomalies(merchant, metrics_data, period_start)
        
        # Generate recommendations
        recommendations = await self._generate_recommendations(metrics_data, anomalies)
        
        # Build metric objects
        metrics = [
            InsightMetric(
                name="GMV",
                value=metrics_data.get("gmv", 0) / 100,  # Convert to rupees
                change_percent=metrics_data.get("gmv_change", 0),
                trend="up" if metrics_data.get("gmv_change", 0) > 0 else "down",
            ),
            InsightMetric(
                name="Success Rate",
                value=metrics_data.get("success_rate", 0),
                change_percent=metrics_data.get("success_rate_change", 0),
                trend="up" if metrics_data.get("success_rate_change", 0) > 0 else "down",
            ),
            InsightMetric(
                name="Avg Ticket",
                value=metrics_data.get("avg_ticket", 0),
                change_percent=metrics_data.get("avg_ticket_change", 0),
                trend="up" if metrics_data.get("avg_ticket_change", 0) > 0 else "down",
            ),
            InsightMetric(
                name="Refund Rate",
                value=metrics_data.get("refund_rate", 0),
                change_percent=metrics_data.get("refund_rate_change", 0),
                trend="down" if metrics_data.get("refund_rate_change", 0) < 0 else "up",  # Lower is better
            ),
        ]
        
        return WeeklyInsight(
            period_start=period_start,
            period_end=period_end,
            summary=summary,
            metrics=metrics,
            anomalies=anomalies,
            recommendations=recommendations,
        )

    async def _calculate_weekly_metrics(
        self,
        merchant: Merchant,
        period_start: datetime,
        period_end: datetime,
    ) -> dict[str, Any]:
        """Calculate all metrics for a week."""
        # Current period payments
        current_result = await self.db.execute(
            select(Payment)
            .where(Payment.merchant_id == merchant.id)
            .where(Payment.created_at >= period_start)
            .where(Payment.created_at < period_end)
        )
        current_payments = current_result.scalars().all()
        
        # Previous period (for comparison)
        duration = period_end - period_start
        prev_start = period_start - duration
        prev_end = period_start
        
        prev_result = await self.db.execute(
            select(Payment)
            .where(Payment.merchant_id == merchant.id)
            .where(Payment.created_at >= prev_start)
            .where(Payment.created_at < prev_end)
        )
        prev_payments = prev_result.scalars().all()
        
        def calc(payment_list: list[Payment]) -> dict[str, Any]:
            total_amount = sum(p.amount for p in payment_list)
            successful = [p for p in payment_list if p.status == "captured"]
            count = len(payment_list)
            success_rate = len(successful) / count * 100 if count > 0 else 0
            avg_ticket = total_amount / count / 100 if count > 0 else 0
            
            return {
                "gmv": total_amount,
                "count": count,
                "success_rate": success_rate,
                "avg_ticket": avg_ticket,
            }
        
        current = calc(current_payments)
        previous = calc(prev_payments)
        
        def pct_change(curr: float, prev: float) -> float:
            if prev == 0:
                return 0.0
            return ((curr - prev) / prev) * 100
        
        # Calculate refund rate
        refund_result = await self.db.execute(
            select(func.sum(Refund.amount))
            .where(Refund.merchant_id == merchant.id)
            .where(Refund.created_at >= period_start)
            .where(Refund.created_at < period_end)
        )
        refund_total = refund_result.scalar() or 0
        refund_rate = refund_total / current["gmv"] * 100 if current["gmv"] > 0 else 0
        
        return {
            "gmv": current["gmv"],
            "gmv_change": pct_change(current["gmv"], previous["gmv"]),
            "payment_count": current["count"],
            "success_rate": current["success_rate"],
            "success_rate_change": pct_change(current["success_rate"], previous["success_rate"]),
            "avg_ticket": current["avg_ticket"],
            "avg_ticket_change": pct_change(current["avg_ticket"], previous["avg_ticket"]),
            "refund_rate": refund_rate,
        }

    async def _generate_narrative(self, metrics: dict[str, Any]) -> str:
        """Generate natural language summary using LLM."""
        from langchain_anthropic import ChatAnthropic
        from app.core.config import get_settings
        
        llm = ChatAnthropic(
            model=get_settings().ANTHROPIC_MODEL,
            temperature=0.3,
            max_tokens=500,
        )
        
        prompt = f"""Generate a concise 2-3 sentence summary of this week's payment performance:
- GMV: ₹{metrics.get('gmv', 0)/100:,.2f} ({metrics.get('gmv_change', 0):+.1f}% vs last week)
- Payments: {metrics.get('payment_count', 0)} transactions
- Success Rate: {metrics.get('success_rate', 0):.1f}%
- Average Ticket: ₹{metrics.get('avg_ticket', 0):.2f}
- Refund Rate: {metrics.get('refund_rate', 0):.2f}%

Focus on the most notable changes and what they might indicate."""

        response = await llm.ainvoke(prompt)
        return response.content

    async def _detect_anomalies(
        self,
        merchant: Merchant,
        current_metrics: dict[str, Any],
        period_start: datetime,
    ) -> list[str]:
        """Detect unusual patterns in the data."""
        anomalies = []
        
        # Check for significant drops in success rate
        if current_metrics.get("success_rate_change", 0) < -10:
            anomalies.append(
                f"Success rate dropped significantly ({current_metrics.get('success_rate_change', 0):.1f}%)"
            )
        
        # Check for unusual refund rate
        if current_metrics.get("refund_rate", 0) > 5:
            anomalies.append(
                f"High refund rate detected ({current_metrics.get('refund_rate', 0):.2f}%)"
            )
        
        # Check for GMV spike or drop
        gmv_change = current_metrics.get("gmv_change", 0)
        if abs(gmv_change) > 50:
            direction = "spike" if gmv_change > 0 else "drop"
            anomalies.append(f"Unusual GMV {direction} ({gmv_change:+.1f}%)")
        
        return anomalies

    async def _generate_recommendations(
        self,
        metrics: dict[str, Any],
        anomalies: list[str],
    ) -> list[str]:
        """Generate actionable recommendations based on metrics."""
        recommendations = []
        
        if metrics.get("success_rate", 0) < 90:
            recommendations.append(
                "Consider analyzing failed payments by method to identify technical issues"
            )
        
        if metrics.get("refund_rate", 0) > 3:
            recommendations.append(
                "Review refund reasons to identify product or service issues"
            )
        
        if metrics.get("gmv_change", 0) < -20:
            recommendations.append(
                "Investigate the GMV decline - consider running a promotion or outreach campaign"
            )
        
        if not anomalies and metrics.get("success_rate", 0) > 95:
            recommendations.append(
                "Performance is strong - consider optimizing for conversion rate improvement"
            )
        
        return recommendations
