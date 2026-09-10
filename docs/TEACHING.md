# How to teach this (Oscar → student)

Audience: someone pivoting into cloud who does not need to become an EDI specialist.

## Ground rules

- Run the app before opening AWS console screenshots. Cloud names stick after a thing has been seen.
- One file at a time. Do not tour the whole repo on day one.
- When she asks “would a company really…?” answer from `docs/ARCHITECTURE.md`, not from extra features.

## Session 1 — Make a 214 real (45–60 min)

1. Start with a story: coffee left Chicago, buyer is in Milwaukee, carrier sends status.
2. Open `samples/01_enroute_ontime.edi`. Decode B10, N1, AT7 together.
3. `uvicorn` + dashboard. Click the FLOCK bill. Match tape ↔ file.
4. Ingest the A9 sample. Watch the red stamp and the alert list.
5. Homework: change a city in a sample and re-ingest. What updates? What stays (PRO)?

## Session 2 — APIs and keys (45 min)

1. `/docs` Swagger. GET list, GET one id.
2. POST without `X-API-Key` → 401.
3. Explain: the board is a client; so is a customer portal.
4. Homework: `curl` a delayed filter. Sketch who would hold the key in a real company.

## Session 3 — Cloud mapping (60 min)

1. Draw the table in the README on a whiteboard. She fills the AWS column.
2. Docker Compose: “two services, one network.” Name VPC + security groups.
3. Cost: laptop $0 vs Render free vs ~$40 AWS classroom.
4. Availability: kill the API process, watch the board fail, talk Multi-AZ.
5. Homework: she explains RPO vs RTO using the raw `ingest_records` idea.

## If you only have one evening

Do Session 1 + the 401 curl. Assign the architecture doc as reading. The goal is “I can follow a message through a system,” not “I can recite X12 element 1650.”
