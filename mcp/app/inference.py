import os
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


class NutritionInferenceService:
    """Estimate nutrition through OpenAI when server-side inference is configured."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")).strip()
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._client: OpenAI | None = None

    def client(self) -> OpenAI:
        if not self.api_key:
            raise NutritionInferenceUnavailable("Nutrition inference is not configured.")
        if self._client is None:
            self._client = OpenAI(
                api_key=self.api_key,
                timeout=20.0,
                max_retries=1,
            )
        return self._client

    def infer(self, request: NutritionInferenceRequest) -> NutritionEstimate:
        description = request.food_name.strip()
        if request.quantity:
            description += f"\nQuantity: {request.quantity.strip()}"
        try:
            response = self.client().responses.parse(
                model=self.model,
                store=False,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "Estimate nutrition for the described food or supplement. "
                            "Return values for the stated quantity. Use grams for protein, "
                            "carbohydrates, fat, natural sugar, and added sugar. Separate "
                            "intrinsic sugar from added sugar. If details are ambiguous, "
                            "make conservative assumptions and lower confidence. This is "
                            "an estimate for user review, not medical advice."
                        ),
                    },
                    {"role": "user", "content": description},
                ],
                text_format=NutritionEstimate,
            )
        except OpenAIError as exc:
            raise NutritionInferenceUnavailable(
                "Nutrition inference is temporarily unavailable."
            ) from exc
        estimate = response.output_parsed
        if estimate is None:
            raise NutritionInferenceUnavailable(
                "Nutrition inference returned no usable estimate."
            )
        return NutritionEstimate.model_validate(estimate)
