from __future__ import annotations

from datetime import date
from typing import Literal, cast

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import distinct, select
from sqlalchemy.orm import Session

from app import models as _models  # noqa: F401  # registers Expense with Base before create_all
from app.db import Base, engine, get_db
from app.insights import generate_category_insight, generate_monthly_insight
from app.llm import LLMClient, LLMError, get_llm_client
from app.ml.categorizer import DEFAULT_PROTOTYPES, suggest_category, train_categorizer
from app.models import Expense
from app.parser import parse_expense_text
from app.schemas import (
    CategorizerTrainResponse,
    CategorySuggestionResponse,
    CategoryTotal,
    ExpenseCreate,
    ExpenseRead,
    ExpenseUpdate,
    Insight,
    MonthTotal,
    ParsedExpense,
    TextInput,
)
from app.stats import total_by_category, total_by_month

Base.metadata.create_all(bind=engine)

app = FastAPI(title="expense-tracker", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/expenses", status_code=201, response_model=ExpenseRead)
def create_expense(payload: ExpenseCreate, db: Session = Depends(get_db)) -> Expense:  # noqa: B008
    row = Expense(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.get("/expenses", response_model=list[ExpenseRead])
def list_expenses(
    category: str | None = None,
    since: date | None = None,
    db: Session = Depends(get_db),  # noqa: B008
) -> list[Expense]:
    stmt = select(Expense)
    if category is not None:
        stmt = stmt.where(Expense.category == category)
    if since is not None:
        stmt = stmt.where(Expense.occurred_at >= since)
    stmt = stmt.order_by(Expense.occurred_at.desc(), Expense.id.desc())
    return list(db.execute(stmt).scalars().all())


@app.get("/expenses/{expense_id}", response_model=ExpenseRead)
def get_expense(expense_id: int, db: Session = Depends(get_db)) -> Expense:  # noqa: B008
    row = db.execute(select(Expense).where(Expense.id == expense_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="expense not found")
    return row


@app.patch("/expenses/{expense_id}", response_model=ExpenseRead)
def update_expense(
    expense_id: int, payload: ExpenseUpdate, db: Session = Depends(get_db)  # noqa: B008
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
def delete_expense(expense_id: int, db: Session = Depends(get_db)) -> None:  # noqa: B008
    row = db.execute(select(Expense).where(Expense.id == expense_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="expense not found")
    db.delete(row)
    db.commit()


@app.get("/stats/by-month", response_model=list[MonthTotal])
def stats_by_month(db: Session = Depends(get_db)) -> list[MonthTotal]:  # noqa: B008
    return total_by_month(db)


@app.get("/stats/by-category", response_model=list[CategoryTotal])
def stats_by_category(db: Session = Depends(get_db)) -> list[CategoryTotal]:  # noqa: B008
    return total_by_category(db)


@app.post("/expenses/parse", response_model=ParsedExpense)
def parse_expense_endpoint(
    payload: TextInput,
    llm: LLMClient = Depends(get_llm_client),  # noqa: B008
) -> ParsedExpense:
    try:
        return parse_expense_text(payload.text, llm=llm)
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {exc}") from exc


@app.post("/expenses/from-text", status_code=201, response_model=ExpenseRead)
def create_expense_from_text(
    payload: TextInput,
    db: Session = Depends(get_db),  # noqa: B008
    llm: LLMClient = Depends(get_llm_client),  # noqa: B008
) -> Expense:
    try:
        parsed = parse_expense_text(payload.text, llm=llm)
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {exc}") from exc
    row = Expense(
        amount=parsed.amount,
        category=parsed.category,
        description=parsed.description,
        occurred_at=parsed.occurred_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.get("/insights/monthly", response_model=Insight)
def monthly_insight_endpoint(
    month: str,
    db: Session = Depends(get_db),  # noqa: B008
    llm: LLMClient = Depends(get_llm_client),  # noqa: B008
) -> Insight:
    try:
        return generate_monthly_insight(month, db, llm=llm)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {exc}") from exc


@app.get("/insights/category", response_model=Insight)
def category_insight_endpoint(
    category: str,
    since: date | None = None,
    db: Session = Depends(get_db),  # noqa: B008
    llm: LLMClient = Depends(get_llm_client),  # noqa: B008
) -> Insight:
    try:
        return generate_category_insight(category, db, since=since, llm=llm)
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {exc}") from exc


@app.post("/ml/categorize", response_model=CategorySuggestionResponse)
def categorize_endpoint(
    payload: TextInput,
    db: Session = Depends(get_db),  # noqa: B008
) -> CategorySuggestionResponse:
    """Suggest a category for the given expense description.

    Merges categories already present in the DB with the built-in default
    prototypes so that user-defined categories are always considered.
    """
    db_categories = list(db.execute(select(distinct(Expense.category))).scalars().all())
    prototypes = sorted(set(db_categories) | set(DEFAULT_PROTOTYPES))
    result = suggest_category(payload.text, prototypes)
    return CategorySuggestionResponse(
        category=result.category,
        score=result.score,
        mode=cast(Literal["zero-shot", "trained"], result.mode),
    )


@app.post("/ml/train-categorizer", response_model=CategorizerTrainResponse)
def train_categorizer_endpoint(
    db: Session = Depends(get_db),  # noqa: B008
) -> CategorizerTrainResponse:
    """Fit a logistic-regression categorizer on all expenses in the DB.

    Rows with empty or whitespace-only descriptions are excluded — they carry
    no signal for the text-embedding classifier.  Returns a refusal response
    when the data set is too small to produce a reliable model.
    """
    rows = db.execute(select(Expense.description, Expense.category)).all()
    labeled = [(desc, cat) for desc, cat in rows if desc and desc.strip()]
    result = train_categorizer(labeled)
    return CategorizerTrainResponse(
        status=cast(Literal["trained", "refused-insufficient-data"], result.status),
        reason=result.reason,
        n_examples=result.n_examples,
        n_categories=result.n_categories,
        metrics=result.metrics,
    )
