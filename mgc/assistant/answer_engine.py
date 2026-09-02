import re
from dataclasses import dataclass, field

from .docs_index import Index, TOPIC_KEYWORDS

BASE_TABLE = {
    "A": {
        "studio": (480, 8_640_000, 18_000),
        "1-bed": (720, 13_320_000, 18_500),
        "2-bed": (1_150, 21_850_000, 19_000),
    },
    "B": {
        "1-bed": (720, 13_680_000, 19_000),
        "2-bed": (1_150, 22_425_000, 19_500),
        "2-bed-corner": (1_310, 26_855_000, 20_500),
        "3-bed": (1_880, 39_480_000, 21_000),
        "4-bed": (3_400, 88_400_000, 26_000),
    },
}

PRETTY = {
    "studio": "Studio",
    "1-bed": "1-Bed Standard",
    "2-bed": "2-Bed Standard",
    "2-bed-corner": "2-Bed Corner",
    "3-bed": "3-Bed Executive",
    "4-bed": "4-Bed Penthouse",
}

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "onebed": 1, "twobed": 2,
}

PRICE_VERBS = ("price", "cost", "rate", "how much", "quote", "total", "worth", "what does", "what's", "what is", "what are")


@dataclass
class Answer:
    status: str
    lines: list = field(default_factory=list)
    sources: list = field(default_factory=list)

    @property
    def text(self):
        return "\n".join(self.lines)

    def add_source(self, passage=None, source=None):
        s = source or (passage.source if passage else None)
        if s and s not in self.sources:
            self.sources.append(s)


def fmt(n: float) -> str:
    return f"PKR {n:,.0f}"


def parse_unit(q: str) -> tuple:
    ql = q.lower()
    corner = bool(re.search(r"\bcorner\b", ql))
    if "studio" in ql:
        return "studio", corner
    m = re.search(r"\b(\d+|one|two|three|four)\b\s*(?:-?\s*)?(?:bed(?:rooms?)?|bhk)\b", ql)
    if m:
        n = NUMBER_WORDS.get(m.group(1).lower(), int(m.group(1)))
        sku = f"{n}-bed"
        if sku == "2-bed" and corner:
            sku = "2-bed-corner"
        return sku, corner
    if "penthouse" in ql:
        return "4-bed", corner
    if "executive" in ql:
        return "3-bed", corner
    return None, corner


