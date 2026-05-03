"""
Pydantic schemas for API request/response validation.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============== Auth Schemas ==============

class RazorpayOAuthCallback(BaseModel):
    """Schema for Razorpay OAuth callback."""
    code: str
    state: Optional[str] = None


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    merchant_id: str


# ============== Merchant Schemas ==============

class MerchantBase(BaseModel):
    """Base merchant schema."""
    name: str
    email: str


class MerchantCreate(MerchantBase):
    """Schema for creating a merchant."""
    razorpay_merchant_id: str
    access_token_encrypted: str


class MerchantResponse(MerchantBase):
    """Schema for merchant response."""
    id: str
    razorpay_merchant_id: str
    last_synced_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ============== Payment Schemas ==============

class PaymentSummary(BaseModel):
    """Payment summary for dashboard."""
    total_payments: int
    total_amount: int  # in paise
    successful_payments: int
    failed_payments: int
    success_rate: float
    avg_ticket_size: float  # in rupees


class PaymentResponse(BaseModel):
    """Individual payment response."""
    id: str
    razorpay_id: str
    amount: int
    status: str
    method: str
    created_at: datetime
    currency: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


# ============== Refund Schemas ==============

class RefundSummary(BaseModel):
    """Refund summary for dashboard."""
    total_refunds: int
    total_refund_amount: int  # in paise
    refund_rate: float  # percentage of GMV


class RefundResponse(BaseModel):
    """Individual refund response."""
    id: str
    razorpay_id: str
    amount: int
    reason: Optional[str] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ============== Query Schemas ==============

class QueryRequest(BaseModel):
    """Natural language query request."""
    question: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = None


class SQLResult(BaseModel):
    """SQL execution result."""
    sql: str
    explanation: str
    rows: list[dict[str, Any]]
    row_count: int


class SemanticChunk(BaseModel):
    """Retrieved semantic chunk from RAG."""
    content: str
    period_start: datetime
    period_end: datetime
    similarity_score: float


class QueryResponse(BaseModel):
    """Query response with answer and citations."""
    answer: str
    sql_results: Optional[SQLResult] = None
    semantic_chunks: list[SemanticChunk] = []
    conversation_id: str
    streaming: bool = False


# ============== Sync Schemas ==============

class SyncTriggerRequest(BaseModel):
    """Request to trigger data sync."""
    full_sync: bool = False  # If True, sync all available data; otherwise last 90 days


class SyncStatusResponse(BaseModel):
    """Sync job status response."""
    task_id: str
    status: str  # pending, started, completed, failed
    message: str
    last_synced_at: Optional[datetime] = None


# ============== Conversation Schemas ==============

class Message(BaseModel):
    """Chat message."""
    role: str  # user, assistant, system
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConversationResponse(BaseModel):
    """Conversation history response."""
    id: str
    merchant_id: str
    messages: list[Message]
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============== Insights Schemas ==============

class InsightMetric(BaseModel):
    """Single metric in an insight."""
    name: str
    value: float
    change_percent: Optional[float] = None
    trend: str  # up, down, flat


class WeeklyInsight(BaseModel):
    """Auto-generated weekly insight."""
    period_start: datetime
    period_end: datetime
    summary: str
    metrics: list[InsightMetric]
    anomalies: list[str] = []
    recommendations: list[str] = []


# ============== Dashboard Schemas ==============

class DashboardKPIs(BaseModel):
    """Dashboard KPI cards."""
    gmv: int  # Gross Merchandise Value in paise
    gmv_change: float
    success_rate: float
    success_rate_change: float
    avg_ticket_size: float  # in rupees
    avg_ticket_change: float
    refund_rate: float
    refund_rate_change: float


class DashboardData(BaseModel):
    """Complete dashboard data."""
    kpis: DashboardKPIs
    payments_over_time: list[dict[str, Any]]
    payment_method_breakdown: list[dict[str, Any]]
    recent_transactions: list[PaymentResponse]
