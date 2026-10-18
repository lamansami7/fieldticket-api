import os
import secrets
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from io import BytesIO
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)

app = FastAPI(
    title="FieldTicket API",
    description="Generate construction T&M tickets and PDF documents.",
    version="1.0.0",
)

CENT = Decimal("0.01")
MAX_MONEY = Decimal("100000000")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def authenticate_customer(
    x_api_key: Annotated[str | None, Header()] = None
):
    if not x_api_key:
        raise HTTPException(401, "API key required")

    from database_backend import use_postgres

    if use_postgres():
        from postgres_customers import authenticate_postgres_key
        customer = authenticate_postgres_key(x_api_key)
    else:
        import hashlib
        from customer_keys import connect

        key_hash = hashlib.sha256(
            x_api_key.encode()
        ).hexdigest()

        with connect() as db:
            row = db.execute(
                """
                SELECT id, customer_name
                FROM api_keys
                WHERE key_hash = ? AND active = 1
                """,
                (key_hash,),
            ).fetchone()

        customer = (
            {
                "customer_id": row[0],
                "customer_name": row[1],
            }
            if row is not None else None
        )

    if customer is None:
        raise HTTPException(
            401, "Invalid or revoked API key"
        )

    return customer


def require_api_key(
    customer: dict = Depends(authenticate_customer)
):
    from database_backend import use_postgres

    if use_postgres():
        from postgres_usage import charge_postgres_request
        charge_postgres_request(customer["customer_id"])
    else:
        from usage_limits import initialize_usage, charge_request
        initialize_usage()
        charge_request(customer["customer_id"])

    return customer


