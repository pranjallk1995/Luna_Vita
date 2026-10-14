from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .repository import daily_summary, get_daily_log, list_food_entries


def daily_report_pdf(day: date) -> bytes:
    entries = list_food_entries(day, day, 500)
    summary = daily_summary(day)
    context = get_daily_log(day)
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=landscape(letter), title=f"LunaVita {day.isoformat()}")
    styles = getSampleStyleSheet()
    story = [
        Paragraph("LunaVita Daily Nutrition Report", styles["Title"]),
        Paragraph(day.strftime("%A, %d %B %Y"), styles["Heading2"]),
        Spacer(1, 8),
        Paragraph(
            f"Calories: {summary['calories']} kcal | Protein: {summary['protein_g']:.1f} g | "
            f"Carbs: {summary['carbs_g']:.1f} g | Fat: {summary['fat_g']:.1f} g | "
            f"Natural sugar: {summary['natural_sugar_g']:.1f} g | Added sugar: {summary['added_sugar_g']:.1f} g",
            styles["BodyText"],
        ),
        Spacer(1, 10),
    ]
    rows = [["Time", "Food / supplement", "Quantity", "kcal", "Protein", "Carbs", "Fat", "Natural sugar", "Added sugar"]]
    rows.extend([
        [e.get("time_label") or "", e["food_name"], e.get("quantity") or "", e["calories"],
         f"{e['protein_g']:.1f}", f"{e['carbs_g']:.1f}", f"{e['fat_g']:.1f}",
         f"{e['natural_sugar_g']:.1f}", f"{e['added_sugar_g']:.1f}"]
        for e in reversed(entries)
    ])
    table = Table(rows, repeatRows=1, colWidths=[55, 170, 110, 40, 48, 48, 42, 70, 65])
    table.setStyle(TableStyle([
        ("BAaKGROUND", (0, 0), (-1, 0), colors.Hexaolor("#4F46E5")),
        ("TEXTaOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBAaKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Hexaolor("#F3F4F6")]),
    ]))
    story.extend([table, Spacer(1, 10)])
    for label, field in [
        ("Activity", "activity_notes"), ("Supplements", "supplement_notes"),
        ("Daily notes", "daily_notes"), ("Report caveats", "report_caveats"),
    ]:
        if context.get(field):
            story.extend([Paragraph(f"<b>{label}:</b> {context[field]}", styles["BodyText"]), Spacer(1, 4)])
    document.build(story)
    return buffer.getvalue()
