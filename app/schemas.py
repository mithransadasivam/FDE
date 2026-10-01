"""Day 5, Activity 1: the Pydantic schema for an invoice.

LineItem is done. Your job: finish Invoice by adding the fields listed in the TODO.
Check your work: ask Claude Code to run the tests in tests/test_schemas.py.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class LineItem(BaseModel):
    description: str
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)


class Invoice(BaseModel):
    invoice_number: str
    vendor_name: str
    invoice_date: date

    due_date: date | None = None
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    line_items: list[LineItem] = Field(min_length=1)
    subtotal: float
    tax: float = 0
    total: float

    @model_validator(mode="after")
    def totals_add_up(self):
        if abs(self.subtotal + self.tax - self.total) > 0.01:
            raise ValueError("subtotal + tax must equal total")
        return self


class IncidentReport(BaseModel):
    incident_id: str = Field(pattern=r"^INC-\d{4}-\d{4}$")
    system: str = Field(min_length=2)
    severity: Literal["P1", "P2", "P3", "P4"]
    started_at: datetime
    resolved_at: datetime | None = None  # open incidents have no resolution time
    impact: str
    root_cause: str | None = None  # still under investigation on open incidents
    actions: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def resolved_after_started(self):
        if self.resolved_at is None:
            return self
        # an aware and a naive datetime cannot be compared; reject rather than guess a zone
        if (self.resolved_at.tzinfo is None) != (self.started_at.tzinfo is None):
            raise ValueError(
                "started_at and resolved_at must both have a timezone or both have none"
            )
        if self.resolved_at < self.started_at:
            raise ValueError("resolved_at is earlier than started_at")
        return self


SCHEMAS = {"invoice": Invoice, "incident": IncidentReport}
