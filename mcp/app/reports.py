"""In-memory ReportLab rendering of the daily nutrition and body PDF."""

from dataclasses import dataclass, field
from datetime import date, datetime
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .clock import LocalClock

Row = dict[str, Any]


@dataclass(frozen=True)
class DailyReport:
    """Everything one day's PDF shows, gathered before rendering starts."""

    day: date
    food_entries: list[Row]
    totals: Row
    context: Row = field(default_factory=dict)
    measurements: list[Row] = field(default_factory=list)


class DailyReportRenderer:
    """Render a ``DailyReport`` as a two-page landscape PDF."""

    BODY_METRICS = {
        "weight": ("Weight", "kg"),
        "bmr": ("BMR", "kcal/day"),
        "health_score": ("Health score", "/100"),
        "body_age": ("Body age", "years"),
        "bmi": ("BMI", ""),
        "water_ratio": ("Water ratio", "%"),
    }

    @staticmethod
    def table_style() -> TableStyle:
        return TableStyle(
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

    @classmethod
    def measurement_period(cls, measurement: dict) -> str:
        label = str(measurement.get("time_label") or "").lower()
        if "morning" in label or "am" in label:
            return "Morning"
        if "night" in label or "evening" in label or "pm" in label:
            return "Night"
        measured_at = datetime.fromisoformat(measurement["measured_at"])
        if measured_at.tzinfo is not None:
            measured_at = LocalClock.localize(measured_at)
        return "Morning" if measured_at.hour < 12 else "Night"

    @classmethod
    def format_measurement(cls, metric: str, value: float) -> str:
        _, unit = cls.BODY_METRICS[metric]
        if metric == "health_score":
            return f"{value:g}/100"
        if metric == "bmi":
            return f"{value:g}"
        if unit == "%":
            return f"{value:g}%"
        return f"{value:g} {unit}"

    @classmethod
    def food_entry_time(cls, entry: dict) -> str:
        """Prefer the recorded consumption time, then its free-form label."""
        consumed_at = entry.get("consumed_at")
        if consumed_at:
            try:
                timestamp = datetime.fromisoformat(str(consumed_at))
                if timestamp.tzinfo is not None:
                    timestamp = LocalClock.localize(timestamp)
                return timestamp.strftime("%I:%M %p").lstrip("0")
            except (TypeError, ValueError):
                pass
        return str(entry.get("time_label") or "").strip()

    @staticmethod
    def wrapped_cell(value: object, style: ParagraphStyle) -> Paragraph:
        """Create a table cell that wraps and escapes arbitrary text."""
        text = escape(str(value or "")).replace("\n", "<br/>")
        return Paragraph(text, style)

    @classmethod
    def body_measurement_rows(cls, measurements: list[Row]) -> list[list[str]]:
        """Keep the latest Morning and Night value of every body metric."""
        latest: dict[tuple[str, str], dict] = {}
        for measurement in measurements:
            metric = measurement["metric"]
            if metric not in cls.BODY_METRICS:
                continue
            period = cls.measurement_period(measurement)
            latest[(metric, period)] = measurement

        rows = [["Measurement", "Morning", "Night"]]
        for metric, (label, _) in cls.BODY_METRICS.items():
            row = [label]
            for period in ("Morning", "Night"):
                measurement = latest.get((metric, period))
                row.append(
                    cls.format_measurement(metric, float(measurement["value"]))
                    if measurement
                    else "Not recorded"
                )
            rows.append(row)
        return rows

    def render(self, report: DailyReport) -> bytes:
        day, entries = report.day, report.food_entries
        summary, context = report.totals, report.context
        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            title=f"LunaVita {day.isoformat()}",
        )
        styles = getSampleStyleSheet()
        table_header_style = ParagraphStyle(
            "TableHeader",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=9,
            textColor=colors.white,
        )
        table_cell_style = ParagraphStyle(
            "TableCell",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            spaceAfter=0,
            spaceBefore=0,
        )

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
        food_rows = [
            [
                self.wrapped_cell(label, table_header_style)
                for label in (
                    "Time",
                    "Food / supplement",
                    "Quantity",
                    "kcal",
                    "Protein",
                    "Carbs",
                    "Fat",
                    "Natural sugar",
                    "Added sugar",
                )
            ]
        ]
        food_rows.extend(
            [
                [
                    self.wrapped_cell(self.food_entry_time(entry), table_cell_style),
                    self.wrapped_cell(entry["food_name"], table_cell_style),
                    self.wrapped_cell(entry.get("quantity") or "", table_cell_style),
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
        food_table = Table(
            food_rows,
            repeatRows=1,
            colWidths=[55, 170, 110, 40, 48, 48, 42, 70, 65],
        )
        food_table.setStyle(self.table_style())
        story.extend([food_table, Spacer(1, 10)])
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

        story.extend(
            [
                PageBreak(),
                Paragraph("LunaVita Body Measurements", styles["Title"]),
                Paragraph(day.strftime("%A, %d %B %Y"), styles["Heading2"]),
                Spacer(1, 8),
                Paragraph(
                    "Morning and night weigh-in information for the selected day.",
                    styles["BodyText"],
                ),
                Spacer(1, 10),
            ]
        )
        measurement_table = Table(
            self.body_measurement_rows(report.measurements),
            repeatRows=1,
            colWidths=[220, 220, 220],
        )
        measurement_table.setStyle(self.table_style())
        story.append(measurement_table)

        document.build(story)
        return buffer.getvalue()
