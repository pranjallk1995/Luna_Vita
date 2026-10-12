import os
from functools import lru_cache
from typing import Literal

from openai import OpenAI, OpenAIError
from pydantic import BaseModel, Field


class NutritionEstimate(BaseModel):
    calories: int = Field(ge=0, le=100_000)
    protein_g: float = Field(ge=0, le=10_000)
    carbs_g: float = Field(ge=0, le=10_000)
    fat_g: float = Field(ge=0, le=10_000)
    natural_sugar_g: float = Field(ge=0, le=10_000)
    added_sugar_g: float = Field(ge=0, le=10_000)
    confidence: Literal["low", "medium", "high"]
    assumptions: str = Field(max_length=500)


class NutritionInferenceRequest(BaseModel):
    food_name: str = Field(min_length=1, max_length=200)
    quantity: str | None = Field(default=None, max_length=300)


class NutritionInferenceUnavailable(RuntimeError):
    pass


@lru_cache
def _client() -> OpenAI:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise NutritionInferenceUnavailable("Nutrition inference is not configured.")
    return OpenAI(api_key=key, timeout=20.0, max_retries=1)


def infer_nutrition(request: NutritionInferenceRequest) -> NutritionEstimate:
    description = request.food_name.strip()
    if request.quantity:
        description += f"\nQuantity: {request.quantity.strip()}"
    try:
        response = _client().responses.parse(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            store=False,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Estimate nutrition for the described food or supplement. Return values for the stated "
                        "quantity. Use grams for protein, carbohydrates, fat, natural sugar, and added sugar. "
                        "Separate intrinsic sugar from added sugar. If details are ambiguous, make conservative "
                        "assumptions and lower confidence. This is an estimate for user review, not medical advice."
                    ),
                },
                {"role": "user", "content": description},
            ],
            text_format=NutritionEstimate,
        )
    except OpenAIError as exc:
        raise NutritionInferenceUnavailable("Nutrition inference is temporarily unavailable.") from exc
    estimate = response.output_parsed
    if estimate is None:
        raise NutritionInferenceUnavailable("Nutrition inference returned no usable estimate.")
    return NutritionEstimate.model_validate(estimate)