def parse_block(q: str):
    m = re.search(r"block\s*([a-bA-B])", q, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return None


def parse_floor(q: str) -> int:
    # matches "floor 15", "15th floor", "floors 13-19" style
    m = re.search(r"\b(?:floor[s]?\s+)(\d{1,2})\b", q, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d{1,2})\s*(?:st|nd|rd|th)?\s*(?:floor|fl)\b", q, re.IGNORECASE)
    return int(m.group(1)) if m else None


def is_margalla(q: str) -> bool:
    ql = q.lower()
    return any(w in ql for w in ("margalla", "facing", "mountain", "view"))


def floor_premium(floor: int) -> float:
    if floor is None:
        return 0.0
    if 13 <= floor <= 19:
        return 0.04
    if 20 <= floor <= 22:
        return 0.07
    return 0.0


def topic_hits(q: str) -> list:
    ql = q.lower()
    scored = []
    for topic, keys in TOPIC_KEYWORDS.items():
        hits = sum(1 for k in keys if k in ql)
        if hits:
            scored.append((hits, topic))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [t for _, t in scored]


REFUSAL = {
    "rental_yield": (
        "MGC does not publish rental yield projections and sales staff must not give "
        "projections verbally. Direct this query to the marketing manager."
    ),
    "anchor_tenant": (
        "No anchor tenant has been confirmed as of the brochure issue date (March 2025); "
        "discussions are ongoing. The ground floor is reserved for food and beverage tenants."
    ),
    "home_loan": (
        "MGC has arrangements in principle with two banks, but terms, eligibility and "
        "mark-up rates are set by the bank, not by MGC. Sales staff must not quote mark-up rates."
    ),
    "gas": (
        "A Sui gas connection has been applied for. There is no confirmed timeline yet."
    ),
}


class Engine:
    def __init__(self, index: Index):
        self.index = index
        self.by_topic = {}
        for p in index.passages:
            for t in p.topics:
                self.by_topic.setdefault(t, []).append(p)

    def answer(self, q: str) -> Answer:
        unit, corner = parse_unit(q)
        block = parse_block(q)
        floor = parse_floor(q)
        margalla = is_margalla(q)
        has_price_verb = any(v in q.lower() for v in PRICE_VERBS)

        selected = topic_hits(q)
        if selected and selected[0] in REFUSAL:
            topic = selected[0]
            a = Answer(status="refused")
            a.lines.append(REFUSAL[topic])
            for p in self.by_topic.get(topic, []):
                a.add_source(p)
            return a

        if selected and selected[0] == "transfer_fee":
            return self._transfer_fee()

        if unit and has_price_verb:
            validity = self._validate(unit, corner, block, floor, margalla)
            if validity is not None:
                a = Answer(status="refused")
                a.lines.append(validity)
                self._price_sources(a)
                return a
            return self._price(unit, block, floor, margalla, corner, q)

        if selected:
            return self._topic_answer(selected[0])

        return self._fallback(q)

    def _validate(self, unit, corner, block, floor, margalla):
        if unit == "studio" and block == "B":
            return "Studio units are only available in Block A."
        if unit in ("3-bed", "4-bed", "2-bed-corner") and block == "A":
            return f"{PRETTY[unit]} units are only available in Block B."
        if unit in ("studio", "1-bed") and margalla:
            return "Studio and 1-Bed units are not available with a Margalla-facing orientation."
        if corner and unit != "2-bed-corner":
            return "Corner units are only available as the 2-Bed Corner unit type in Block B."
        return None

    def _price_sources(self, a: Answer):
        for p in self.by_topic.get("base_price", []):
            a.add_source(p)
        for p in self.by_topic.get("location_premium", []):
            a.add_source(p)

    def _price(self, unit, block, floor, margalla, corner, q) -> Answer:
        a = Answer(status="answered")
        ql = q.lower()
        entries = [b for b in ("A", "B") if not block or b == block]
        if not block:
            lines = [f"{PRETTY[unit]} base price:"]
            for b in entries:
                if unit in BASE_TABLE[b]:
                    area, base, psf = BASE_TABLE[b][unit]
                    lines.append(f"  Block {b}: {fmt(base)} ({area:,} sq ft at {fmt(psf)}/sq ft)")
            a.lines.append("\n".join(lines))
            self._price_sources(a)
            a.lines.append("")
            a.lines.append("Location premiums (floors 13-19 +4%, 20-22 +7%, corner +3%, Margalla-facing +6%) are cumulative and applied on top of the base price.")
            return a

        if unit not in BASE_TABLE[block or "A"]:
            a.status = "unsupported"
            a.lines.append(f"No {PRETTY.get(unit, unit)} listing found in Block {block}.")
            return a

        area, base, psf = BASE_TABLE[block][unit]
        premium = []
        fprem = floor_premium(floor)
        if fprem:
            label = f"floor {floor}"
            if fprem == 0.04:
                label += " (floors 13-19)"
            else:
                label += " (floors 20-22)"
            premium.append(("+4%" if fprem == 0.04 else "+7%", fprem, label))
        if corner or unit == "2-bed-corner":
            premium.append(("+3%", 0.03, "corner unit"))
        if margalla:
            premium.append(("+6%", 0.06, "Margalla-facing"))
        total_pct = sum(r for _, r, _ in premium)
        priced = base * (1 + total_pct)

        a.lines.append(f"{PRETTY[unit]} (Block {block}) - {area:,} sq ft")
        a.lines.append(f"  Base price: {fmt(base)}")
        for label, r, desc in premium:
            a.lines.append(f"  {label} premium ({desc}): +{fmt(base * r)}")
        if total_pct == 0:
            a.lines.append("  (no location premiums requested in this quote)")
        else:
            a.lines.append(f"  Premiums are cumulative: +{total_pct * 100:.0f}% over base.")
            a.lines.append(f"  Total unit price: {fmt(priced)}")

        if "cash" in ql or "full cash" in ql:
            if total_pct != 0:
                a.lines.append("")
                a.lines.append("Note: a 12% cash discount applies to the base price only; location premiums are not discounted.")
            else:
                a.lines.append("")
                a.lines.append(f"With full cash payment (12% off base price): {fmt(base * 0.88)}")
        if "50%" in ql or "50 %" in ql:
            a.lines.append(f"With 50% upfront payment (6% off base price): {fmt(base * 0.94)}")
        overseas = any(w in ql for w in ("roshan", "rda", "overseas"))
        if overseas:
            a.lines.append("Overseas Pakistani buyers via Roshan Digital Account: additional 2% discount, stackable with the above.")

        self._price_sources(a)
        a.lines.append("")
        a.lines.append(f"Not included above: mandatory parking {fmt(1_450_000)}, utility & meter {fmt(285_000)}, maintenance advance (12 months at 9.50/sq ft, at possession).")
        return a

    def _transfer_fee(self) -> Answer:
        a = Answer(status="conflict")
        fee_passages = self.by_topic.get("transfer_fee", [])
        values = []
        for p in fee_passages:
            # only extract the percentage that follows the phrase "transfer fee"
            m = re.search(r"transfer fee[^\d]*?(\d+(?:\.\d+)?)\s*%", p.text, re.IGNORECASE)
            if m:
                values.append((float(m.group(1)), p))
        a.lines.append("The two documents disagree on the transfer fee:")
        seen = set()
        for v, p in values:
            where = p.section or p.source_file
            if (v, where) not in seen:
                seen.add((v, where))
                a.lines.append(f"  {v:.1f}% of the current list price ({where})")
        a.lines.append("Confirm the applicable rate with head office before quoting a customer (0308-77 77 275).")
        for p in fee_passages:
            a.add_source(p)
        return a

    def _topic_answer(self, topic: str) -> Answer:
        a = Answer(status="answered")
        passages = self.by_topic.get(topic, [])
        seen = set()
        for p in passages:
            if p.text in seen:
                continue
            seen.add(p.text)
            a.lines.append(f"- {p.text}")
            a.add_source(p)
        if not a.lines:
            a.status = "unsupported"
            a.lines.append(f"I don't have information on that in these documents.")
        return a

    def _fallback(self, q: str) -> Answer:
        boosts = {}
        unit, corner = parse_unit(q)
        if unit:
            prettified = PRETTY[unit].lower()
            boosts[prettified] = 3.0
        block = parse_block(q)
        if block:
            boosts[f"block {block.lower()}"] = 2.0
        hits = self.index.search(q, limit=3, boost=boosts)
        a = Answer(status="partial")
        if not hits:
            a.lines.append("I don't have that in these documents. Ask the marketing manager (sales enquiries: 0308-77 77 275).")
            return a
        a.lines.append("I can't give a confident answer to this from the documents alone. Closest passages:")
        seen = set()
        for p in hits:
            if p.text in seen:
                continue
            seen.add(p.text)
            a.lines.append(f"- {p.text}")
            a.add_source(p)
        return a