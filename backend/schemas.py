from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class IssueCreate(BaseModel):
    constituency_id: str
    ward: Optional[str] = None
    mla_name: Optional[str] = None
    complainant_name: Optional[str] = None
    complainant_address: Optional[str] = None
    contact_number: Optional[str] = None
    issue_summary: str = Field(..., min_length=5)
    issue_category: Optional[str] = "Garbage"
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class IssueResponse(BaseModel):
    id: int
    constituency_id: str
    ward: Optional[str]
    mla_name: Optional[str]
    complainant_name: Optional[str]
    complainant_address: Optional[str]
    contact_number: Optional[str]
    issue_summary: str
    issue_category: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    images: Optional[str]
    resolution_photo: Optional[str]
    upvotes: int
    created_at: datetime
    resolved: bool
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


class IssueListResponse(BaseModel):
    issues: list[IssueResponse]
    total: int
    offset: int
    limit: int
    has_more: bool


class ConstituencyInfo(BaseModel):
    id: str
    name: str
    mla: str
    party: str
    color: str
    issue_count: int
    resolved_count: int
    active_count: int
    avg_resolution_hours: Optional[float] = None
    address: Optional[str] = None
    contact_number: Optional[str] = None
    email: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class IssueStats(BaseModel):
    total_reports: int
    total_active: int
    total_resolved: int
    total_upvotes: int


class SubscribeRequest(BaseModel):
    email: str
    constituency_id: Optional[str] = None
    ward: Optional[str] = None


class SubscribeResponse(BaseModel):
    message: str
    unsubscribed: bool = False


class ConstituencyLeaderboard(BaseModel):
    rank: int
    constituency_id: str
    name: str
    mla: str
    party: str
    total_reports: int
    active: int
    resolved: int
    resolution_rate: float
    avg_resolution_hours: Optional[float]
    upvotes: int


class DigestEntry(BaseModel):
    constituency_name: str
    new_issues: int
    resolved_issues: int
    top_category: str
    total_active: int


class WeeklyDigest(BaseModel):
    week_start: str
    week_end: str
    total_new: int
    total_resolved: int
    constituencies: list[DigestEntry]
