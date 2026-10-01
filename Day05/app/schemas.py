"""Day 5, Activity 1: the Pydantic schema for an invoice.

LineItem is done. Your job: finish Invoice by adding the fields listed in the TODO.
Check your work: ask Claude Code to run the tests in tests/test_schemas.py.
"""

from datetime import date

from pydantic import BaseModel, Field, model_validator


# A BaseModel is a Pydantic class: it checks the data you give it against the
# type and rules on each field, and raises a ValidationError if anything is wrong.
class LineItem(BaseModel):
    """One row on an invoice, such as '2 x laptop repair at 3500'."""

    description: str
    quantity: float = Field(gt=0)  # gt=0: greater than zero, so 0 or negative is rejected
    unit_price: float = Field(ge=0)  # ge=0: zero or more, so a free item is allowed


class Invoice(BaseModel):
    """A whole invoice. Used to check what the model extracted from invoice text."""

    # Required fields: no default, so leaving one out is an error.
    invoice_number: str
    vendor_name: str
    invoice_date: date  # the string "2026-09-01" is converted to a date automatically

    # Optional: some invoices do not show a due date.
    due_date: date | None = None
    # Exactly three capital letters, such as INR, USD or GBP.
    # The pattern is a regex: ^ start, [A-Z]{3} three capitals, $ end.
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    # A list of LineItem objects; each one is checked by the LineItem rules above.
    # min_length=1 rejects an empty list.
    line_items: list[LineItem] = Field(min_length=1)
    subtotal: float
    tax: float = 0  # defaults to 0 when the invoice shows no tax
    total: float

    # Runs after all the fields above have passed their own checks, so it can
    # compare fields with each other (a single field can't see the others).
    @model_validator(mode="after")
    def totals_must_add_up(self):
        """subtotal + tax must equal total, allowing a difference of up to 0.01."""
        # abs() makes the check work in both directions; 0.01 allows for rounding.
        if abs(self.subtotal + self.tax - self.total) > 0.01:
            # Raising ValueError here becomes a ValidationError for the caller.
            raise ValueError(
                f"subtotal + tax ({self.subtotal + self.tax}) does not equal total ({self.total})"
            )
        return self
