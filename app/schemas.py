from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExpenseBase(BaseModel):
    amount: float = Field(..., gt=0)
    category: str
    description: str = ""
    occurred_at: date


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    amount: float | None = Field(default=None, gt=0)
    category: str | None = None
    description: str | None = None
    occurred_at: date | None = None


class ExpenseRead(ExpenseBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MonthTotal(BaseModel):
    month: str
    total: float


class CategoryTotal(BaseModel):
    category: str
    total: float


class TextInput(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)


class ParsedExpense(BaseModel):
    amount: float = Field(..., gt=0)
    category: str
    description: str
    occurred_at: date = Field(default_factory=date.today)
    confidence: float = Field(..., ge=0.0, le=1.0)


class Insight(BaseModel):
    scope: str
    narrative: str
    stats: dict[str, float]
    generated_at: datetime = Field(default_factory=datetime.now)


class CategorySuggestionResponse(BaseModel):
    category: str
    # cosine similarity in [-1, 1] for zero-shot; class probability in [0, 1] for trained.
    # The wider bound [-1, 1] covers both modes without a conditional validator.
    score: float = Field(..., ge=-1.0, le=1.0)
    mode: Literal["zero-shot", "trained"]


class CategorizerTrainResponse(BaseModel):
    status: Literal["trained", "refused-insufficient-data"]
    reason: str
    n_examples: int = Field(..., ge=0)
    n_categories: int = Field(..., ge=0)
    metrics: dict[str, float] | None = None


class AnomalyFlagResponse(BaseModel):
    expense_id: int
    amount: float
    category: str
    reason: str
    score: float
