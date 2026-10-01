"""Day 5, Activity 1: the Pydantic schema for an invoice.

LineItem is done. Your job: finish Invoice by adding the fields listed in the TODO.
Check your work: ask Claude Code to run the tests in tests/test_schemas.py.
"""

from datetime import date

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
