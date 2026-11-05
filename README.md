# EventProof

EventProof is a lightweight FastAPI + vanilla JavaScript MVP for cautious,
evidence-aware event verification. It produces one of:

* `SUPPORTED`
* `MANIPULATED`
* `RECYCLED_OR_MISCONTEXTUALIZED`
* `CONFLICTING_EVIDENCE`
* `UNVERIFIABLE`

The current deterministic pipeline inspects supplied metadata, parses dates,
locations, and coordinates, and aggregates perturbation scores. It does not
pretend that an absent signal is proof. Open-Meteo and GDACS adapters are
available for future opt-in orchestration; the API currently remains
offline-first and does not make network calls by default.

## Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
uvicorn eventproof.main:app --reload
```

Open http://127.0.0.1:8000. API docs are at `/docs`.

## Checks

```bash
ruff check .
pytest
```

## Limitations

This is not a forensic authenticity system. It cannot verify media pixels,
identify a person, establish chain of custody, or guarantee event truth.
External sources may be stale or unavailable. Human review and independently
verifiable provenance remain necessary.
