from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid

class SeenCall(Base):
    __tablename__ = "seen_calls"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id = Column(String(36), ForeignKey("sources.id"), nullable=False)
    call_hash = Column(String, nullable=False)
    title = Column(String)
    url = Column(String)
    deadline = Column(String)
    summary = Column(Text)
    relevance_score = Column(Integer, nullable=True)
    relevance_reason = Column(Text, nullable=True)
    scored_at = Column(DateTime(timezone=True), nullable=True)
    scored_profile_hash = Column(String(64), nullable=True)
    first_seen = Column(DateTime(timezone=True), server_default=func.now())

    source = relationship("Source", back_populates="seen_calls")
    feedback = relationship("CallFeedback", back_populates="seen_call", cascade="all, delete")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    source_id = Column(String(36), ForeignKey("sources.id"))
    call_title = Column(String)
    call_url = Column(String)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="alerts")


class CallFeedback(Base):
    __tablename__ = "call_feedback"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    seen_call_id = Column(String(36), ForeignKey("seen_calls.id"), nullable=False, index=True)
    label = Column(String(20), nullable=False)  # "relevant" | "not_relevant"
    reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="call_feedback")
    seen_call = relationship("SeenCall", back_populates="feedback")
