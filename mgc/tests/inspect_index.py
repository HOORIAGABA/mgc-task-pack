"""Inspect the document index — passages, topics, and TF-IDF scores."""
from mgc.assistant.docs_index import parse_docs, Index

passages = parse_docs()
index = Index(passages)

print(f"Total passages indexed: {len(passages)}\n")

# --- Passages grouped by source file ---
print("=" * 60)
print("PASSAGES BY DOCUMENT")
print("=" * 60)

by_file = {}
for p in passages:
    by_file.setdefault(p.source_file, []).append(p)

for fname, group in by_file.items():
    print(f"\n--- {fname} ({len(group)} passages) ---")
    for i, p in enumerate(group, 1):
        topics = f" [{', '.join(sorted(p.topics))}]" if p.topics else ""
        text = p.text[:100] + ("..." if len(p.text) > 100 else "")
        print(f"  {i:2d}. {p.section:<35s} {text}{topics}")

# --- Topic summary ---
print(f"\n{'=' * 60}")
print("TOPIC COVERAGE")
print("=" * 60)

topic_count = {}
for p in passages:
    for t in p.topics:
        topic_count.setdefault(t, []).append(p)

for topic in sorted(topic_count, key=lambda t: -len(topic_count[t])):
    ps = topic_count[topic]
    print(f"\n  {topic} ({len(ps)} passages):")
    for p in ps:
        text = p.text[:80] + ("..." if len(p.text) > 80 else "")
        print(f"    - [{p.source_file}] {text}")

# --- TF-IDF demo: search for sample queries ---
print(f"\n{'=' * 60}")
print("TF-IDF SEARCH RESULTS")
print("=" * 60)

queries = [
    "transfer fee percentage",
    "rental yield projection",
    "anchor tenant confirmed",
    "base price 2-bed Block B",
    "Margalla facing corner floor 15",
]

for q in queries:
    results = index.search(q, limit=3)
    print(f"\n  Q: \"{q}\"")
    for i, p in enumerate(results, 1):
        text = p.text[:80] + ("..." if len(p.text) > 80 else "")
        print(f"    {i}. [{p.source_file}] {text}")

# --- IDF scores for interesting terms ---
print(f"\n{'=' * 60}")
print("IDF SCORES (selected terms)")
print("=" * 60)

sample_terms = [
    "transfer", "fee", "yield", "anchor", "margalla",
    "corner", "premium", "booking", "possession", "loan",
    "the", "is", "price", "unit",
]

for term in sorted(sample_terms):
    idf = index._idf(term)
    print(f"  {term:<15s} IDF = {idf:.3f}")
