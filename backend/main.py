import json
import os
import uuid
import secrets
import shutil
from io import BytesIO
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from PIL import Image

from backend.models import SessionLocal, Issue, WatchSubscription, MCD_WARDS, CONSTITUENCY_WARDS
from backend.models import DATABASE_URL
from backend.models import MCD_ZONE_EMAILS, CONSTITUENCY_MCD_ZONE
from backend.admin_auth import authenticate, validate_token, ADMIN_USERNAME, ADMIN_PASSWORD
from backend.schemas import (
    IssueCreate, IssueResponse, IssueListResponse,
    ConstituencyInfo, IssueStats, SubscribeRequest, SubscribeResponse,
    ConstituencyLeaderboard, WeeklyDigest, DigestEntry,
)

app = FastAPI(title="Delhi Civic Watch — Report & Track Civic Issues")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEOJSON_PATH = os.path.join(BASE_DIR, "data", "delhi_constituencies.geojson")

# On Fly.io, use persistent volume for uploads
DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

CATEGORIES = [
    "Garbage Dumping", "Sewage & Drainage", "Potholes & Roads",
    "Street Lights", "Water Logging", "Open Manhole",
    "Illegal Construction", "Public Toilet", "Stray Animals",
    "Air Pollution", "Noise Pollution", "Other",
]


def load_geojson():
    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def compute_centroid(geometry):
    if geometry["type"] == "MultiPolygon":
        coords = geometry["coordinates"][0][0]
    elif geometry["type"] == "Polygon":
        coords = geometry["coordinates"][0]
    else:
        return None, None
    if not coords:
        return None, None
    lats = [c[1] for c in coords]
    lngs = [c[0] for c in coords]
    return sum(lats) / len(lats), sum(lngs) / len(lngs)


def compress_image(file_bytes: bytes, max_size: int = 1200, quality: int = 75) -> bytes:
    """Resize and compress an image to reduce storage. ~4MB → ~150KB."""
    img = Image.open(BytesIO(file_bytes))
    # Convert RGBA/P to RGB for JPEG
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    # Resize if larger than max_size on longest side
    if max(img.size) > max_size:
        ratio = max_size / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    # Compress to JPEG
    out = BytesIO()
    img.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue()


def check_storage() -> dict:
    """Returns disk usage stats. Flags warning at 80%, critical at 90%."""
    # Check uploads directory disk usage
    usage = shutil.disk_usage(UPLOADS_DIR)
    total_gb = usage.total / (1024 ** 3)
    used_gb = usage.used / (1024 ** 3)
    free_gb = usage.free / (1024 ** 3)
    pct_used = (usage.used / usage.total) * 100

    # Check DB file size
    db_path = DATABASE_URL.replace("sqlite:///", "")
    if not os.path.isabs(db_path):
        db_path = os.path.join(BASE_DIR, db_path)
    db_size_mb = os.path.getsize(db_path) / (1024 * 1024) if os.path.exists(db_path) else 0

    # Determine status
    if pct_used >= 90:
        status = "critical"
        message = "Storage is nearly full. New reports are temporarily paused. Admin has been notified."
    elif pct_used >= 80:
        status = "warning"
        message = "Storage is running low. Reports still accepted but admin should expand storage soon."
    else:
        status = "healthy"
        message = None

    return {
        "status": status,
        "message": message,
        "disk": {
            "total_gb": round(total_gb, 2),
            "used_gb": round(used_gb, 2),
            "free_gb": round(free_gb, 2),
            "pct_used": round(pct_used, 1),
        },
        "db_size_mb": round(db_size_mb, 2),
    }


STORAGE_THRESHOLD = 90  # Block submissions when disk is 90% full

# Telegram Bot Config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else ""
APP_URL = os.getenv("APP_URL", "http://localhost:8000")

