from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid

class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (
        Index("ix_sources_origin_country_code", "origin_country_code"),
        Index("ix_sources_user_country", "user_id", "origin_country_code"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    url = Column(String, nullable=False)
    label = Column(String)
    keywords = Column(JSON, default=list)
    fetch_mode = Column(String, default="fetch")
    crawl_config = Column(JSON, nullable=True)
    origin_country_code = Column(String(2), nullable=True)
    is_active = Column(Boolean, default=True)
    last_checked = Column(DateTime(timezone=True))
    last_status = Column(String, default="pending")  # "pending" | "ok" | "error"
    last_error = Column(String)                       # error message if last check failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="sources")
    seen_calls = relationship("SeenCall", back_populates="source", cascade="all, delete")
