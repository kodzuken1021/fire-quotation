import os
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

COMPANY = "LS Ramos Safety Supplies and Services"


def _php(value):
    return f"PHP {value:,.2f}"


def build_quotation_pdf(folder, quotation, req, client):
    """Writes the PDF and returns its file name (not the full path)."""
    os.makedirs(folder, exist_ok=True)
    filename = f"{quotation.quotation_no}.pdf"
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(os.path.join(folder, filename), pagesize=A4,
                            leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
                            title=f"Quotation {quotation.quotation_no}")

    story = [
        Paragraph(escape(COMPANY), styles["Title"]),
        Paragraph("OFFICIAL QUOTATION", styles["Heading2"]),
        Paragraph(f"<b>Quotation no.:</b> {escape(quotation.quotation_no)}", styles["Normal"]),
        Paragraph(f"<b>Request no.:</b> {req.id}", styles["Normal"]),
        Paragraph(f"<b>Valid until:</b> {quotation.valid_until.strftime('%B %d, %Y') if quotation.valid_until else '-'}",
                  styles["Normal"]),
        Spacer(1, 6 * mm),
        Paragraph("<b>Prepared for</b>", styles["Normal"]),
        Paragraph(escape(client.full_name), styles["Normal"]),
        Paragraph(escape(client.company_name or ""), styles["Normal"]),
        Paragraph(escape(client.email), styles["Normal"]),
        Spacer(1, 6 * mm),
    ]

    rows = [["Item", "Qty", "Unit price", "Amount"]]
    for l in quotation.line_details():
        rows.append([Paragraph(escape(l["name"]), styles["Normal"]), l["quantity"],
                     _php(l["unit_price"]), _php(l["line_total"])])
    if req.needs_installation:
        rows.append(["Installation charge", "", "", _php(quotation.installation_charge)])
    if req.needs_testing:
        rows.append(["Testing charge", "", "", _php(quotation.testing_charge)])
    rows.append(["", "", "TOTAL", _php(quotation.total)])

    table = Table(rows, colWidths=[85 * mm, 15 * mm, 35 * mm, 35 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#c62828")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (-2, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -2), 0.4, colors.lightgrey),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [table, Spacer(1, 8 * mm),
              Paragraph("Thank you for your request. To proceed, please reply to the email this quotation came with.",
                        styles["Normal"])]
    doc.build(story)
    return filename