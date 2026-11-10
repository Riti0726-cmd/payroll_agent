from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


OosDestination = Literal["benefits", "tax", "workers_comp", "other"]
Category = Literal["qa", "changelist", "todo", "out_of_scope"]


@dataclass
class TriageMessage:
    category: str
    query: str
    intent: str
    confidence: float
    employee_id: str | None = None
    pay_period: str | None = None
    oos_destination: str | None = None
    client_id: str | None = None
    employee_name: str | None = None
    effective_date: str | None = None


@dataclass
class ResolutionMessage:
    category: str
    query: str
    findings: str
    employee_id: str | None = None
    pay_period: str | None = None


ChangeType = Literal[
    "hourly_pay_rate",
    "salary",
    "direct_deposit",
    "w4",
    "address",
    "position",
    "other",
]
SystemTarget = Literal["prismhr", "isolved", "unknown"]
ValidationStatus = Literal["ok", "needs_clarification", "invalid"]


class ClassificationResult(BaseModel):
    category: Category
    intent: str
    confidence: float = 0.95
    employee_id: str | None = Field(
        default=None,
        description="Employee ID only when explicitly present in the inquiry. Do not invent one.",
    )
    pay_period: str | None = Field(
        default=None,
        description="Pay period only when explicitly present (for example 2026-08).",
    )
    oos_destination: OosDestination | None = Field(
        default=None,
        description=(
            "When category is out_of_scope: benefits | tax | workers_comp | other. "
            "Null for in-scope payroll categories."
        ),
    )
    client_id: str | None = Field(
        default=None,
        description="Client ID only when explicitly present in the inquiry. Never invent.",
    )
    employee_name: str | None = Field(
        default=None,
        description="Employee name only when explicitly present. Never invent.",
    )
    effective_date: str | None = Field(
        default=None,
        description=(
            "Effective or due date as stated (ISO YYYY-MM-DD when possible). Never invent."
        ),
    )
    change_type: ChangeType | None = Field(
        default=None,
        description=(
            "For changelist: type of change when clear from the email. Null otherwise."
        ),
    )
    new_value: str | None = Field(
        default=None,
        description="For changelist: stated new/to value only when present in the email.",
    )
    previous_value: str | None = Field(
        default=None,
        description="For changelist: stated previous/from value only when present in the email.",
    )
    system_target: SystemTarget | None = Field(
        default=None,
        description="Optional prismhr | isolved | unknown when stated; else null.",
    )


class ValidationResult(BaseModel):
    status: ValidationStatus = "needs_clarification"
    client_ok: bool | None = None
    employee_ok: bool | None = None
    missing: list[str] = Field(default_factory=list)
    notes: str = ""


class ChangeLineBuild(BaseModel):
    field: str
    from_value: str | None = Field(default=None, alias="from")
    to: str | None = None
    effective_date: str | None = None
    recommended_system: str | None = None
    recommended_field: str | None = None
    notes: str = ""
    incomplete: bool = False

    model_config = {"populate_by_name": True}


class ChangelistSource(BaseModel):
    label: str = ""
    detail: str = ""


class ChangelistBuildResult(BaseModel):
    """Structured output from the changelist agent (before due/priority)."""

    changes: list[ChangeLineBuild] = Field(default_factory=list)
    findings: str = ""
    client_active_employees: int | None = None
    calendar_cutoff: str | None = None
    sources: list[ChangelistSource] = Field(default_factory=list)


class QaChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class QaSource(BaseModel):
    label: str
    detail: str = ""
    query: str | None = None
    interpretation: str | None = None
    response: str | None = None


class QaChatResponse(BaseModel):
    answer: str
    sources: list[QaSource] = Field(default_factory=list)


class QueueItemResponse(BaseModel):
    id: str
    subject: str
    category: Category
    priority: Literal[1, 2, 3, 4, 5]
    receivedAt: str
    clientId: str | None = None
    employeeId: str | None = None
    bodyExcerpt: str | None = None
    extracted: dict[str, str] | None = None
    hasDraft: bool = False


class QueueListResponse(BaseModel):
    items: list[QueueItemResponse] = Field(default_factory=list)


HistoryStatus = Literal["done", "accepted", "discarded", "approved", "needs_clarification"]


class HistoryItemResponse(BaseModel):
    id: str
    subject: str
    status: HistoryStatus
    category: Category
    priority: Literal[1, 2, 3, 4, 5]
    receivedAt: str
    clientId: str | None = None
    employeeId: str | None = None
    bodyExcerpt: str | None = None
    extracted: dict[str, str] | None = None


class HistoryListResponse(BaseModel):
    items: list[HistoryItemResponse] = Field(default_factory=list)


class DraftItemResponse(BaseModel):
    id: str
    subject: str
    to: str
    body: str
    status: Literal["pending", "accepted", "discarded", "sent"]
    relatedQueueId: str | None = None


class DraftListResponse(BaseModel):
    items: list[DraftItemResponse] = Field(default_factory=list)


class ChangeListLineResponse(BaseModel):
    id: str
    field: str
    from_value: str | None = Field(default=None, alias="from")
    to: str | None = None
    reviewed: bool = False
    effectiveDate: str | None = None
    incomplete: bool = False
    recommendedSystem: str | None = None
    recommendedField: str | None = None

    model_config = {"populate_by_name": True}


class ChangeListItemResponse(BaseModel):
    id: str
    clientId: str
    title: str
    lines: list[ChangeListLineResponse] = Field(default_factory=list)
    dueDate: str | None = None
    status: Literal["pending", "incomplete"] | None = None
    priority: Literal[1, 2, 3, 4, 5] | None = None


class ChangeListListResponse(BaseModel):
    items: list[ChangeListItemResponse] = Field(default_factory=list)


class EmailRecordResponse(BaseModel):
    """One email's triage state for the Outlook add-in task pane."""

    id: str
    subject: str
    triaged: bool
    category: Category | None = None
    priority: Literal[1, 2, 3, 4, 5]
    receivedAt: str
    status: str | None = None
    done: bool = False
    clientId: str | None = None
    employeeId: str | None = None
    extracted: dict[str, str] | None = None
    draft: DraftItemResponse | None = None
    changeList: ChangeListItemResponse | None = None


class SettingsRunResponse(BaseModel):
    runId: str
    startedAt: str
    status: str
    result: str = ""


class SettingsResponse(BaseModel):
    lookbackDays: int
    mode: Literal["manual", "recurring"]
    intervalHours: Literal[2, 4, 24]
    runs: list[SettingsRunResponse] = Field(default_factory=list)


class SettingsUpdateRequest(BaseModel):
    lookbackDays: int = Field(ge=1)
    mode: Literal["manual", "recurring"]
    intervalHours: Literal[2, 4, 24]
