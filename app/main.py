from __future__ import annotations

from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as _models  # noqa: F401  # registers Expense with Base before create_all
from app.db import Base, engine, get_db
from app.models import Expense
from app.schemas import ExpenseCreate, ExpenseRead, ExpenseUpdate

Base.metadata.create_all(bind=engine)

app = FastAPI(title="expense-tracker", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/expenses", status_code=201, response_model=ExpenseRead)
def create_expense(payload: ExpenseCreate, db: Session = Depends(get_db)) -> Expense:
    row = Expense(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.get("/expenses", response_model=list[ExpenseRead])
def list_expenses(
    category: str | None = None,
    since: date | None = None,
    db: Session = Depends(get_db),
) -> list[Expense]:
    stmt = select(Expense)
    if category is not None:
        stmt = stmt.where(Expense.category == category)
    if since is not None:
        stmt = stmt.where(Expense.occurred_at >= since)
    stmt = stmt.order_by(Expense.occurred_at.desc(), Expense.id.desc())
    return list(db.execute(stmt).scalars().all())


@app.get("/expenses/{expense_id}", response_model=ExpenseRead)
def get_expense(expense_id: int, db: Session = Depends(get_db)) -> Expense:
    row = db.execute(select(Expense).where(Expense.id == expense_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="expense not found")
    return row


@app.patch("/expenses/{expense_id}", response_model=ExpenseRead)
def update_expense(
    expense_id: int, payload: ExpenseUpdate, db: Session = Depends(get_db)
) -> Expense:
    row = db.execute(select(Expense).where(Expense.id == expense_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="expense not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


@app.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: int, db: Session = Depends(get_db)) -> None:
    row = db.execute(select(Expense).where(Expense.id == expense_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="expense not found")
    db.delete(row)
    db.commit()
