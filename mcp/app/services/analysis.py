"""Pure food analysis over a period: item counts, top contributors, prefer/avoid."""

import calendar
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from difflib import SequenceMatcher
from itertools import combinations
from typing import Any

NUTRIENT_FIELDS = (
    "calories",
    "protein_g",
    "carbs_g",
    "fat_g",
    "natural_sugar_g",
    "added_sugar_g",
)


@dataclass(frozen=True)
class PeriodWindow:
    """An inclusive range of calendar days to analyse."""

    start: date
    end: date

    @classmethod
    def month_of(cls, day: date) -> "PeriodWindow":
        """The whole calendar month containing ``day``."""
        last_day = calendar.monthrange(day.year, day.month)[1]
        return cls(day.replace(day=1), day.replace(day=last_day))

    @property
    def length(self) -> int:
        return (self.end - self.start).days + 1

    def days(self) -> list[date]:
        return [self.start + timedelta(days=offset) for offset in range(self.length)]

    def label(self) -> str:
        return f"{self.start:%d %b} – {self.end:%d %b %Y}"


class FoodName:
    """Group spelling variants such as "Paratha" and "parathas" together."""

    @staticmethod
    def key(name: str) -> str:
        words = re.sub(r"[^\w\s]", " ", name.lower()).split()
        last = words[-1] if words else ""
        if len(last) > 3 and last.endswith("s") and not last.endswith(("ss", "us", "is")):
            words[-1] = last[:-1]
        return " ".join(words)


class FoodCatalog:
    """Resolve any spelling of a food to its one canonical name.

    ``aliases`` maps a ``FoodName.key`` to the canonical name it was merged
    into (by a rename or an explicit alias). Otherwise a spelling resolves to
    the name already used most often for the same key, so "parathas" logs as
    the existing "Paratha".
    """

    def __init__(self, aliases: dict[str, str], name_counts: dict[str, int]) -> None:
        self.aliases = aliases
        self.spellings: dict[str, Counter] = defaultdict(Counter)
        for name, count in name_counts.items():
            self.spellings[FoodName.key(name)][name.strip()] += count

    def canonical(self, name: str) -> str:
        key = FoodName.key(name)
        if key in self.aliases:
            return self.aliases[key]
        spellings = self.spellings.get(key)
        if not spellings:
            return name.strip()
        return min(spellings.items(), key=lambda item: (-item[1], item[0]))[0]

    def key(self, name: str) -> str:
        return FoodName.key(self.canonical(name))

    def resolve(self, name: str) -> dict[str, Any]:
        """The name an entry logged as ``name`` would be saved under, and why."""
        key = FoodName.key(name)
        canonical = self.canonical(name)
        if key in self.aliases:
            source = "alias"
        elif key in self.spellings:
            source = "existing"
        else:
            source = "new"
        known = next(
            (food for food in self.names() if FoodName.key(food["name"]) == FoodName.key(canonical)),
            None,
        )
        return {
            "name": name.strip(),
            "canonical_name": canonical,
            "source": source,
            "entries": known["entries"] if known else 0,
            "aliases": known["aliases"] if known else [],
        }

    def names(self) -> list[dict[str, Any]]:
        """Every canonical food with its entry count and the spellings merged into it."""
        foods: dict[str, dict[str, Any]] = {}
        for spellings in self.spellings.values():
            for spelling, count in spellings.items():
                name = self.canonical(spelling)
                food = foods.setdefault(
                    FoodName.key(name), {"name": name, "entries": 0, "aliases": set()}
                )
                food["entries"] += count
                if spelling != name:
                    food["aliases"].add(spelling)
        for alias_key, name in self.aliases.items():
            food = foods.setdefault(FoodName.key(name), {"name": name, "entries": 0, "aliases": set()})
            food["aliases"].add(alias_key)
        return sorted(
            ({**food, "aliases": sorted(food["aliases"])} for food in foods.values()),
            key=lambda food: (-food["entries"], food["name"].lower()),
        )


