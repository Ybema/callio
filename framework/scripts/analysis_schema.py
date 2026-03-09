"""
Strict JSON schema for LFA analysis results.
Enforces 30/50/20 scoring model with evidence-anchored findings.
"""

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, validator
from enum import Enum


class SeverityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PatchOperation(str, Enum):
    REPLACE = "replace"
    INSERT = "insert"
    UPDATE_DATE = "update_date"
    ADD_NODES = "add_nodes"


class EvidenceType(str, Enum):
    SEMANTIC_SIM = "semantic_sim"
    KEYWORD_GAP = "keyword_gap"
    STRUCTURE_CHECK = "structure_check"
    READABILITY_SCORE = "readability_score"
    DATE_RANGE_CHECK = "date_range_check"
    SMART_COMPLETENESS = "smart_completeness"


class Evidence(BaseModel):
    type: EvidenceType
    score: Optional[float] = None
    call_ref_id: Optional[str] = None
    missing_terms: Optional[List[str]] = None
    details: Optional[Dict[str, Any]] = None


class Location(BaseModel):
    section: str
    start: int
    end: int


class Patch(BaseModel):
    op: PatchOperation
    target: str
    start: int
    end: int
    text: str


class ScoreImpact(BaseModel):
    delta: float
    affects: List[str]


class Finding(BaseModel):
    id: str
    criterion: str
    severity: SeverityLevel
    confidence: float = Field(ge=0.0, le=1.0)
    location: Location
    quote: str = Field(max_length=30)
    issue: str
    evidence: List[Evidence]
    recommendation: str
    suggested_rewrite: Optional[str] = None
    patch: Optional[Patch] = None
    score_impact: Optional[ScoreImpact] = None


class CriterionScore(BaseModel):
    id: str
    name: str
    weight: float = Field(ge=0.0, le=1.0)
    score: float = Field(ge=0.0, le=100.0)
    findings: List[str]  # Finding IDs


class CategoryScore(BaseModel):
    score: float = Field(ge=0.0, le=100.0)
    weight: float = Field(ge=0.0, le=1.0)
    calc: str


class OverallScore(BaseModel):
    score: float = Field(ge=0.0, le=100.0)
    formula: str


class Scores(BaseModel):
    call_alignment: CategoryScore
    internal_consistency: CategoryScore
    content_quality: CategoryScore
    overall: OverallScore


class Criteria(BaseModel):
    call_alignment: List[CriterionScore]
    internal_consistency: List[CriterionScore]
    content_quality: List[CriterionScore]


class CalcTrace(BaseModel):
    CA1: Optional[str] = None
    CA2: Optional[str] = None
    CA3: Optional[str] = None
    CA4: Optional[str] = None
    CA5: Optional[str] = None
    CA6: Optional[str] = None
    LC1: Optional[str] = None
    LC2: Optional[str] = None
    LC3: Optional[str] = None
    LC4: Optional[str] = None
    LC5: Optional[str] = None
    LC6: Optional[str] = None
    LC7: Optional[str] = None
    LC8: Optional[str] = None
    CQ1: Optional[str] = None
    CQ2: Optional[str] = None
    CQ3: Optional[str] = None
    CQ4: Optional[str] = None
    overall: str


class Meta(BaseModel):
    project: str
    analysis_date: str
    version: str
    method: str
    doc_hash: str


class LFAAnalysisResult(BaseModel):
    meta: Meta
    scores: Scores
    criteria: Criteria
    findings: List[Finding]
    calc_trace: CalcTrace

    @validator('scores')
    def validate_weights(cls, v):
        """Ensure weights sum to 1.0"""
        total_weight = v.call_alignment.weight + v.internal_consistency.weight + v.content_quality.weight
        if abs(total_weight - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total_weight}")
        return v

    @validator('criteria')
    def validate_criteria_weights(cls, v):
        """Ensure criterion weights within each category sum to 1.0"""
        for category in [v.call_alignment, v.internal_consistency, v.content_quality]:
            total_weight = sum(c.weight for c in category)
            if abs(total_weight - 1.0) > 0.001:
                raise ValueError(f"Category weights must sum to 1.0, got {total_weight}")
        return v

    def get_overall_score(self) -> float:
        """Calculate overall score using the 30/50/20 formula"""
        return (
            self.scores.call_alignment.score * self.scores.call_alignment.weight +
            self.scores.internal_consistency.score * self.scores.internal_consistency.weight +
            self.scores.content_quality.score * self.scores.content_quality.weight
        )

    def get_quality_level(self, score: float) -> str:
        """Convert score to quality level"""
        if score >= 85:
            return "EXCELLENT"
        elif score >= 70:
            return "GOOD"
        elif score >= 55:
            return "FAIR"
        elif score >= 40:
            return "NEEDS_WORK"
        else:
            return "POOR"
