# Shipment visibility

A small **cloud-shaped** control tower you can run on a laptop, then talk through as if it were a freight company's production stack.

It:

1. Accepts **EDI 214** shipment-status messages
2. Extracts events (departed, en route, delayed, delivered)
3. Stores a normalized shipment + event history
4. Exposes status on a REST API
5. Raises **delayed-shipment** notifications
6. Shows a dispatch dashboard
7. Documents scale, security, availability, and cost in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

Built to be taught, not to replace a TMS.

## What you will learn

| Piece you can touch | Cloud idea it stands for |
|---|---|
| `POST /api/ingest/edi214` | Inbound integration / API Gateway |
| `samples/*.edi` | Files landing in an S3 bucket |
| `app/edi214.py` | A worker or Lambda that parses a message |
| Postgres (or SQLite) | RDS — system of record |
| `GET /api/shipments` | Product API for customers and the UI |
| Delay scanner | EventBridge scheduled rule |
| Log / webhook / email | CloudWatch + SNS / SES |
| Dashboard | S3 + CloudFront static site |
| `X-API-Key` | The first, simplest auth lesson |

## Quick start (no Docker)

```bash
cd projects/shipment-visibility
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The first launch loads the sample 214s so the board is not empty.

Write endpoints need header `X-API-Key: teaching-demo-key` (already filled in on the dashboard).

## Quick start (Docker — closer to “cloud services”)

```bash
docker compose up --build
```

This starts **two containers**: API and Postgres. That pairing is the teaching moment — the app is stateless; the database is the durable service.

## Lesson plan (about 90 minutes)

Use this order. Stay on one idea until it clicks, then move.

### 1. The business problem (10 min)

A shipper sold coffee. A carrier hauled it. The shipper’s customer asks “where is my freight?” EDI 214 is the carrier’s status update. Without a system, that answer lives in email and phone calls.

Open `samples/01_enroute_ontime.edi` and read it top to bottom. Find:

- `ST*214` — “this transaction is a 214”
- `B10` — PRO number, shipment id, SCAC (carrier code)
- `N1*SH` / `N1*CN` — shipper and consignee
- `G62*EP` — promised delivery
- `AT7` + `MS1` — a status ping and where it happened

### 2. Run the stack (10 min)

Start the app. Click a bill. The **event tape** is the AT7 segments, normalized. Compare the file to the tape so the parser stops feeling magical.

### 3. Follow one message (20 min)

In the dashboard, **Ingest 214 → Carrier delay (A9)**. Then:

1. Show `POST /api/ingest/edi214` in [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
2. Open `app/edi214.py` (`parse_214`)
3. Open `app/ingest.py` (upsert shipment, append events)
4. Open `app/delays.py` (why this one alerts)
5. Look at **Delay alerts** on the board

Same path, five layers: wire → parse → store → rule → notify.

### 4. The API is the product (15 min)

```bash
curl -s http://127.0.0.1:8000/api/shipments | python3 -m json.tool
curl -s http://127.0.0.1:8000/api/shipments/1 | python3 -m json.tool
```

The HTML page is a client. A mobile app, a customer portal, or another carrier system would call the same JSON.

Try a write without the key, then with it:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8000/api/ingest/edi214 \
  -H 'Content-Type: application/json' \
  -d '{"content":"ST*214*1"}'
```

You should see `401`. That is the security lesson in one command.

### 5. Delay rules (15 min)

Two reasons a bill goes red:

- Carrier sent **A9 / SD / AP** (“we are late”)
- **Promised delivery is in the past** and it is not delivered

`04_overdue.edi` is the second case. Ask: should we page someone at 2am, or batch this every 5 minutes? That question is the scheduler vs. stream trade-off in `docs/ARCHITECTURE.md`.

### 6. Cloud decisions (20 min)

Read `docs/ARCHITECTURE.md` together. For each local piece, name the AWS service you would swap in, and what it would cost if this stayed a demo vs. if a 3PL put 2 million 214s/day through it.

## Tests

```bash
pytest -q
```

The parser tests are the ones to walk first: they prove a 214 becomes a PRO, parties, and events before any cloud is involved.

## Project map

```
app/edi214.py          parser
app/ingest.py          normalize + persist
app/delays.py          late-freight rules
app/notifications.py   log / webhook / email
app/main.py            HTTP API + dashboard host
frontend/              dispatch board
samples/               teaching 214s
docs/ARCHITECTURE.md   scale, security, availability, cost
```

## Deploy

`render.yaml` is a free-tier blueprint (web service + Postgres). Free web apps sleep after 15 minutes; free Postgres expires after 30 days. That limitation is itself a teaching point — see the cost section of the architecture doc.
