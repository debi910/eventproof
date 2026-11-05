# EventProof

EventProof is a lightweight FastAPI + vanilla JavaScript MVP for cautious,
evidence-aware event verification. It produces one of:

* `SUPPORTED`
* `MANIPULATED`
* `RECYCLED_OR_MISCONTEXTUALIZED`
* `CONFLICTING_EVIDENCE`
* `UNVERIFIABLE`

The current deterministic pipeline accepts short image/video/audio uploads or
JSON evidence, inspects supplied metadata, parses dates, locations, and
coordinates, and aggregates perturbation scores. It does not pretend that an
absent signal is proof. Open-Meteo and GDACS adapters are opt-in; failures are
shown as unavailable evidence rather than converted into a positive result.

## The demo story

EventProof is intentionally positioned as an **evidence ledger for one
high-stakes decision**, not a universal real/fake classifier. The fastest
demo is:

1. Click **Load demo case** in the browser.
2. Run the evidence pass on the labeled synthetic Quito flood claim.
3. Walk through the verdict, perturbation signal, provenance gaps, and the
   explicit support / contradiction / unknown ledger.
4. End on the reviewer plan: what a journalist, moderator, or incident
   responder should check next.

This shape follows the strongest recent hackathon patterns: a narrow workflow,
visible uncertainty, source-by-source reasoning, graceful degradation, and a
clear user action after the model responds. It also makes the demo honest:
the synthetic fixture is marked as synthetic and no detector result is
presented as proof.

## Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
uvicorn eventproof.main:app --reload
```

Open http://127.0.0.1:8000. API docs are at `/docs`.

The browser form uses `multipart/form-data`. API clients may also send JSON:

```json
{"evidence":{"text":"Flood in Quito 2025-02-03","claimed_location":"Quito"}}
```

For multipart requests, use the `media` field for an image/video/audio file
and text fields such as `claimed_event`, `claimed_location`, and
`check_external_sources`. Uploads are limited to 25 MB.

## Checks

```bash
ruff check .
pytest
```

## Limitations

This is not a forensic authenticity system. It cannot verify media pixels,
identify a person, establish chain of custody, or guarantee event truth.
Temporal localization, heavyweight detector adapters, and C2PA inspection are
extension points, not bundled capabilities. External sources may be stale or
unavailable. Human review and independently verifiable provenance remain
necessary.
