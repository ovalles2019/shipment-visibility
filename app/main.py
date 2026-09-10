from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, SessionLocal, engine, get_db
from app.delays import scan_and_notify
from app.edi214 import EDIParseError
from app.ingest import ingest_edi
from app.models import Notification, Shipment
from app.schemas import IngestRequest, IngestResponse, NotificationOut, StatsOut
from app.seed import load_samples, seed_if_empty
from app.serialize import shipment_detail, shipment_out
from app.status_codes import bucket_for

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("shipvis")

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
SAMPLES = ROOT / "samples"
scheduler = BackgroundScheduler()


def _scheduled_delay_scan() -> None:
    db = SessionLocal()
    try:
        created = scan_and_notify(db)
        if created:
            log.info("Delay scan created %s notification(s)", created)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not settings.skip_seed:
            n = seed_if_empty(db)
            if n:
                log.info("Seeded %s sample EDI files", n)
    finally:
        db.close()
    scheduler.add_job(
        _scheduled_delay_scan,
        "interval",
        minutes=max(1, settings.delay_check_minutes),
        id="delay-scan",
        replace_existing=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Shipment Visibility",
    description="Teaching platform: ingest EDI 214, normalize events, expose status, alert on delays.",
    lifespan=lifespan,
)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key")


@app.get("/health")
def health():
    return {"status": "ok", "service": "shipment-visibility"}


@app.get("/api/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db)):
    rows = db.query(Shipment).all()
    buckets = {"in_transit": 0, "delayed": 0, "delivered": 0, "exception": 0}
    for row in rows:
        buckets[bucket_for(row.current_status, row.overdue)] += 1
    return StatsOut(
        total=len(rows),
        notifications=db.query(Notification).count(),
        **buckets,
    )


@app.get("/api/shipments")
def list_shipments(
    bucket: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    rows = db.query(Shipment).order_by(Shipment.updated_at.desc()).all()
    out = [shipment_out(r) for r in rows]
    if bucket:
        out = [s for s in out if s.bucket == bucket]
    if q:
        needle = q.lower()
        out = [
            s
            for s in out
            if needle in s.pro_number.lower()
            or needle in s.shipper_name.lower()
            or needle in s.consignee_name.lower()
            or needle in s.po_number.lower()
        ]
    return out


@app.get("/api/shipments/{shipment_id}")
def get_shipment(shipment_id: int, db: Session = Depends(get_db)):
    row = db.get(Shipment, shipment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return shipment_detail(row)


@app.get("/api/notifications", response_model=list[NotificationOut])
def list_notifications(db: Session = Depends(get_db)):
    return (
        db.query(Notification)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )


@app.post("/api/ingest/edi214", response_model=IngestResponse, dependencies=[Depends(require_api_key)])
def ingest(req: IngestRequest, db: Session = Depends(get_db)):
    try:
        shipment, events_added, alerts = ingest_edi(db, req.content, req.filename)
    except EDIParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return IngestResponse(
        shipment=shipment_detail(shipment),
        events_added=events_added,
        delay_alerts=alerts,
    )


@app.post("/api/ingest/samples", dependencies=[Depends(require_api_key)])
def ingest_samples(db: Session = Depends(get_db)):
    loaded = load_samples(db)
    return {"loaded": loaded}


@app.post("/api/delays/check", dependencies=[Depends(require_api_key)])
def check_delays(db: Session = Depends(get_db)):
    created = scan_and_notify(db)
    return {"notifications_created": created}


@app.get("/samples/{filename}")
def sample_file(filename: str):
    path = (SAMPLES / filename).resolve()
    if path.parent != SAMPLES.resolve() or path.suffix != ".edi" or not path.is_file():
        raise HTTPException(status_code=404, detail="Sample not found")
    return FileResponse(path, media_type="text/plain")


if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

    @app.get("/")
    def dashboard():
        return FileResponse(FRONTEND / "index.html")
