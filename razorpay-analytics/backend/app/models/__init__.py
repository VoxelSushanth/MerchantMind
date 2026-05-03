"""
SQLAlchemy models for the Razorpay Analytics database.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    JSON,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, VECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Merchant(Base):
    """Merchant model - represents a connected Razorpay merchant."""

    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    razorpay_merchant_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    payments = relationship("Payment", back_populates="merchant", cascade="all, delete-orphan")
    refunds = relationship("Refund", back_populates="merchant", cascade="all, delete-orphan")
    embeddings = relationship("Embedding", back_populates="merchant", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="merchant", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Merchant(id={self.id}, name={self.name})>"


class Payment(Base):
    """Payment transaction cache from Razorpay API."""

    __tablename__ = "payments_cache"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    merchant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("merchants.id"), nullable=False, index=True)
    razorpay_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # Amount in paise
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # captured, failed, authorized, refunded
    method: Mapped[str] = mapped_column(String(100), nullable=False)  # card, upi, netbanking, wallet
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fees: Mapped[int] = mapped_column(Integer, nullable=True)  # Razorpay fees in paise
    tax: Mapped[int] = mapped_column(Integer, nullable=True)  # GST in paise
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    merchant = relationship("Merchant", back_populates="payments")
    refunds = relationship("Refund", back_populates="payment", cascade="all, delete-orphan")

    # Indexes for common queries
    __table_args__ = (
        Index("idx_payments_merchant_status", "merchant_id", "status"),
        Index("idx_payments_merchant_created", "merchant_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, amount={self.amount}, status={self.status})>"


class Refund(Base):
    """Refund records linked to payments."""

    __tablename__ = "refunds_cache"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    payment_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("payments_cache.id"), nullable=False, index=True)
    merchant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("merchants.id"), nullable=False, index=True)
    razorpay_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # Refund amount in paise
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # processed, failed, pending
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # Relationships
    merchant = relationship("Merchant", back_populates="refunds")
    payment = relationship("Payment", back_populates="refunds")

    def __repr__(self) -> str:
        return f"<Refund(id={self.id}, amount={self.amount})>"


class Embedding(Base):
    """Vector embeddings for RAG over transaction summaries."""

    __tablename__ = "embeddings"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    merchant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("merchants.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(VECTOR(1536), nullable=True)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship
    merchant = relationship("Merchant", back_populates="embeddings")

    # Index for vector similarity search
    __table_args__ = (
        Index("idx_embeddings_merchant_period", "merchant_id", "period_start", "period_end"),
    )

    def __repr__(self) -> str:
        return f"<Embedding(id={self.id}, period={self.period_start} to {self.period_end})>"


class Conversation(Base):
    """Conversation history for chat interface."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    merchant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("merchants.id"), nullable=False, index=True)
    messages: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    merchant = relationship("Merchant", back_populates="conversations")

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, merchant_id={self.merchant_id})>"
