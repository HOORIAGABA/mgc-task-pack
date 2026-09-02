from dataclasses import dataclass, field
from pathlib import Path
import re

DOCS_DIR = Path(__file__).resolve().parent.parent / "data" / "docs"


@dataclass
class Passage:
    source_file: str
    doc_title: str
    section: str
    text: str
    topics: set = field(default_factory=set)

    @property
    def source(self):
        where = self.source_file
        if self.section:
            where += f" \u203a {self.section}"
        return where


TOPIC_KEYWORDS = {
    "rental_yield": ("yield", "rental"),
    "anchor_tenant": ("anchor", "anchor tenant"),
    "transfer_fee": ("transfer fee",),
    "home_loan": ("loan", "mark-up", "markup", "mortgage", "home financing"),
    "gas": ("gas", "sui"),
    "payment_plan": ("payment plan", "instalment", "installment", "quarterly", "booking / token", "on possession"),
    "discount": ("discount", "cash payment", "50% upfront", "roslan", "roshn", "second unit"),
    "other_charges": ("utility connection", "parking slot", "maintenance advance"),
    "booking_process": ("form mgc-b1", "allocation letter", "confirmation payment", "token amount", "escrow"),
    "cancel_refund": ("cancel", "refund", "liquidated damages"),
    "transfer_process": ("transferred to a third party", "power of attorney"),
    "possession": ("possession", "completion certificate", "holding charge"),
    "unit_change": ("changed to a different unit", "change is permitted"),
    "base_price": ("base price",),
    "location_premium": ("premium", "floors 13", "floors 20"),
    "project_overview": ("22-storey", "418 residential", "groundbreaking", "structural completion"),
    "commercial_podium": ("commercial podium", "74 commercial", "food and beverage"),
    "approvals": ("approval", "noc", "capital development authority", "pak-epa"),
    "sales_office": ("sales office", "0308", "head office"),
}


def _strip_md(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1", text)
    return text.strip()


def _tag_topics(text: str, topics: set) -> None:
    low = text.lower()
    for topic, keys in TOPIC_KEYWORDS.items():
        if any(k in low for k in keys):
            topics.add(topic)


def _parse_table(rows: list, section: str, file_name: str, doc_title: str, out: list) -> None:
    header = None
    for raw in rows:
        cells = [c.strip() for c in raw.strip().strip("|").split("|")]
        if not cells or all(re.fullmatch(r":?-{3,}:?", c or "") for c in cells):
            continue
        if header is None:
            header = cells
            continue
        parts = []
        for i, cell in enumerate(cells):
            if not cell:
                continue
            label = header[i] if i < len(header) and header[i] else f"col{i}"
            parts.append(f"{label}: {cell}")
        text = _strip_md("; ".join(parts))
        p = Passage(file_name, doc_title, section, text)
        _tag_topics(text, p.topics)
        out.append(p)


def parse_docs(docs_dir: Path = DOCS_DIR) -> list:
    passages = []
    for md in sorted(docs_dir.glob("*.md")):
        doc_title = ""
        section = ""
        block = []
        table_rows = []
        in_table = False
        for line in md.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                if in_table and table_rows:
                    _parse_table(table_rows, section, md.name, doc_title, passages)
                    table_rows = []
                    in_table = False
                if block:
                    text = _strip_md("\n".join(block).strip())
                    if text and text != doc_title:
                        p = Passage(md.name, doc_title, section, text)
                        _tag_topics(text, p.topics)
                        passages.append(p)
                    block = []
                if stripped.startswith("# "):
                    doc_title = stripped.lstrip("# ").strip()
                else:
                    section = stripped.lstrip("#").strip()
                continue
            if stripped.startswith("|"):
                table_rows.append(stripped)
                in_table = True
                continue
            if in_table:
                if table_rows:
                    _parse_table(table_rows, section, md.name, doc_title, passages)
                    table_rows = []
                in_table = False
            if not stripped:
                if block:
                    text = _strip_md("\n".join(block).strip())
                    if text:
                        p = Passage(md.name, doc_title, section, text)
                        _tag_topics(text, p.topics)
                        passages.append(p)
                    block = []
                continue
            block.append(stripped)
        if block:
            text = _strip_md("\n".join(block).strip())
            if text:
                p = Passage(md.name, doc_title, section, text)
                _tag_topics(text, p.topics)
                passages.append(p)
        if in_table and table_rows:
            _parse_table(table_rows, section, md.name, doc_title, passages)
    return passages


def _tokenize(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _df(passages: list) -> dict:
    df = {}
    for p in passages:
        for t in _tokenize(p.text):
            df[t] = df.get(t, 0) + 1
    return df


class Index:
    def __init__(self, passages: list):
        self.passages = passages
        self.df = _df(passages)
        self.n = len(passages)
        for p in self.passages:
            p._tokens = _tokenize(p.text)

    def _idf(self, term: str) -> float:
        from math import log
        n = max(1, self.df.get(term, 0))
        return log((1 + self.n) / (1 + n)) + 1.0

    def search(self, query: str, limit: int = 3, boost: dict = None) -> list:
        q = _tokenize(query)
        boost = boost or {}
        scored = []
        for p in self.passages:
            score = 0.0
            for t in q:
                if t in p._tokens:
                    score += self._idf(t)
            boost_hits = 0
            for term in boost:
                if term in p.text.lower():
                    boost_hits += boost[term]
            scored.append((score + boost_hits, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for s, p in scored if s > 0][:limit]