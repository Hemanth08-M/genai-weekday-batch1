"""Pydantic schemas for LLM structured output and the fixed log schema."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

RequestType = Literal[
    "new_patient", "er_emergency", "emergency_admission",
    "routine_bed", "cleaning", "patient_handling", "malformed",
]
Priority = Literal["emergency", "urgent", "routine"]


class TriageResult(BaseModel):
    """What the orchestrator derives from a free-text request."""
    request_type: RequestType = Field(description="Category of the request")
    priority: Priority = Field(description="emergency, urgent or routine")
    patient_name: Optional[str] = Field(None, description="Patient name if stated, else null")
    patient_id: Optional[str] = Field(None, description="Existing patient id like P005 if stated, else null")
    age: Optional[int] = Field(None, description="Age if stated or estimated, e.g. 'around 60' gives 60")
    condition: Optional[str] = Field(None, description="Short clinical condition, e.g. 'chest pain'")
    specialty_needed: Optional[str] = Field(None, description="One of the hospital specialties")
    ward_needed: Optional[Literal["ER", "ICU", "General"]] = Field(None, description="Ward if a bed is needed")
    staff_capability: Optional[Literal["registration", "wheelchair", "stretcher", "standard", "biohazard"]] = Field(
        None, description="Staff capability needed (cleaning: standard/biohazard; handling: wheelchair/stretcher)")
    rationale: str = Field(description="One sentence explaining the classification")


class ChatIntent(BaseModel):
    intent: Literal["scenario", "question", "completion"] = Field(
        description="scenario = an operational request to act on; question = asking about current hospital "
                    "state; completion = reporting that the work for one or more request ids is done")
    request_ids: list[str] = Field(default_factory=list,
                                   description="Request ids mentioned for completion, e.g. ['R03', 'C002']")


# Fixed schema required by the task, plus audit columns appended after it
LOG_COLUMNS = ["request_id", "type", "priority", "patient", "doctor", "bed", "staff", "status", "time_taken", "reason"]
LOG_EXTRA_COLUMNS = ["timestamp", "description", "workers", "retry_of", "shift_id"]
TRACE_COLUMNS = ["shift_id", "request_id", "worker", "event", "detail", "logged_at"]
ESCALATION_COLUMNS = ["shift_id", "request_id", "priority", "type", "unresolved", "recommended_action", "flagged_at"]
