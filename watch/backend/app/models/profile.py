from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid
import enum


class OrgType(str, enum.Enum):
    academic = "academic"
    sme = "sme"
    large_enterprise = "large_enterprise"
    startup = "startup"
    ngo = "ngo"
    public_authority = "public_authority"
    consortium = "consortium"


class CollaborationPref(str, enum.Enum):
    solo = "solo"
    open = "open"
    required = "required"


class DeadlineHorizon(str, enum.Enum):
    m3 = "3m"
    m6 = "6m"
    m12 = "12m"
    any = "any"


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True)
    org_type = Column(Enum(OrgType), nullable=True)
    country = Column(String(2), nullable=True)
    trl_min = Column(Integer, nullable=True)
    trl_max = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    context_url = Column(Text, nullable=True)
    context_text = Column(Text, nullable=True)
    matcher_profile_hash = Column(String(64), nullable=True)
    context_last_fetched_at = Column(DateTime(timezone=True), nullable=True)
    focus_domains = Column(JSON, nullable=True)
    problem_frames = Column(JSON, nullable=True)
    funding_types = Column(JSON, nullable=True)
    collaboration = Column(JSON, nullable=True)  # list of CollaborationPref values, e.g. ["solo", "open"]
    budget_min = Column(Integer, nullable=True)
    budget_max = Column(Integer, nullable=True)
    deadline_horizon = Column(Enum(DeadlineHorizon), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="profile")
