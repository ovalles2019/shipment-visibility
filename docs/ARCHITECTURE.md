# Architecture decisions

This demo is a **modular monolith**: one FastAPI process, one database, a scheduled delay scan, and a static dashboard served by the same app.

That is a feature for teaching. You can see the whole path. Below is how the same design stretches — or breaks — when it becomes a real visibility platform, and how we would rebuild it on AWS.

```
Carrier 214 ──POST /api/ingest/edi214──► Parser ──► Postgres
                                              │
                                              ├── GET /api/shipments ──► Dashboard / customers
                                              └── Delay rules ──► log / webhook / email
```

## What we chose, and why

| Decision | Choice | Why for a teaching repo |
|---|---|---|
| App style | One service | You can read the request from ingress to row |
| Language | Python 3.12 + FastAPI | Matches Oscar’s other demos; OpenAPI is free |
| Database | Postgres in Docker, SQLite on a laptop | Same SQL; two “managed database” stories |
| Parser | ~150 lines, no X12 library | The 214 becomes visible, not hidden in a vendor SDK |
| Auth | Shared API key on writes | One header, one 401, then talk Cognito |
| Alerts | Log always; webhook/SMTP optional | SNS/SES without an AWS bill |
| Hosting | Render blueprint + local Docker | Something you can actually deploy this weekend |
| UI | Static HTML/JS | No frontend build step in lesson 1 |

## Scalability

**What the demo does.** Ingest is synchronous: the HTTP request parses the 214, writes rows, and evaluates delay rules before it returns. That is fine for a classroom and for a few thousand messages a day.

**Where it bends.**

- **Ingest burst.** Carriers often dump status in batches (end of hour, after a yard scan). A synchronous API will time out or drop connections. Production move: land the raw file in object storage, enqueue a pointer, ack the partner fast, parse out of band.
- **Hot shipment key.** All events for one PRO hit the same row. Use `pro_number + scac` as the natural key (we already unique-constrain it) and keep events append-only.
- **Read vs write.** The dashboard and customer APIs are read-heavy. An index on `pro_number`, `current_status`, and `promised_delivery` covers this demo. At millions of events/day you split **ingest writes** from **query replicas**, or put a cache in front of `GET /api/shipments/{id}`.
- **Parser CPU.** EDI parse is cheap compared with LLM work. Horizontal scale is “more workers pulling a queue,” not a bigger box.
- **Fan-out.** One 214 may need to notify a shipper, a broker, and a store manager. That is a topic (SNS), not a `for` loop in the request.

**AWS shape at 10x–1000x**

1. S3 inbound bucket (`s3://…/214/inbound/`) + S3 event
2. SQS queue (visibility timeout, DLQ)
3. Worker (Lambda or ECS) runs the same `parse_214` / `ingest_edi` you have here
4. RDS Postgres, Multi-AZ, read replica for the API
5. API Gateway + the same FastAPI on ECS Fargate (or Lambda if you keep the handler tiny)
6. EventBridge rule every 5 minutes still calls `scan_and_notify` — or you emit a domain event the moment an AT7 is `A9`

**What we would not do yet:** Kafka, microservices per carrier, or a separate “event store” product. Those show up when you have many producers and multiple independent consumers, not when you have one parser and one dashboard.

## Security

**What the demo does.**

- Write routes require `X-API-Key`. Reads are open so the dashboard is easy to teach.
- Raw EDI is stored in `ingest_records` (the “keep the fax” rule).
- Secrets live in environment variables (`.env` locally, Render env / AWS Secrets Manager later).
- Sample files contain no real customer freight.

**Honest gaps — call these out while teaching.**

- A shared API key is not a user. It cannot be revoked per person, and it is in the browser.
- Reads are unauthenticated. A customer must only see **their** bills (`WHERE shipper_id = :sub`).
- No TLS termination in Docker; rely on the platform (Render/CloudFront) for HTTPS.
- No partner allow-list. A real inbound 214 endpoint checks ISA sender ID and signs or IPs the VAN.
- Notifications can leak PII (shipper, consignee, PO). Treat the webhook like a production integration.
- SQLAlchemy parameterization is in use; do not concatenate EDI text into SQL (we don’t).

**Production controls to name**

| Control | AWS / platform analog |
|---|---|
| Rotate the ingest key | Secrets Manager + deploy |
| Per-tenant reads | Cognito / IAM + row filters |
| Inbound partner auth | mTLS, signed SFTP, or a VAN |
| Encrypt data at rest | RDS encryption, S3 SSE |
| Encrypt in transit | HTTPS only, no mixed content |
| Least privilege | Task role that can read the inbound bucket and write RDS, nothing else |
| Audit | CloudTrail + the `ingest_records` table |

## Availability