class Labor(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    workers: int = Field(ge=1, le=1000)
    hours_per_worker: Decimal = Field(gt=0, le=10000)
    hourly_rate: Decimal = Field(ge=0, le=100000)


class Material(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    quantity: Decimal = Field(gt=0, le=1000000)
    unit: str = Field(min_length=1, max_length=30)
    unit_price: Decimal = Field(ge=0, le=1000000)


class Ticket(BaseModel):
    ticket_number: str = Field(min_length=1, max_length=60)
    contractor: str = Field(min_length=1, max_length=200)
    customer: str = Field(min_length=1, max_length=200)
    project: str = Field(min_length=1, max_length=200)
    work_date: date
    description: str = Field(min_length=1, max_length=3000)
    labor: list[Labor] = Field(default_factory=list, max_length=100)
    materials: list[Material] = Field(default_factory=list, max_length=100)
    tax_rate_percent: Decimal = Field(default=0, ge=0, le=100)
    markup_percent: Decimal = Field(default=0, ge=0, le=100)


def calculate(ticket: Ticket) -> dict:
    labor_lines = []
    material_lines = []

    for item in ticket.labor:
        amount = money(
            item.workers * item.hours_per_worker * item.hourly_rate
        )
        labor_lines.append({
            "description": item.description,
            "worker_hours": str(item.workers * item.hours_per_worker),
            "amount": str(amount),
        })

    for item in ticket.materials:
        amount = money(item.quantity * item.unit_price)
        material_lines.append({
            "description": item.description,
            "quantity": str(item.quantity),
            "unit": item.unit,
            "amount": str(amount),
        })

    labor_total = sum(
        (Decimal(x["amount"]) for x in labor_lines), Decimal(0)
    )
    material_total = sum(
        (Decimal(x["amount"]) for x in material_lines), Decimal(0)
    )
    subtotal = labor_total + material_total
    markup = money(subtotal * ticket.markup_percent / 100)
    taxable = material_total + money(
        material_total * ticket.markup_percent / 100
    )
    tax = money(taxable * ticket.tax_rate_percent / 100)
    total = subtotal + markup + tax

    if total > MAX_MONEY:
        raise HTTPException(422, "Ticket total exceeds limit")

    return {
        "ticket_number": ticket.ticket_number,
        "currency": "USD",
        "labor": labor_lines,
        "materials": material_lines,
        "labor_total": str(money(labor_total)),
        "material_total": str(money(material_total)),
        "subtotal": str(money(subtotal)),
        "markup": str(markup),
        "tax": str(tax),
        "total": str(money(total)),
        "status": "draft",
        "tax_policy": "Material and material markup only",
    }


def pdf_document(ticket: Ticket, result: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=(612, 792),
        leftMargin=42, rightMargin=42,
        topMargin=42, bottomMargin=42,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="TicketTitle", parent=styles["Title"],
        fontSize=20, textColor=colors.HexColor("#17365D"),
        spaceAfter=18,
    ))
    styles.add(ParagraphStyle(
        name="RightMoney", parent=styles["Normal"],
        alignment=TA_RIGHT,
    ))

    def p(value):
        return Paragraph(
            escape(str(value)).replace("\n", "<br/>"),
            styles["Normal"]
        )

    story = [
        Paragraph("FIELDTICKET | TIME & MATERIALS",
                  styles["TicketTitle"]),
        p("Ticket: " + ticket.ticket_number),
        p("Date: " + ticket.work_date.isoformat()),
        p("Contractor: " + ticket.contractor),
        p("Customer: " + ticket.customer),
        p("Project: " + ticket.project),
        Spacer(1, 16),
        Paragraph("Work Description", styles["Heading2"]),
        p(ticket.description),
        Spacer(1, 14),
        Paragraph("Labor", styles["Heading2"]),
    ]

    def add_table(rows):
        table = Table(rows, colWidths=[370, 156], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0),
             colors.HexColor("#17365D")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F0F4F8")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(table)

    labor_rows = [[p("Description"), p("Amount (USD)")]]
    for item in result["labor"]:
        labor_rows.append([
            p(item["description"] + " (" +
              item["worker_hours"] + " worker-hours)"),
            p("$" + item["amount"]),
        ])
    if len(labor_rows) == 1:
        labor_rows.append([p("No labor"), p("$0.00")])
    add_table(labor_rows)

    story.extend([
        Spacer(1, 14),
        Paragraph("Materials", styles["Heading2"])
    ])

    material_rows = [[p("Description"), p("Amount (USD)")]]
    for item in result["materials"]:
        material_rows.append([
            p(item["description"] + " (" +
              item["quantity"] + " " + item["unit"] + ")"),
            p("$" + item["amount"]),
        ])
    if len(material_rows) == 1:
        material_rows.append([p("No materials"), p("$0.00")])
    add_table(material_rows)

    story.append(Spacer(1, 20))
    for label, key in [
        ("Labor", "labor_total"),
        ("Materials", "material_total"),
        ("Subtotal", "subtotal"),
        ("Markup", "markup"),
        ("Material tax", "tax"),
        ("TOTAL", "total"),
    ]:
        story.append(
            Paragraph(
                f"{label}: ${result[key]}",
                styles["RightMoney"]
            )
        )
        story.append(Spacer(1, 5))

    story.extend([
        Spacer(1, 16),
        p("DRAFT - Review quantities, rates, tax and approval "
          "requirements before billing."),
    ])
    doc.build(story)
    return buffer.getvalue()


@app.get("/")
def home():
    return {
        "name": "FieldTicket API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/v1/tickets/calculate",
          dependencies=[Depends(require_api_key)])
def calculate_ticket(ticket: Ticket):
    return calculate(ticket)


@app.post("/v1/tickets/pdf",
          dependencies=[Depends(require_api_key)])
def generate_pdf(ticket: Ticket):
    result = calculate(ticket)
    pdf = pdf_document(ticket, result)
    safe_name = "".join(
        c for c in ticket.ticket_number
        if c.isalnum() or c in "-_"
    )[:60] or "ticket"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="ticket-{safe_name}.pdf"',
            "Cache-Control": "no-store",
        },
    )



@app.get("/v1/usage")
def customer_usage(
    customer: dict = Depends(authenticate_customer)
):
    from database_backend import use_postgres

    if use_postgres():
        from postgres_usage import get_postgres_usage
        usage = get_postgres_usage(customer["customer_id"])
    else:
        from usage_limits import initialize_usage, get_usage
        initialize_usage()
        usage = get_usage(customer["customer_id"])

    return {
        "customer": customer["customer_name"],
        **usage
    }
