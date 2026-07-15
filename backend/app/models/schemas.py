from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(default="Executive Analytics Workspace", min_length=1, max_length=120)
    description: str | None = None






class ChatAttachment(BaseModel):
    kind: str = Field(default="context", min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=200)
    context: str = Field(min_length=1, max_length=12000)
    artifact_id: str | None = None


class ChatRequest(BaseModel):
    dataset_id: str
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    attachments: list[ChatAttachment] = Field(default_factory=list, max_length=3)


class ChatResponse(BaseModel):
    answer: str
    evidence: list[str]
    sql: str | None = None
    data: list[dict[str, Any]] = []
    chart: dict[str, Any] | None = None
    confidence: float = 0.0
    mode: str | None = None
    active_skill: str | None = None
    artifact: dict[str, Any] | None = None
    chat_message_id: str | None = None


class ReportBlockRequest(BaseModel):
    key: str
    label: str
    description: str | None = None
    required: bool = False
    kind: Literal[
        "summary", "narrative", "metrics", "findings", "chart", "actions",
        "comparison", "table", "key_value", "bullets", "references", "callout",
    ] | None = None
    presentation: dict[str, Any] | None = None
    data_fields: list[str] = Field(default_factory=list)
    chart_intent: str | None = None


class ReportRequest(BaseModel):
    dataset_id: str
    audience: str = "Leadership team"
    goal: str = "Identify risks, opportunities, and next actions"
    horizon: str = "Next quarter"
    tone: Literal["Board-ready", "Strategic", "Operational", "Technical"] = "Strategic"
    focus_areas: list[str] = Field(default_factory=lambda: ["growth", "risk", "quality"])
    template: str = "executive"
    report_type: str | None = None
    blocks: list[str] | None = None
    custom_blocks: list[ReportBlockRequest] | None = None
    approved_plan: dict[str, Any] | None = None


class ReportTypePayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    audience: str = Field(default="Leadership team", max_length=200)
    goal: str = Field(default="Identify risks, opportunities, and next actions", max_length=1000)
    horizon: str = Field(default="Next quarter", max_length=120)
    tone: Literal["Board-ready", "Strategic", "Operational", "Technical"] = "Strategic"
    focus_areas: list[str] = Field(default_factory=lambda: ["growth", "risk", "quality"])
    sections: list[ReportBlockRequest] = Field(min_length=1)
    visual_style: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class ReportTypeCreate(ReportTypePayload):
    dataset_id: str


class ReportTypeUpdate(ReportTypePayload):
    pass