**What the demo does.** One process. If it dies, ingest and the delay scanner die together. SQLite is a single file; Postgres in Compose is one container without a replica.

**How we talk about SLOs.** A visibility API is not a payment switch. A reasonable teaching target: ingest accepted 99.9% of the month, status reads 99.9%, alerts *eventually* (minutes, not milliseconds).

**Failure modes worth acting out**

| Failure | What the user sees | What we would change |
|---|---|---|
| API process crash | Dashboard blank, 214 POST fails | Two tasks behind a load balancer; health check is already `/health` |
| Database down | Everything fails | Multi-AZ RDS; the API should fail noisy, not write to disk “for later” unless you have a queue |
| Parser rejects a 214 | HTTP 422 | Keep the raw payload (we do), send the partner a 997/824 later, operate a DLQ |
| Notification webhook down | Alert still stored as `log` | Retry with backoff; do not fail the ingest because email is down (we already isolate this) |
| Free Render sleep | First request is slow / 503 | Paid instance, or accept “classroom hours only” |
| Duplicate 214 | Same PRO, no extra events | Idempotent event fingerprint (`status + time + city`) |

**RPO / RTO in one sentence each**

- **RPO:** How much EDI can we lose? Prefer “none of the raw files” (S3 versioning) even if we replay parse.
- **RTO:** How fast must the board come back? For this product, an hour is embarrassing; five minutes is a good bar for a single-region app.

## Cost

Numbers below are **order-of-magnitude teaching figures** for us-east-1, 2026, not a quote. Always re-check the AWS calculator before a real design review.

### This demo

| Setup | Monthly-ish cost | Catch |
|---|---|---|
| Laptop + SQLite | $0 | Fine for lessons 1–5 |
| Docker Compose | $0 | Needs Docker memory |
| Render free web + free Postgres | $0 | Sleeps at 15 min idle; DB expires at 30 days |
| Render starter web + starter Postgres | ~$15–25 | Always-on classroom |

### If we lifted the same design to AWS (low traffic)

Assume 50k 214s/month, tiny dashboard traffic.

| Service | Why | Ballpark |
|---|---|---|
| API Gateway + Lambda *or* one small Fargate task | Ingest + API | $5–25 |
| RDS Postgres db.t4g.micro | System of record | $15–30 (or Aurora Serverless v2 if spiky) |
| S3 | Raw 214 archive | cents |
| SQS + DLQ | Buffer | cents |
| SNS / SES | Delay mail | cents–a few dollars |
| CloudWatch | Logs | $2–10 if you are noisy |
| **Total** | | **roughly $25–70** |

### If a 3PL ran 2M 214s/day

The code path stays similar; the bill moves to:

- Always-on workers (ECS/EKS or a large reserved RDS)
- Multi-AZ + a read replica
- NAT, VPC endpoints, and log ingest (these surprise people more than Lambda)
- A VAN or SFTP landing zone (often a vendor invoice, not an AWS line)

Teaching question: **what do we pay for that we do not use at classroom scale?** Idle RDS, idle NAT gateways, and verbose logs. That is why the demo starts as one process.

### Cost decisions we already made

1. **No managed EDI vendor in the critical path.** Orderful/Stedi/Cleo would shrink `edi214.py` and add a monthly platform fee. Great later; they hide the lesson now.
2. **SQLite default.** Zero ops for lesson 1. Compose Postgres when you teach “stateful service vs. ephemeral filesystem.”
3. **Alerts default to logs.** Email looks impressive and then becomes spam + SES sandbox homework.
4. **One region.** Multi-region active-active is the wrong first availability lecture.

## Mapping this repo to AWS

| File / route | Local | AWS swap |
|---|---|---|
| `POST /api/ingest/edi214` | FastAPI | API Gateway or S3 PUT |
| `ingest_records` | Table | S3 object + optional Dynamo pointer |
| `app/edi214.py` | In-process | Lambda / ECS worker |
| `app/ingest.py` | SQLAlchemy | Same code, RDS |
| `GET /api/shipments` | FastAPI | API Gateway + ECS, Cognito later |
| `app/delays.py` + APScheduler | In-process cron | EventBridge rule |
| `app/notifications.py` | log / httpx / SMTP | SNS topic → Slack, SES, webhook |
| `frontend/` | Served by FastAPI | S3 + CloudFront |
| `.env` | File | Secrets Manager / SSM |
| `docker-compose.yml` | Two containers | ECS + RDS in a VPC |

## What “done” looks like in an interview

You should be able to draw the box diagram above from memory, then answer:

1. Why is ingest async once carriers batch?
2. How do you keep a replay from creating duplicate events?
3. Who is allowed to read a shipment?
4. What happens when the mail provider is down?
5. What is the first dollar you spend when this leaves a laptop?

If those five are crisp, the tech stack did its job.