# Brevo (Sendinblue) — 300 free emails/day
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL", "alerts@delhicivicwatch.in")


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send email via Brevo API. Returns True if sent."""
    if not BREVO_API_KEY:
        return False
    try:
        import urllib.request, json as _json
        payload = _json.dumps({
            "sender": {"name": "Delhi Civic Watch", "email": NOTIFICATION_EMAIL},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_body,
        }).encode()
        req = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=payload,
            headers={
                "api-key": BREVO_API_KEY,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False


def send_telegram(chat_id: str, text: str) -> bool:
    """Send a message to a Telegram chat. Returns True if sent."""
    if not TELEGRAM_BOT_TOKEN:
        return False
    try:
        import urllib.request, urllib.parse
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(f"{TELEGRAM_API}/sendMessage", data=data)
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception:
        return False


def notify_subscribers(constituency_id: str, constituency_name: str, issue_summary: str, category: str, is_new: bool = True):
    """Notify Telegram AND email subscribers when an issue is created or resolved."""
    db = SessionLocal()
    try:
        # --- Telegram subscribers ---
        tg_subs = db.query(WatchSubscription).filter(
            WatchSubscription.chat_id.isnot(None),
            (WatchSubscription.constituency_id == constituency_id) |
            (WatchSubscription.constituency_id.is_(None))
        ).all()

        if is_new:
            tg_text = (
                f"🆕 <b>New Issue in {constituency_name}</b>\n"
                f"📂 {category}\n"
                f"📝 {issue_summary[:200]}\n\n"
                f"<a href=\"{APP_URL}\">View on Delhi Civic Watch</a>"
            )
            email_subject = f"🆕 New Issue in {constituency_name}"
        else:
            tg_text = (
                f"✅ <b>Issue Resolved in {constituency_name}</b>\n"
                f"📝 {issue_summary[:200]}\n\n"
                f"<a href=\"{APP_URL}\">View on Delhi Civic Watch</a>"
            )
            email_subject = f"✅ Issue Resolved in {constituency_name}"

        for sub in tg_subs:
            send_telegram(sub.chat_id, tg_text)

        # --- Email subscribers ---
        email_subs = db.query(WatchSubscription).filter(
            WatchSubscription.email.isnot(None),
            (WatchSubscription.constituency_id == constituency_id) |
            (WatchSubscription.constituency_id.is_(None))
        ).all()

        if email_subs:
            email_body = f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;padding:20px;">
                <h2>{'🆕 New Issue' if is_new else '✅ Issue Resolved'} in {constituency_name}</h2>
                <p><strong>Category:</strong> {category}</p>
                <p><strong>Issue:</strong> {issue_summary[:300]}</p>
                <hr>
                <p><a href="{APP_URL}" style="color:#d93025;">View on Delhi Civic Watch</a></p>
                <p style="color:#999;font-size:12px;">You received this because you subscribed to alerts for {constituency_name or 'all of Delhi'}.
                To unsubscribe, reply to this email.</p>
            </div>
            """
            for sub in email_subs:
                send_email(sub.email, email_subject, email_body)
    finally:
        db.close()


# ═══════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════
@app.get("/api/health")
def health_check():
    storage = check_storage()
    return {
        "alive": True,
        "storage": storage,
        "accepting_reports": storage["status"] != "critical",
    }
# STATS
# ═══════════════════════════════════════════════
@app.get("/api/stats", response_model=IssueStats)
def get_stats(db: Session = Depends(get_db)):
    total = db.query(Issue).count()
    resolved = db.query(Issue).filter(Issue.resolved == True).count()
    total_upvotes = db.query(func.coalesce(func.sum(Issue.upvotes), 0)).scalar()
    return IssueStats(
        total_reports=total,
        total_active=total - resolved,
        total_resolved=resolved,
        total_upvotes=int(total_upvotes),
    )


