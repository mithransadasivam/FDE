from app.schemas import IncidentReport, Invoice
from scripts.extract_batch import describe


def test_describe_incident_shows_severity_and_system():
    incident = IncidentReport(
        incident_id="INC-2026-0917",
        system="Payments API",
        severity="P1",
        started_at="2026-09-14T14:05:00+05:30",
        impact="Card payments failed",
        actions=["Rolled back"],
    )
    assert describe(incident) == "P1 Payments API"


def test_describe_invoice_shows_total_and_currency():
    invoice = Invoice(
        invoice_number="INV-1",
        vendor_name="Acme",
        invoice_date="2026-09-01",
        currency="INR",
        line_items=[{"description": "Repair", "quantity": 2, "unit_price": 3500}],
        subtotal=7000,
        total=7000,
    )
    assert describe(invoice) == "total 7,000.00 INR"
