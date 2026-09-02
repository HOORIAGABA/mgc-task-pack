#!/usr/bin/env python3
"""Part 1 — Document Q&A CLI."""
import sys
from mgc.assistant import Engine, Index, parse_docs


def main():
    engine = Engine(Index(parse_docs()))
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
        r = engine.answer(q)
        print(f"\n  {r.text}\n")
        if r.sources:
            print("Sources:")
            for s in r.sources:
                print(f"  - {s}")
        print(f"\n  [status: {r.status}]")
        return

    print("MGC Document Assistant — type a question, or 'quit' to exit.\n")
    while True:
        try:
            q = input("Q: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break
        if q.lower() in ("quit", "exit", "q"):
            break
        if not q:
            continue
        r = engine.answer(q)
        print(f"\n  {r.text}\n")
        if r.sources:
            print("Sources:")
            for s in r.sources:
                print(f"  - {s}")
        print(f"\n  [status: {r.status}]\n")


if __name__ == "__main__":
    main()
