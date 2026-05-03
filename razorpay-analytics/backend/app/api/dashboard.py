"""
API routes for dashboard and insights.
"""
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.api.schemas import DashboardData, DashboardKPIs, WeeklyInsight, InsightMetric, PaymentResponse
from app.core.database import get_db
from app.models import Merchant, Payment, Refund

logger = get_logger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardData)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
):
    """
    Get dashboard data with KPIs and charts.
    """
    # Get merchant
    result = await db.execute(select(Merchant).limit(1))
    merchant = result.scalar_one_or_none()
    
    if not merchant:
        raise HTTPException(status_code=404, detail="No merchant found")
    
    # Calculate date ranges
    now = datetime.utcnow()
    last_30_days = now - timedelta(days=30)
    previous_30_days = last_30_days - timedelta(days=30)
    
    # Current period metrics
    current_payments = await db.execute(
        select(Payment)
        .where(Payment.merchant_id == merchant.id)
        .where(Payment.created_at >= last_30_days)
    )
    current_payments_list = current_payments.scalars().all()
    
    # Previous period metrics
    previous_payments = await db.execute(
        select(Payment)
        .where(Payment.merchant_id == merchant.id)
        .where(Payment.created_at >= previous_30_days)
        .where(Payment.created_at < last_30_days)
    )
    previous_payments_list = previous_payments.scalars().all()
    
    # Calculate KPIs
    kpis = await calculate_kpis(current_payments_list, previous_payments_list)
    
    # Payments over time (daily)
    payments_over_time = await get_payments_over_time(db, merchant.id, last_30_days)
    
    # Payment method breakdown
    payment_method_breakdown = await get_payment_method_breakdown(db, merchant.id, last_30_days)
    
    # Recent transactions
    recent = await db.execute(
        select(Payment)
        .where(Payment.merchant_id == merchant.id)
        .order_by(Payment.created_at.desc())
        .limit(10)
    )
    recent_transactions = [
        PaymentResponse.model_validate(p)
        for p in recent.scalars().all()
    ]
    
    return DashboardData(
        kpis=kpis,
        payments_over_time=payments_over_time,
        payment_method_breakdown=payment_method_breakdown,
        recent_transactions=recent_transactions,
    )


async def calculate_kpis(
    current_payments: list[Payment],
    previous_payments: list[Payment],
) -> DashboardKPIs:
    """Calculate KPI metrics with comparison."""
    
    def calc_metrics(payments: list[Payment]) -> dict[str, Any]:
        total_amount = sum(p.amount for p in payments)
        successful = [p for p in payments if p.status == "captured"]
        success_count = len(successful)
        total_count = len(payments)
        success_rate = success_count / total_count * 100 if total_count > 0 else 0
        avg_ticket = total_amount / total_count / 100 if total_count > 0 else 0
        
        # Refunds
        refund_amount = sum(r.amount for r in payments if hasattr(r, 'refunds'))  # Simplified
        
        return {
            "gmv": total_amount,
            "success_rate": success_rate,
            "avg_ticket": avg_ticket,
            "refund_rate": refund_amount / total_amount * 100 if total_amount > 0 else 0,
        }
    
    current = calc_metrics(current_payments)
    previous = calc_metrics(previous_payments)
    
    def pct_change(curr: float, prev: float) -> float:
        if prev == 0:
            return 0.0
        return ((curr - prev) / prev) * 100
    
    return DashboardKPIs(
        gmv=current["gmv"],
        gmv_change=pct_change(current["gmv"], previous["gmv"]),
        success_rate=current["success_rate"],
        success_rate_change=pct_change(current["success_rate"], previous["success_rate"]),
        avg_ticket_size=current["avg_ticket"],
        avg_ticket_change=pct_change(current["avg_ticket"], previous["avg_ticket"]),
        refund_rate=current["refund_rate"],
        refund_rate_change=pct_change(current["refund_rate"], previous["refund_rate"]),
    )


async def get_payments_over_time(
    db: AsyncSession,
    merchant_id: str,
    from_date: datetime,
) -> list[dict[str, Any]]:
    """Get daily payment totals for chart."""
    from sqlalchemy import extract
    
    result = await db.execute(
        select(
            extract('year', Payment.created_at).label('year'),
            extract('month', Payment.created_at).label('month'),
            extract('day', Payment.created_at).label('day'),
            func.sum(Payment.amount).label('total'),
            func.count(Payment.id).label('count'),
        )
        .where(Payment.merchant_id == merchant_id)
        .where(Payment.created_at >= from_date)
        .group_by(
            extract('year', Payment.created_at),
            extract('month', Payment.created_at),
            extract('day', Payment.created_at),
        )
        .order_by('year', 'month', 'day')
    )
    
    return [
        {
            "date": f"{int(row.year):04d}-{int(row.month):02d}-{int(row.day):02d}",
            "amount": float(row.total) / 100,  # Convert to rupees
            "count": row.count,
        }
        for row in result.all()
    ]


async def get_payment_method_breakdown(
    db: AsyncSession,
    merchant_id: str,
    from_date: datetime,
) -> list[dict[str, Any]]:
    """Get payment breakdown by method."""
    result = await db.execute(
        select(
            Payment.method,
            func.sum(Payment.amount).label('total'),
            func.count(Payment.id).label('count'),
        )
        .where(Payment.merchant_id == merchant_id)
        .where(Payment.created_at >= from_date)
        .group_by(Payment.method)
        .order_by(func.count(Payment.id).desc())
    )
    
    total = sum(row.count for row in result.all())
    
    return [
        {
            "method": row.method,
            "amount": float(row.total) / 100,
            "count": row.count,
            "percentage": row.count / total * 100 if total > 0 else 0,
        }
        for row in result.all()
    ]


@router.get("/insights/auto", response_model=list[WeeklyInsight])
async def get_auto_insights(
    db: AsyncSession = Depends(get_db),
):
    """
    Get auto-generated weekly insights.
    
    In production, this would be triggered by a cron job.
    """
    from app.services.insights_service import InsightsService
    
    # Get merchant
    result = await db.execute(select(Merchant).limit(1))
    merchant = result.scalar_one_or_none()
    
    if not merchant:
        raise HTTPException(status_code=404, detail="No merchant found")
    
    insights_service = InsightsService(db)
    insights = await insights_service.generate_weekly_insights(merchant)
    
    return insights
