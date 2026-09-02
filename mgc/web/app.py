"""FastAPI app — serves the HTML page and two API endpoints."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ..assistant import Engine, Index, parse_docs
from ..models.scorer import train_model

TEMPLATE = Path(__file__).parent / "templates" / "index.html"

app = FastAPI(title="MGC Sales Assistant")
_engine = None
_model = _scaler = _cat_values = _medians = None


def _init():
    global _engine, _model, _scaler, _cat_values, _medians
    if _engine is None:
        _engine = Engine(Index(parse_docs()))
    if _model is None:
        _model, _scaler, _cat_values, _medians = train_model()


class Question(BaseModel):
    question: str


class Lead(BaseModel):
    source: str = "Unknown"
    city: str = "Unknown"
    property_type: str = "Apartment"
    budget_pkr_lac: float | None = None
    is_overseas: bool = False
    referred_by_existing_client: bool = False
    has_financing_approved: bool = False
    agent_experience_years: float | None = None
    first_response_minutes: float | None = None


@app.on_event("startup")
def startup():
    _init()


@app.post("/api/ask")
def ask(q: Question):
    result = _engine.answer(q.question)
    return {"answer": result.text, "sources": result.sources, "status": result.status}


@app.post("/api/score")
def score(lead: Lead):
    row = {
        "source": lead.source.strip().title(),
        "city": lead.city.strip().lower().title(),
        "property_type": lead.property_type.strip().title(),
        "budget_pkr_lac": lead.budget_pkr_lac if lead.budget_pkr_lac is not None else _medians["budget_pkr_lac"],
        "is_overseas": int(lead.is_overseas),
        "referred_by_existing_client": int(lead.referred_by_existing_client),
        "has_financing_approved": int(lead.has_financing_approved),
        "agent_experience_years": lead.agent_experience_years if lead.agent_experience_years is not None else _medians["agent_experience_years"],
        "first_response_minutes": lead.first_response_minutes if lead.first_response_minutes is not None else _medians["first_response_minutes"],
    }

    vec = []
    for c in ["source", "city", "property_type"]:
        for v in _cat_values[c]:
            vec.append(1 if row[c] == v else 0)
    vec.extend([row[c] for c in ["is_overseas", "referred_by_existing_client", "has_financing_approved"]])
    vec.extend([row[c] for c in ["budget_pkr_lac", "agent_experience_years", "first_response_minutes"]])

    import numpy as np
    X = np.array([vec], dtype=float)
    X_s = _scaler.transform(X)
    prob = float(_model.predict_proba(X_s)[0, 1])

    return {"probability": round(prob, 4), "label": "likely to convert" if prob >= 0.5 else "unlikely to convert"}


@app.get("/", response_class=HTMLResponse)
def index():
    _init()
    return TEMPLATE.read_text(encoding="utf-8")
