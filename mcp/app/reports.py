from datetime import date
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .repository import LunaVitaRepository


class DailyReportService:
    """Build the daily nutrition PDF from repository data."""

    def __init__(self, repository: LunaVitaRepository) -> None:
        self.repository = repository

    def build(self, day: date) -> bytes:
        entries = self.repository.list_food_entries(day, day, 500)
        summary = self.repository.daily_summary(day)
        context = self.repository.get_daily_log(day)
        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            title=f"LunaVita {day.isoformat()}",
        )
        styles = getSampleStyleSheet()
        story = [
            Paragraph("LunaVita Daily Nutrition Report", styles["Title"]),
            Paragraph(day.strftime("%A, %d %B %Y"), styles["Heading2"]),
            Spacer(1, 8),
            Paragraph(
                f"Calories: {summary['calories']} kcal | "
                f"Protein: {summary['protein_g']:.1f} g | "
                f"Carbs: {summary['carbs_g']:.1f} g | "
                f"Fat: {summary['fat_g']:.1f} g | "
                f"Natural sugar: {summary['natural_sugar_g']:.1f} g | "
                f"Added sugar: {summary['added_sugar_g']:.1f} g",
                styles["BodyText"],
            ),
            Spacer(1, 10),
        ]
        rows = [
            [
                "Time",
                "Food / supplement",
                "Quantity",
                "kcal",
                "Protein",
                "Carbs",
                "Fat",
                "Natural sugar",
                "Added sugar",
            ]
        ]
        rows.extend(
            [
                [
                    entry.get("time_label") or "",
                    entry["food_name"],
                    entry.get("quantity") or "",
                    entry["calories"],
                    f"{entry['protein_g']:.1f}",
                    f"{entry['carbs_g']:.1f}",
                    f"{entry['fat_g']:.1f}",
                    f"{entry['natural_sugar_g']:.1f}",
                    f"{entry['added_sugar_g']:.1f}",
                ]
                for entry in reversed(entries)
            ]
        )
        table = Table(
            rows,
            repeatRows=1,
            colWidths=[55, 170, 110, 40, 48, 48, 42, 70, 65],
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F46E5")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F3F4F6")],
                    ),
                ]
            )
        )
        story.extend([table, Spacer(1, 10)])
        for label, field in [
            ("Activity", "activity_notes"),
            ("Supplements", "supplement_notes"),
            ("Daily notes", "daily_notes"),
            ("Report caveats", "report_caveats"),
        ]:
            value = context.get(field)
            if value:
                story.extend(
                    [
                        Paragraph(
                            f"<b>{label}:</b> {escape(str(value))}",
                            styles["BodyText"],
                        ),
                        Spacer(1, 4),
                    ]
                )
        document.build(story)
        return buffer.getvalue()
