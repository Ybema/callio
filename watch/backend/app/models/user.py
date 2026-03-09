from sqlalchemy import Column, String, Boolean, DateTime, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid
import enum

class PlanTier(str, enum.Enum):
    free = "free"
    pro = "pro"
    team = "team"

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    plan = Column(Enum(PlanTier), default=PlanTier.free)
    stripe_customer_id = Column(String, unique=True)
    stripe_subscription_id = Column(String)
    alert_last_error = Column(String)
    alert_last_error_at = Column(DateTime(timezone=True))
    alert_last_ok_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sources = relationship("Source", back_populates="user", cascade="all, delete")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete")
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete")
    call_feedback = relationship("CallFeedback", back_populates="user", cascade="all, delete")
