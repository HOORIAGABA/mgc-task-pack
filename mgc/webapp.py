#!/usr/bin/env python3
"""Part 4 — Web interface."""
import uvicorn

if __name__ == "__main__":
    print("MGC Sales Assistant — http://localhost:8000")
    uvicorn.run("mgc.web.app:app", host="0.0.0.0", port=8000, reload=True)
