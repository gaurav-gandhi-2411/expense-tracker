from __future__ import annotations

from fastapi import FastAPI

from app import models as _models  # noqa: F401  # registers Expense with Base before create_all
from app.db import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="expense-tracker", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
