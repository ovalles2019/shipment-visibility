# Shipment visibility — teaching platform

Oscar is using this repo to teach a cloud-career pivot: EDI ingest → normalize → API → delay alerts → dashboard.

- Prefer small, readable modules over extra abstraction.
- Keep sample EDI 214 files valid enough to parse; do not chase a full X12 library.
- Docs in `docs/ARCHITECTURE.md` must stay honest about what this demo is vs. a 3PL production stack.
- Local path: FastAPI + Postgres (or SQLite). Cloud mapping lives in the architecture doc, not as unused AWS SDK calls.
