"""
API routes for data synchronization.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.api.schemas import SyncTriggerRequest, SyncStatusResponse
from app.core.database import get_db
from app.models import Merchant

logger = get_logger(__name__)
router = APIRouter(prefix="/sync", tags=["Data Sync"])


@router.post("/trigger", response_model=SyncStatusResponse)
async def trigger_sync(
    request: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger manual data synchronization.
    
    Queues a Celery task to sync data from Razorpay.
    """
    import uuid
    
    # Get merchant (in production, extract from JWT)
    result = await db.execute(select(Merchant).limit(1))
    merchant = result.scalar_one_or_none()
    
    if not merchant:
        raise HTTPException(status_code=404, detail="No merchant found")
    
    # Generate task ID
    task_id = str(uuid.uuid4())
    
    # Queue sync task
    from app.services.tasks import sync_merchant_data_task
    
    days = 365 if request.full_sync else 90
    
    background_tasks.add_task(
        sync_merchant_data_task,
        merchant_id=merchant.id,
        days=days,
        task_id=task_id,
    )
    
    logger.info("Sync triggered", merchant_id=merchant.id, task_id=task_id)
    
    return SyncStatusResponse(
        task_id=task_id,
        status="pending",
        message=f"Sync started for last {days} days",
        last_synced_at=merchant.last_synced_at,
    )


@router.get("/status/{task_id}", response_model=SyncStatusResponse)
async def get_sync_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get status of a sync task.
    
    In production, this would query Celery task state.
    For now, returns mock status.
    """
    # Get merchant
    result = await db.execute(select(Merchant).limit(1))
    merchant = result.scalar_one_or_none()
    
    if not merchant:
        raise HTTPException(status_code=404, detail="No merchant found")
    
    # In production, use Celery's AsyncResult
    # from celery.result import AsyncResult
    # task_result = AsyncResult(task_id)
    # status = task_result.status
    
    # Mock status for demo
    return SyncStatusResponse(
        task_id=task_id,
        status="completed",  # Mock
        message="Sync completed successfully",
        last_synced_at=merchant.last_synced_at,
    )