class DuplicateFinder:
    """Pairs of canonical foods whose names suggest they are the same food."""

    MIN_SIMILARITY = 0.8  # spelling similarity that flags a likely typo

    @classmethod
    def pair(cls, first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any] | None:
        first_key, second_key = FoodName.key(first["name"]), FoodName.key(second["name"])
        similarity = SequenceMatcher(None, first_key, second_key).ratio()
        first_words, second_words = set(first_key.split()), set(second_key.split())
        if similarity >= cls.MIN_SIMILARITY:
            reason = "similar spelling"
        elif first_words <= second_words or second_words <= first_words:
            reason = "one name contains the other"
            similarity = max(
                similarity,
                len(first_words & second_words) / len(first_words | second_words),
            )
        else:
            return None
        keep, merge = sorted(
            (first, second), key=lambda food: (-food["entries"], food["name"].lower())
        )
        return {
            "keep": keep["name"],
            "merge": merge["name"],
            "similarity": round(similarity, 2),
            "reason": reason,
            "entries": {keep["name"]: keep["entries"], merge["name"]: merge["entries"]},
        }

    @classmethod
    def suggest(cls, foods: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        """Likely duplicates, most similar first; ``keep`` is the more logged name."""
        pairs = (cls.pair(first, second) for first, second in combinations(foods, 2))
        found = [pair for pair in pairs if pair is not None]
        found.sort(key=lambda pair: (-pair["similarity"], pair["keep"].lower()))
        return found[:limit]


@dataclass
class FoodGroup:
    """Every entry of one food over the period, with summed nutrition."""

    key: str
    names: Counter = field(default_factory=Counter)
    count: int = 0
    days: set = field(default_factory=set)
    totals: dict[str, float] = field(
        default_factory=lambda: dict.fromkeys(NUTRIENT_FIELDS, 0.0)
    )
    images: list[str] = field(default_factory=list)

    def add(self, row: dict[str, Any], name: str | None = None) -> None:
        """Count the entry under ``name``, its canonical spelling, if given."""
        self.names[name or str(row["food_name"]).strip()] += 1
        if row.get("image_url"):
            self.images.append(str(row["image_url"]))
        self.count += 1
        self.days.add(str(row.get("consumed_date") or ""))
        for nutrient in NUTRIENT_FIELDS:
            self.totals[nutrient] += float(row.get(nutrient) or 0)

    @property
    def name(self) -> str:
        """The spelling used most often."""
        return self.names.most_common(1)[0][0]

    @property
    def image(self) -> str | None:
        """The image of the latest entry that has one."""
        return self.images[-1] if self.images else None

    @property
    def calories(self) -> float:
        return self.totals["calories"]

    @property
    def calories_per_serving(self) -> float:
        return self.calories / self.count if self.count else 0.0

    def calorie_share(self, nutrient: str, kcal_per_gram: int) -> float:
        """Fraction of this food's logged calories that come from ``nutrient``."""
        if self.calories <= 0:
            return 0.0
        return min(self.totals[nutrient] * kcal_per_gram / self.calories, 1.0)

    @property
    def protein_share(self) -> float:
        return self.calorie_share("protein_g", 4)

    @property
    def carb_share(self) -> float:
        return self.calorie_share("carbs_g", 4)

    @property
    def fat_share(self) -> float:
        return self.calorie_share("fat_g", 9)

    @property
    def added_sugar_share(self) -> float:
        return self.calorie_share("added_sugar_g", 4)


@dataclass(frozen=True)
class Verdict:
    kind: str  # "prefer", "avoid", or "neutral"
    reason: str
    score: float
    source: str = "rule"  # "rule" when computed, "override" when set explicitly


class MacroQuality:
    """Rate foods by macro balance: high protein, low carb, little added sugar.

    Shares are fractions of each food's logged calories (4 kcal/g for protein
    and carbs, 9 kcal/g for fat). Added sugar is judged against the WHO
    guideline of keeping free sugars under 10% of energy.
    """

    MIN_KCAL_PER_SERVING = 50
    PREFER_MIN_PROTEIN = 0.20
    PREFER_MAX_CARBS = 0.40
    PREFER_MAX_ADDED_SUGAR = 0.05
    AVOID_MIN_ADDED_SUGAR = 0.10
    AVOID_MAX_PROTEIN = 0.10
    FAT_ALLOWANCE = 0.40

    @classmethod
    def score(cls, food: FoodGroup) -> float:
        """Higher is better; protein earns points, carbs, sugar, and excess fat cost them."""
        return 100 * (
            food.protein_share
            - 0.5 * food.carb_share
            - food.added_sugar_share
            - 0.5 * max(0.0, food.fat_share - cls.FAT_ALLOWANCE)
        )

    @staticmethod
    def percent(share: float) -> str:
        return f"{share * 100:.0f}%"

    @classmethod
    def verdict(cls, food: FoodGroup) -> Verdict:
        score = cls.score(food)
        if food.calories_per_serving < cls.MIN_KCAL_PER_SERVING:
            return Verdict("neutral", "Too few calories to rate", score)
        if food.added_sugar_share >= cls.AVOID_MIN_ADDED_SUGAR:
            return Verdict(
                "avoid",
                f"{cls.percent(food.added_sugar_share)} of its calories from added sugar",
                score,
            )
        if food.protein_share < cls.AVOID_MAX_PROTEIN:
            heavier = "carbs" if food.carb_share >= food.fat_share else "fat"
            heavy_share = max(food.carb_share, food.fat_share)
            return Verdict(
                "avoid",
                f"Only {cls.percent(food.protein_share)} of calories from protein; "
                f"{cls.percent(heavy_share)} from {heavier}",
                score,
            )
        if (
            food.protein_share >= cls.PREFER_MIN_PROTEIN
            and food.carb_share <= cls.PREFER_MAX_CARBS
            and food.added_sugar_share < cls.PREFER_MAX_ADDED_SUGAR
        ):
            return Verdict(
                "prefer",
                f"{cls.percent(food.protein_share)} of calories from protein, "
                f"{cls.percent(food.carb_share)} from carbs",
                score,
            )
        return Verdict("neutral", "Balanced, but not protein-dense", score)


@dataclass(frozen=True)
class Contributor:
    name: str
    amount: float
    share: float


class FoodAnalysis:
    """Aggregate a period's food entries into the analysis view's sections.

    ``overrides`` maps a ``FoodName.key`` to a stored verdict row; an override
    replaces the rule-based verdict for that food but keeps its macro score.
    ``catalog`` merges aliased spellings into their canonical food.
    """

    TOP_CONTRIBUTORS = 3
    TOP_SUGGESTIONS = 5

    def __init__(
        self,
        rows: list[dict[str, Any]],
        window: PeriodWindow,
        overrides: dict[str, dict[str, Any]] | None = None,
        catalog: FoodCatalog | None = None,
    ) -> None:
        self.window = window
        catalog = catalog or FoodCatalog({}, {})
        groups: dict[str, FoodGroup] = defaultdict(lambda: FoodGroup(key=""))
        for row in rows:
            name = catalog.canonical(str(row["food_name"]))
            key = FoodName.key(name)
            groups[key].key = key
            groups[key].add(row, name)
        self.foods = sorted(
            groups.values(), key=lambda food: (-food.count, -food.calories, food.name.lower())
        )
        self.by_day: dict[str, dict[str, float]] = defaultdict(
            lambda: dict.fromkeys(NUTRIENT_FIELDS, 0.0)
        )
        for row in rows:
            day_totals = self.by_day[str(row.get("consumed_date"))]
            for nutrient in NUTRIENT_FIELDS:
                day_totals[nutrient] += float(row.get(nutrient) or 0)
        self.entries = len(rows)
        self.days_logged = len({str(row.get("consumed_date")) for row in rows})
        self.totals = {
            nutrient: sum(food.totals[nutrient] for food in self.foods)
            for nutrient in NUTRIENT_FIELDS
        }
        overrides = overrides or {}
        self.verdicts = {
            food.key: self.resolve_verdict(food, overrides.get(food.key)) for food in self.foods
        }

    @staticmethod
    def resolve_verdict(food: FoodGroup, override: dict[str, Any] | None) -> Verdict:
        computed = MacroQuality.verdict(food)
        if override is None:
            return computed
        return Verdict(override["verdict"], override["reason"], computed.score, "override")

    def daily_averages(self) -> dict[str, float]:
        """Average intake per logged day, so unlogged days don't dilute it."""
        days = max(self.days_logged, 1)
        return {nutrient: total / days for nutrient, total in self.totals.items()}

    def top_contributors(self, nutrient: str) -> list[Contributor]:
        total = self.totals[nutrient]
        ranked = sorted(self.foods, key=lambda food: food.totals[nutrient], reverse=True)
        return [
            Contributor(food.name, food.totals[nutrient], food.totals[nutrient] / total)
            for food in ranked[: self.TOP_CONTRIBUTORS]
            if total > 0 and food.totals[nutrient] > 0
        ]

    def foods_with(self, kind: str) -> list[tuple[FoodGroup, Verdict]]:
        return [(food, self.verdicts[food.key]) for food in self.foods if self.verdicts[food.key].kind == kind]

    def prefer(self) -> list[tuple[FoodGroup, Verdict]]:
        """Best macro balance first."""
        ranked = sorted(self.foods_with("prefer"), key=lambda pair: pair[1].score, reverse=True)
        return ranked[: self.TOP_SUGGESTIONS]

    def avoid(self) -> list[tuple[FoodGroup, Verdict]]:
        """Biggest calorie impact first, since those are the most worth cutting."""
        ranked = sorted(self.foods_with("avoid"), key=lambda pair: pair[0].calories, reverse=True)
        return ranked[: self.TOP_SUGGESTIONS]

    def daily_totals(self) -> list[dict[str, Any]]:
        """One row per day in the window; unlogged days carry no nutrient values."""
        return [
            {"date": day.isoformat(), "logged": day.isoformat() in self.by_day,
             **self.by_day.get(day.isoformat(), {})}
            for day in self.window.days()
        ]

    def food_dict(self, food: FoodGroup) -> dict[str, Any]:
        verdict = self.verdicts[food.key]
        return {
            "name": food.name,
            "key": food.key,
            "spellings": dict(food.names),
            "image_url": food.image,
            "count": food.count,
            "days": len(food.days),
            "totals": food.totals,
            "calories_per_serving": food.calories_per_serving,
            "protein_share": food.protein_share,
            "carb_share": food.carb_share,
            "fat_share": food.fat_share,
            "added_sugar_share": food.added_sugar_share,
            "verdict": asdict(verdict),
        }

    def to_dict(self) -> dict[str, Any]:
        """The JSON payload shared by the HTTP route and the MCP tool."""
        return {
            "window": {
                "start": self.window.start.isoformat(),
                "end": self.window.end.isoformat(),
                "days": self.window.length,
                "label": self.window.label(),
            },
            "entries": self.entries,
            "days_logged": self.days_logged,
            "totals": self.totals,
            "daily_averages": self.daily_averages(),
            "daily_totals": self.daily_totals(),
            "foods": [self.food_dict(food) for food in self.foods],
            "top_contributors": {
                nutrient: [asdict(item) for item in self.top_contributors(nutrient)]
                for nutrient in NUTRIENT_FIELDS
            },
            "prefer": [self.food_dict(food) for food, _ in self.prefer()],
            "avoid": [self.food_dict(food) for food, _ in self.avoid()],
            "rules": {
                "min_kcal_per_serving": MacroQuality.MIN_KCAL_PER_SERVING,
                "prefer_min_protein_share": MacroQuality.PREFER_MIN_PROTEIN,
                "prefer_max_carb_share": MacroQuality.PREFER_MAX_CARBS,
                "prefer_max_added_sugar_share": MacroQuality.PREFER_MAX_ADDED_SUGAR,
                "avoid_min_added_sugar_share": MacroQuality.AVOID_MIN_ADDED_SUGAR,
                "avoid_max_protein_share": MacroQuality.AVOID_MAX_PROTEIN,
            },
        }
