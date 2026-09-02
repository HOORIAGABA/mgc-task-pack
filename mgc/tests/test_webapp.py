"""Quick smoke-test for the webapp endpoints."""
from mgc.web.app import app, _init
from fastapi.testclient import TestClient

_init()
client = TestClient(app)

# Q&A — base price
r = client.post("/api/ask", json={"question": "What's the base price of a 2-bed in Block B?"})
d = r.json()
assert r.status_code == 200
assert "22,425,000" in d["answer"]
assert d["status"] == "answered"
print(f"[PASS] Q&A base price: {d['answer'][:80]}")

# Q&A — conflict
r = client.post("/api/ask", json={"question": "What is the transfer fee?"})
d = r.json()
assert d["status"] == "conflict"
print(f"[PASS] Transfer fee conflict: status={d['status']}")

# Q&A — refusal
r = client.post("/api/ask", json={"question": "What is the rental yield on a 1-bed?"})
d = r.json()
assert d["status"] == "refused"
print(f"[PASS] Rental yield refusal: status={d['status']}")

# Lead scoring
r = client.post("/api/score", json={
    "source": "Referral", "city": "Islamabad", "property_type": "Apartment",
    "budget_pkr_lac": 150, "is_overseas": False,
    "referred_by_existing_client": True, "has_financing_approved": True,
    "agent_experience_years": 5, "first_response_minutes": 10,
})
d = r.json()
assert r.status_code == 200
assert 0 <= d["probability"] <= 1
print(f"[PASS] Lead scoring: {d['probability']:.1%} — {d['label']}")

# HTML page
r = client.get("/")
assert r.status_code == 200
assert "Document Q" in r.text
assert "Lead Scoring" in r.text
print(f"[PASS] HTML page served: {len(r.text)} chars")

print("\nAll checks passed.")
