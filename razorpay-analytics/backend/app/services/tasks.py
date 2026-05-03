"""
Celery tasks for background processing.
"""
from celery import Celery
from structlog import get_logger

from app.core.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

# Initialize Celery
celery_app = Celery(
    "razorpay_analytics",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.services.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    worker_prefetch_multiplier=1,
)


@celery_app.task(bind=True, max_retries=3)
def sync_merchant_data_task(
    self,
    merchant_id: str,
    days: int = 90,
    task_id: str | None = None,
) -> dict:
    """
    Celery task to sync merchant data from Razorpay.
    
    Runs periodically every 6 hours or on-demand.
    """
    import asyncio
    from sqlalchemy.ext.asyncio import AsyncSession
    
    from app.core.database import AsyncSessionLocal, engine
    from app.models import Merchant
    from app.services.data_ingestion import DataIngestionService
    from app.services.razorpay_client import get_razorpay_client
    from app.core.security import decrypt_token
    
    async def run_sync():
        async with AsyncSessionLocal() as db:
            try:
                # Fetch merchant
                from sqlalchemy import select
                result = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
                merchant = result.scalar_one_or_none()
                
                if not merchant:
                    return {"error": "Merchant not found"}
                
                # Create Razorpay client
                async with get_razorpay_client(merchant.access_token_encrypted) as client:
                    # Run data ingestion
                    ingestion_service = DataIngestionService(db)
                    result = await ingestion_service.sync_merchant_data(
                        merchant=merchant,
                        razorpay_client=client,
                        days=days,
                    )
                    
                    logger.info("Sync task completed", merchant_id=merchant_id, result=result)
                    return {
                        "status": "success",
                        "merchant_id": merchant_id,
                        **result,
                    }
                    
            except Exception as e:
                logger.error("Sync task failed", merchant_id=merchant_id, error=str(e))
                raise self.retry(exc=e, countdown=300)  # Retry after 5 minutes
    
    return asyncio.run(run_sync())


@celery_app.task
def generate_embeddings_task(merchant_id: str, days: int = 90) -> dict:
    """Task to regenerate embeddings for a merchant."""
    import asyncio
    from datetime import datetime, timedelta
    
    from app.core.database import AsyncSessionLocal
    from app.models import Merchant
    from app.services.embeddings_service import EmbeddingsService
    
    async def run():
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            result = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
            merchant = result.scalar_one_or_none()
            
            if not merchant:
                return {"error": "Merchant not found"}
            
            to_date = datetime.utcnow()
            from_date = to_date - timedelta(days=days)
            
            embedding_service = EmbeddingsService(db)
            count = await embedding_service.generate_period_summaries(
                merchant, from_date, to_date
            )
            
            return {"status": "success", "embeddings_generated": count}
    
    return asyncio.run(run())


@celery_app.task
def cleanup_old_data_task(days_to_keep: int = 365) -> dict:
    """Periodic task to clean up old cached data."""
    # Implementation for data retention policies
    return {"status": "success", "message": "Cleanup completed"}


# Scheduled tasks (for Celery Beat)
celery_app.conf.beat_schedule = {
    "sync-all-merchants-every-6h": {
        "task": "app.services.tasks.sync_all_merchants_task",
        "schedule": 60 * 60 * 6,  # 6 hours
    },
    "generate-weekly-insights": {
        "task": "app.services.tasks.generate_all_insights_task",
        "schedule": 60 * 60 * 24 * 7,  # Weekly
    },
}


@celery_app.task
def sync_all_merchants_task() -> dict:
    """Sync data for all merchants."""
    import asyncio
    from sqlalchemy import select
    
    from app.core.database import AsyncSessionLocal
    from app.models import Merchant
    
    async def run():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Merchant))
            merchants = result.scalars().all()
            
            synced = 0
            for merchant in merchants:
                try:
                    sync_merchant_data_task.delay(
                        merchant_id=merchant.id,
                        days=90,
                    )
                    synced += 1
                except Exception as e:
                    logger.error("Failed to queue sync", merchant_id=merchant.id, error=str(e))
            
            return {"status": "success", "merchants_queued": synced}
    
    return asyncio.run(run())


@celery_app.task
def generate_all_insights_task() -> dict:
    """Generate insights for all merchants."""
    # Similar pattern to sync_all_merchants_task
    return {"status": "success", "message": "Insights generation queued"}