# ═══════════════════════════════════════════════
# CONSTITUENCIES
# ═══════════════════════════════════════════════
@app.get("/api/constituencies")
def get_constituencies(db: Session = Depends(get_db)):
    geojson = load_geojson()
    constituencies = []
    for feature in geojson["features"]:
        props = feature["properties"]
        const_id = str(props["id"])
        issues = db.query(Issue).filter(Issue.constituency_id == const_id)
        issue_count = issues.count()
        resolved_count = issues.filter(Issue.resolved == True).count()
        lat, lng = compute_centroid(feature["geometry"])

        # Average resolution time
        resolved_issues = issues.filter(
            Issue.resolved == True,
            Issue.resolved_at.isnot(None),
            Issue.created_at.isnot(None),
        ).all()
        if resolved_issues:
            total_hours = sum(
                (r.resolved_at - r.created_at).total_seconds() / 3600
                for r in resolved_issues
            )
            avg_hours = round(total_hours / len(resolved_issues), 1)
        else:
            avg_hours = None

        constituencies.append(ConstituencyInfo(
            id=const_id,
            name=props["name"],
            mla=props["mla"],
            party=props["party"],
            color=props["color"],
            issue_count=issue_count,
            resolved_count=resolved_count,
            active_count=issue_count - resolved_count,
            avg_resolution_hours=avg_hours,
            address=props.get("address"),
            contact_number=props.get("number"),
            email=props.get("email"),
            latitude=lat,
            longitude=lng,
        ))
    return constituencies


@app.get("/api/map-data")
def get_map_data():
    return load_geojson()


@app.get("/api/constituencies/leaderboard", response_model=list[ConstituencyLeaderboard])
def get_leaderboard(db: Session = Depends(get_db)):
    constituencies = get_constituencies(db=db)
    leaderboard = []
    for c in constituencies:
        total = c.issue_count
        if total == 0:
            continue
        resolution_rate = round((c.resolved_count / total) * 100, 1)
        upvotes = db.query(func.coalesce(func.sum(Issue.upvotes), 0)).filter(
            Issue.constituency_id == c.id
        ).scalar()
        leaderboard.append(ConstituencyLeaderboard(
            rank=0,
            constituency_id=c.id,
            name=c.name,
            mla=c.mla,
            party=c.party,
            total_reports=total,
            active=c.active_count,
            resolved=c.resolved_count,
            resolution_rate=resolution_rate,
            avg_resolution_hours=c.avg_resolution_hours,
            upvotes=int(upvotes),
        ))
    leaderboard.sort(key=lambda x: (-x.resolution_rate, x.avg_resolution_hours or 99999))
    for i, item in enumerate(leaderboard):
        item.rank = i + 1
    return leaderboard


# ═══════════════════════════════════════════════
# ISSUES (paginated)
# ═══════════════════════════════════════════════
@app.get("/api/issues", response_model=IssueListResponse)
def get_issues(
    constituency_id: Optional[str] = None,
    ward: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    sort: Optional[str] = "newest",
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Issue)
    if constituency_id:
        query = query.filter(Issue.constituency_id == constituency_id)
    if ward:
        query = query.filter(Issue.ward == ward)
    if category and category != "All":
        query = query.filter(Issue.issue_category == category)
    if status == "active":
        query = query.filter(Issue.resolved == False)
    elif status == "resolved":
        query = query.filter(Issue.resolved == True)

    total = query.count()

    if sort == "upvotes":
        query = query.order_by(Issue.upvotes.desc(), Issue.created_at.desc())
    elif sort == "oldest":
        query = query.order_by(Issue.created_at.asc())
    else:
        query = query.order_by(Issue.created_at.desc())

    issues = query.offset(offset).limit(limit).all()
    return IssueListResponse(
        issues=[IssueResponse.model_validate(i) for i in issues],
        total=total,
        offset=offset,
        limit=limit,
        has_more=(offset + limit) < total,
    )


