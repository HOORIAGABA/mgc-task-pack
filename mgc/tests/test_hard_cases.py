"""Smoke-test the five hard cases from the brief."""

from mgc.assistant import Engine, Index, parse_docs

CASES = [
    (
        "What's the base price of a 2-bed in Block B?",
        {"status": "answered", "must_contain": ["22,425,000", "Block B"]},
    ),
    (
        "What's the total for a Margalla-facing corner unit on floor 15, 2-bed Block B?",
        {"status": "answered", "must_contain": ["26,855,000", "13"]},
    ),
    (
        "What's the transfer fee?",
        {"status": "conflict", "must_contain": ["2", "2.5"]},
    ),
    (
        "What's the rental yield on a 1-bed?",
        {"status": "refused", "must_contain": ["does not publish", "marketing manager"]},
    ),
    (
        "Who is the anchor tenant?",
        {"status": "refused", "must_contain": ["no anchor tenant", "confirmed"]},
    ),
]


def main():
    engine = Engine(Index(parse_docs()))
    passed = 0
    for question, checks in CASES:
        result = engine.answer(question)
        status_ok = result.status == checks["status"]
        text_lower = result.text.lower()
        contains_ok = all(
            kw.lower() in text_lower for kw in checks["must_contain"]
        )
        ok = status_ok and contains_ok
        tag = "PASS" if ok else "FAIL"
        print(f"\n[{tag}] {question}")
        print(f"    status : {result.status} (expected {checks['status']})")
        print(f"    answer : {result.text[:120]}")
        if result.sources:
            print(f"    sources: {', '.join(result.sources)}")
        if not ok:
            if not status_ok:
                print(f"    !! wrong status")
            if not contains_ok:
                print(f"    !! missing keywords: {[k for k in checks['must_contain'] if k.lower() not in text_lower]}")
        if ok:
            passed += 1

    print(f"\n{'='*50}")
    print(f"  {passed}/{len(CASES)} cases passed")
    return 0 if passed == len(CASES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
