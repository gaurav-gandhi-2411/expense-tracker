from __future__ import annotations

from datetime import date, datetime

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