@app.post("/api/issues", response_model=IssueResponse)
async def create_issue(
    constituency_id: str = Form(...),
    issue_summary: str = Form(...),
    issue_category: Optional[str] = Form("Garbage"),
    ward: Optional[str] = Form(None),
    mla_name: Optional[str] = Form(None),
    complainant_name: Optional[str] = Form(None),
    complainant_address: Optional[str] = Form(None),
    contact_number: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    images: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    # Block submissions if storage is critically full
    storage = check_storage()
    if storage["status"] == "critical":
        raise HTTPException(
            status_code=503,
            detail="Storage full — reports temporarily paused. Admin is working on it. Please check back soon.",
        )

    image_paths = []
    for img in images[:3]:
        if img.filename and img.filename.strip():
            content = await img.read()
            compressed = compress_image(content)
            filename = f"{uuid.uuid4().hex}.jpg"
            filepath = os.path.join(UPLOADS_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(compressed)
            image_paths.append(filename)

    db_issue = Issue(
        constituency_id=str(constituency_id),
        ward=ward,
        mla_name=mla_name,
        complainant_name=complainant_name or "Anonymous",
        complainant_address=complainant_address,
        contact_number=contact_number,
        issue_summary=issue_summary,
        issue_category=issue_category,
        latitude=latitude,
        longitude=longitude,
        images=json.dumps(image_paths) if image_paths else None,
    )
    db.add(db_issue)
    db.commit()
    db.refresh(db_issue)

    # Notify Telegram subscribers
    geojson = load_geojson()
    const_name = constituency_id
    for f in geojson.get("features", []):
        if str(f["properties"]["id"]) == str(constituency_id):
            const_name = f["properties"]["name"]
            break
    notify_subscribers(constituency_id, const_name, issue_summary, issue_category or "General", is_new=True)

    return db_issue


# ═══════════════════════════════════════════════
# UPVOTE
# ═══════════════════════════════════════════════
@app.post("/api/issues/{issue_id}/upvote")
def upvote_issue(issue_id: int, db: Session = Depends(get_db)):
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    issue.upvotes = (issue.upvotes or 0) + 1
    db.commit()
    return {"upvotes": issue.upvotes, "verified": issue.upvotes >= 3}


# ═══════════════════════════════════════════════
# RESOLVE (with optional photo)
# ═══════════════════════════════════════════════
@app.post("/api/issues/{issue_id}/resolve")
async def resolve_issue(
    issue_id: int,
    resolution_photo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    if not resolution_photo or not resolution_photo.filename:
        raise HTTPException(status_code=400, detail="Resolution photo is required to mark as resolved")

    content = await resolution_photo.read()
    compressed = compress_image(content)
    filename = f"resolved_{uuid.uuid4().hex}.jpg"
    filepath = os.path.join(UPLOADS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(compressed)
    issue.resolution_photo = filename

    issue.resolved = True
    issue.resolved_at = datetime.utcnow()
    db.commit()

    # Notify Telegram subscribers
    geojson = load_geojson()
    const_name = issue.constituency_id
    for f in geojson.get("features", []):
        if str(f["properties"]["id"]) == str(issue.constituency_id):
            const_name = f["properties"]["name"]
            break
    notify_subscribers(issue.constituency_id, const_name, issue.issue_summary, issue.issue_category or "General", is_new=False)

    return {
        "status": "resolved",
        "resolution_photo": issue.resolution_photo,
        "resolved_at": issue.resolved_at.isoformat() if issue.resolved_at else None,
    }


# ═══════════════════════════════════════════════
# SUBSCRIPTIONS
# ═══════════════════════════════════════════════
@app.post("/api/subscribe", response_model=SubscribeResponse)
def subscribe(body: SubscribeRequest, db: Session = Depends(get_db)):
    # Telegram subscription
    if body.chat_id:
        existing = db.query(WatchSubscription).filter(
            WatchSubscription.chat_id == body.chat_id,
            WatchSubscription.constituency_id == body.constituency_id,
        ).first()
        if existing:
            return SubscribeResponse(message="Already watching this area on Telegram!")
        sub = WatchSubscription(
            chat_id=body.chat_id,
            constituency_id=body.constituency_id,
            ward=body.ward,
            verified=True,
        )
        db.add(sub)
        db.commit()
        const_name = body.constituency_id or "all of Delhi"
        send_telegram(body.chat_id, f"🔔 You're now watching <b>{const_name}</b>! You'll get alerts for new and resolved issues here.")
        return SubscribeResponse(message="Subscribed on Telegram!")

    # Legacy email subscription
    if body.email:
        existing = db.query(WatchSubscription).filter(
            WatchSubscription.email == body.email,
            WatchSubscription.constituency_id == body.constituency_id,
        ).first()
        if existing:
            return SubscribeResponse(message="Already subscribed to this area!")
        token = secrets.token_urlsafe(16)
        sub = WatchSubscription(
            email=body.email,
            constituency_id=body.constituency_id,
            ward=body.ward,
            unsubscribe_token=token,
        )
        db.add(sub)
        db.commit()
        return SubscribeResponse(message=f"Subscribed! Unsubscribe token: {token}")

    raise HTTPException(status_code=400, detail="Provide chat_id (Telegram) or email")


@app.get("/api/unsubscribe")
def unsubscribe(token: str, db: Session = Depends(get_db)):
    sub = db.query(WatchSubscription).filter(
        WatchSubscription.unsubscribe_token == token
    ).first()
    if not sub:
        return SubscribeResponse(message="Invalid or expired token.", unsubscribed=False)
    db.delete(sub)
    db.commit()
    return SubscribeResponse(message="Unsubscribed successfully.", unsubscribed=True)


@app.get("/api/subscriptions/count")
def subscription_count(db: Session = Depends(get_db)):
    return {"total": db.query(WatchSubscription).count()}


@app.get("/api/digest", response_model=WeeklyDigest)

@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request, db=Depends(get_db)):
    """Telegram sends updates here. Captures chat_id on /start."""
    try:
        data = await request.json()
        msg = data.get("message", {})
        chat = msg.get("chat", {})
        text = msg.get("text", "")
        chat_id = str(chat.get("id", ""))

        if not chat_id:
            return {"ok": True}

        if text.startswith("/start"):
            # Check if already subscribed
            existing = db.query(WatchSubscription).filter(
                WatchSubscription.chat_id == chat_id
            ).first()
            if existing:
                send_telegram(chat_id,
                    "👋 You're already subscribed! Use these commands:\n\n"
                    "📌 <b>Commands:</b>\n"
                    "/watch Narela — watch a specific constituency\n"
                    "/unwatch — stop all alerts\n"
                    "/status — see your subscriptions"
                )
            else:
                # Subscribe to all Delhi by default
                sub = WatchSubscription(chat_id=chat_id, verified=True)
                db.add(sub)
                db.commit()
                send_telegram(chat_id,
                    "🏛️ <b>Welcome to Delhi Civic Watch!</b>\n\n"
                    "You'll receive alerts for new and resolved civic issues across Delhi.\n\n"
                    "📌 <b>Commands:</b>\n\n"
                    "🔹 <b>Subscribe to a constituency:</b>\n"
                    "/watch Karol Bagh\n"
                    "/watch Narela\n"
                    "/watch Burari\n"
                    "...or any of the 70 Delhi constituencies.\n\n"
                    "🔹 <b>Unsubscribe:</b>\n"
                    "/unwatch — stop all alerts\n\n"
                    "🔹 <b>Check subscriptions:</b>\n"
                    "/status — see which areas you're watching\n\n"
                    "🔹 <b>Watch all of Delhi (default):</b>\n"
                    "/start — you're already subscribed to all Delhi!\n\n"
                    "<i>You can run /watch multiple times to watch several constituencies.\n"
                    "Example: /watch Karol Bagh then /watch Rohini watches both.</i>"
                )
        elif text.startswith("/unwatch"):
            db.query(WatchSubscription).filter(WatchSubscription.chat_id == chat_id).delete()
            db.commit()
            send_telegram(chat_id, "👋 You've been unsubscribed. Thank you for participating!")
        elif text.startswith("/status"):
            subs = db.query(WatchSubscription).filter(WatchSubscription.chat_id == chat_id).all()
            if not subs:
                send_telegram(chat_id, "You're not watching any areas. Send /start to subscribe.")
            else:
                areas = [s.constituency_id or "All Delhi" for s in subs]
                send_telegram(chat_id, f"🔔 Watching: {', '.join(areas)}")
        elif text.startswith("/watch"):
            parts = text.split(" ", 1)
            if len(parts) > 1:
                area = parts[1].strip()
                # Remove old all-Delhi subs, add specific
                db.query(WatchSubscription).filter(WatchSubscription.chat_id == chat_id, WatchSubscription.constituency_id.is_(None)).delete()
                existing = db.query(WatchSubscription).filter(WatchSubscription.chat_id == chat_id, WatchSubscription.constituency_id == area).first()
                if not existing:
                    sub = WatchSubscription(chat_id=chat_id, constituency_id=area, verified=True)
                    db.add(sub)
                db.commit()
                send_telegram(chat_id, f"🔔 Now watching <b>{area}</b>! You'll get alerts for issues here.")
            else:
                send_telegram(chat_id, "Usage: /watch ConstituencyName\nExample: /watch Karol Bagh")
    except Exception:
        pass
    return {"ok": True}
def get_weekly_digest(db: Session = Depends(get_db)):
    week_ago = datetime.utcnow() - timedelta(days=7)
    new_issues = db.query(Issue).filter(Issue.created_at >= week_ago).all()
    resolved_issues = db.query(Issue).filter(
        Issue.resolved == True, Issue.resolved_at >= week_ago
    ).all()

    geojson = load_geojson()
    const_map = {str(f["properties"]["id"]): f["properties"]["name"] for f in geojson["features"]}

    by_constituency = {}
    for issue in new_issues:
        cid = issue.constituency_id
        if cid not in by_constituency:
            by_constituency[cid] = {"new": 0, "resolved": 0, "categories": {}}
        by_constituency[cid]["new"] += 1
        cat = issue.issue_category or "Other"
        by_constituency[cid]["categories"][cat] = by_constituency[cid]["categories"].get(cat, 0) + 1

    for issue in resolved_issues:
        cid = issue.constituency_id
        if cid not in by_constituency:
            by_constituency[cid] = {"new": 0, "resolved": 0, "categories": {}}
        by_constituency[cid]["resolved"] += 1

    entries = []
    for cid, data in by_constituency.items():
        top_cat = max(data["categories"], key=data["categories"].get) if data["categories"] else "None"
        entries.append(DigestEntry(
            constituency_name=const_map.get(cid, cid),
            new_issues=data["new"],
            resolved_issues=data["resolved"],
            top_category=top_cat,
            total_active=data["new"] - data["resolved"],
        ))

    return WeeklyDigest(
        week_start=week_ago.strftime("%Y-%m-%d"),
        week_end=datetime.utcnow().strftime("%Y-%m-%d"),
        total_new=len(new_issues),
        total_resolved=len(resolved_issues),
        constituencies=entries,
    )


# ═══════════════════════════════════════════════
# WARDS
# ═══════════════════════════════════════════════
@app.get("/api/wards")
def get_wards(constituency_id: Optional[str] = None):
    if constituency_id:
        return CONSTITUENCY_WARDS.get(str(constituency_id), [])
    # Return all wards as flat list of names
    return [w[0] for w in MCD_WARDS]


@app.get("/api/categories")
def get_categories():
    return CATEGORIES


@app.get("/api/mcd-email")
def get_mcd_email(constituency_id: str):
    """Return MCD zone email and MLA email for a constituency."""
    zone = CONSTITUENCY_MCD_ZONE.get(str(constituency_id))
    mcd_email = MCD_ZONE_EMAILS.get(zone) if zone else None

    # Find MLA email from GeoJSON
    mla_email = None
    mla_name = None
    geojson = load_geojson()
    for f in geojson.get("features", []):
        if str(f["properties"]["id"]) == str(constituency_id):
            mla_email = f["properties"].get("email")
            mla_name = f["properties"].get("mla")
            break

    return {
        "constituency_id": constituency_id,
        "mcd_zone": zone,
        "mcd_email": mcd_email,
        "mla_email": mla_email,
        "mla_name": mla_name,
    }


@app.get("/uploads/{filename}")
def serve_upload(filename: str):
    filepath = os.path.join(UPLOADS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404)
    return FileResponse(filepath)


# ═══════════════════════════════════════════════
# ADMIN
# ═══════════════════════════════════════════════
@app.post("/api/admin/login")
def admin_login(data: dict):
    username = data.get("username", "")
    password = data.get("password", "")
    token = authenticate(username, password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": token, "username": username}


@app.get("/api/admin/check")
def admin_check(token: str):
    if not validate_token(token):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"authenticated": True}


@app.delete("/api/admin/complaints/{issue_id}")
def admin_delete_complaint(issue_id: int, token: str, db: Session = Depends(get_db)):
    if not validate_token(token):
        raise HTTPException(status_code=401, detail="Admin access required")
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Complaint not found")
    db.delete(issue)
    db.commit()
    return {"deleted": issue_id}


# Mount frontend LAST
frontend_dir = os.path.join(BASE_DIR, "frontend")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
