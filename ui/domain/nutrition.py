"""Pure nutrition arithmetic behind the summary cards and macro chart."""

from dataclasses import dataclass
from typing import Any


class NutritionStatus:
    """Classify intake against recommendation targets."""

    WARNING_THRESHOLD = 0.85

    @classmethod
    def limit(cls, value: float, target: float) -> str:
        """Warn near a ceiling and flag when it is exceeded."""
        if target <= 0:
            return ""
        ratio = value / target
        if ratio > 1:
            return "danger"
        return "warning" if ratio >= cls.WARNING_THRESHOLD else ""

    @staticmethod
    def protein(value: float, target: float) -> str:
        """Protein is a floor, so reaching it is a success rather than a warning."""
        return "success" if target > 0 and value >= target else ""

    @staticmethod
    def percentage(value: float, target: float) -> int:
        return round((value / target) * 100) if target > 0 else 0


@dataclass(frozen=True)
class Nutrient:
    """One summary card: how to read its value, target, and status."""

    key: str
    icon: str
    label: str
    unit: str
    summary_field: str
    target_field: str
    target_suffix: str = ""
    decimals: int = 1
    is_floor: bool = False

    def status(self, value: float, target: float) -> str:
        if self.is_floor:
            return NutritionStatus.protein(value, target)
        return NutritionStatus.limit(value, target)


NUTRIENTS = (
    Nutrient("calories", "local_fire_department", "Calories", "kcal",
             "calories", "calories_kcal", decimals=0),
    Nutrient("protein", "fitness_center", "Protein", "g",
             "protein_g", "protein_g", is_floor=True),
    Nutrient("carbs", "grain", "Carbs", "g", "carbs_g", "carbs_g"),
    Nutrient("fat", "water_drop", "Fat", "g", "fat_g", "fat_g"),
    Nutrient("sugars", "nutrition", "Added sugar", "g",
             "added_sugar_g", "sugars_g", target_suffix=" max"),
)


@dataclass(frozen=True)
class Macro:
    label: str
    field: str
    color: str


class MacroBreakdown:
    """Share of each macro in a day's food log, rounded to whole percentages."""

    MACROS = (
        Macro("Protein", "protein_g", "#4ade80"),
        Macro("Carbs", "carbs_g", "#60a5fa"),
        Macro("Fat", "fat_g", "#fbbf24"),
        Macro("Natural sugar", "natural_sugar_g", "#c084fc"),
        Macro("Added sugar", "added_sugar_g", "#fb7185"),
    )

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.calories = sum(float(row["calories"]) for row in rows)
        self.grams = [
            sum(float(row[macro.field]) for row in rows) for macro in self.MACROS
        ]
        self.percentages = self.macro_percentages(self.grams)

    @staticmethod
    def macro_percentages(values: list[float]) -> list[int]:
        """Round non-negative macro shares to integers totaling exactly 100%."""
        total = sum(values)
        if total <= 0:
            return [0] * len(values)

        exact = [value * 100 / total for value in values]
        percentages = [int(value) for value in exact]
        remaining = 100 - sum(percentages)
        by_largest_remainder = sorted(
            range(len(values)),
            key=lambda index: (exact[index] - percentages[index], -index),
            reverse=True,
        )
        for index in by_largest_remainder[:remaining]:
            percentages[index] += 1
        return percentages

    def slices(self) -> list[tuple[Macro, float, int]]:
        return list(zip(self.MACROS, self.grams, self.percentages))
