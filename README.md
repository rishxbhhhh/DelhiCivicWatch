# 🏛️ Delhi Civic Watch

> Report civic issues. Track resolutions. Hold your city accountable.

A crowd-sourced platform to report, track, and resolve civic issues across **Delhi's 70 assembly constituencies** and **250 MCD wards**. Inspired by Bengaluru's [NammaKasa](https://nammakasa.in).

**Live demo:** `https://delhi-civic-watch.fly.dev`  
**Source:** `https://github.com/rishxbhhhh/DelhiCivicWatch`  
**Tech:** FastAPI · SQLite · Leaflet.js · Fly.io · Telegram Bot

---

## ✨ Features

| Feature | Details |
|---------|---------|
| **Anonymous Reporting** | No name, no email, no login — submit issues instantly |
| **Photo Upload** | Up to 3 photos per report, captured directly from phone camera |
| **Location Tagging** | GPS auto-detect + tap-on-map fallback for iOS |
| **Image Compression** | Auto-resize to 1200px max → ~150KB per photo (saves 95% space) |
| **Interactive Map** | 70 constituencies with red circle markers sized by active complaints |
| **250 Real MCD Wards** | Post-2022 delimitation — wards filter by constituency |
| **Community Upvotes** | 👍 confirm an issue; 3+ upvotes = "Verified" badge |
| **Before/After Photos** | Resolution proof photo required — creates before→after comparison |
| **Constituency Leaderboard** | Ranked by resolution rate — which MLAs deliver? |
| **Weekly Digest** | Auto-summary of new vs resolved issues per constituency |
| **Telegram Alerts** | 🔔 Watch button → start the bot → instant notifications |
| **Email MCD Button** | 📧 On every complaint — auto-populates MCD zone + MLA in CC |
| **Storage Health Monitor** | Auto-pauses submissions at 90% disk with user-facing banner |
| **Resolution Tracking** | Mark resolved with proof photo + response time tracking |
| **Admin System** | 🔑 Env-secret login — admin can permanently delete complaints |
| **One-Click Upvote** | LocalStorage dedup — same user can't upvote a complaint twice |
| **Complaint Details Modal** | 👁 Eye icon opens full complaint with images, IST timestamp, all details |
| **4000-Char Limit** | Description capped at 4000 chars with live counter |
| **12 Issue Categories** | Garbage, Sewage, Potholes, Street Lights, Water Logging, and more |
| **Mobile Responsive** | Works on phone browsers, touch-friendly, camera-ready |
| **Pagination & Filters** | Browse 20/page, filter by ward/category/status/sort |

---

## 🚀 Quick Start

```powershell
cd C:\Users\rishabh\Desktop\delhi-issues-map
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`

**If port 8000 is taken:**
```powershell
for /f "tokens=5" %a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do taskkill //PID %a //F
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

---

## ☁️ Deploy to Fly.io (Free — $0/month)

The app runs on Fly.io's free tier — **3 VMs, 256MB RAM, 3GB persistent volume.**

### One-time setup

```powershell
# Install Fly CLI
iwr https://fly.io/install.ps1 -useb | iex

# Launch app
cd C:\Users\rishabh\Desktop\delhi-issues-map
fly launch
# → App name: delhi-civic-watch
# → Region: bom (Mumbai)
# → Database: no
# → Deploy: no (do volume first)

# Create persistent volume (DB + photos survive redeploys)
fly volumes create dcw_data --region bom --size 1

# Deploy
fly deploy
```

Your app → `https://delhi-civic-watch.fly.dev`

**Set admin credentials:**
```powershell
fly secrets set ADMIN_USERNAME=... ADMIN_PASSWORD=***
fly deploy
```
Then click 🔑 in the app header → login → ✕ delete buttons appear on every complaint.

---

## 🤖 Telegram Bot Setup

```powershell
# 1. Create bot: @BotFather → /newbot → DelhiCivicWatchBot
# 2. Set token on Fly:
fly secrets set TELEGRAM_BOT_TOKEN=123456:ABC-DEF...

# 3. Register webhook:
curl https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://delhi-civic-watch.fly.dev/api/telegram/webhook
```

**Bot commands:** `/start`, `/watch Karol Bagh`, `/status`, `/unwatch`

---

## 📧 Email Notifications (Brew/ free tier)

Telegram is live. Email uses Brevo (300/day free). Re-enable by:

1. Uncomment email form in `frontend/index.html` (lines ~218-228)
2. Uncomment JS handler in `frontend/script.js` (lines ~371-381)
3. Set secrets:
```powershell
fly secrets set BREVO_API_KEY=xkeysib-...  NOTIFICATION_EMAIL=you@email.com
fly deploy
```

---

## 📋 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Storage health, disk %, accepting_reports flag |
| GET | `/api/stats` | Total/active/resolved/upvote counts |
| GET | `/api/constituencies` | 70 constituencies + MLA + avg resolution time |
| GET | `/api/constituencies/leaderboard` | Ranked by resolution rate |
| GET | `/api/map-data` | GeoJSON boundary data (70 constituencies, 4.7MB) |
| GET | `/api/issues?offset=&limit=&category=&ward=&status=&sort=` | Paginated issues |
| POST | `/api/issues` | Submit issue (multipart: photos, location, anonymous) |
| POST | `/api/issues/{id}/upvote` | Community upvote |
| POST | `/api/issues/{id}/resolve` | Mark resolved (resolution photo **required**) |
| GET | `/api/categories` | 12 issue categories |
| GET | `/api/wards?constituency_id=` | 250 MCD wards (filtered by constituency) |
| GET | `/api/mcd-email?constituency_id=` | MCD zone + MLA email for "Email Authority" |
| POST | `/api/subscribe` | Subscribe (Telegram chat_id or email) |
| POST | `/api/telegram/webhook` | Telegram bot webhook |
| GET | `/api/digest` | Weekly activity summary |
| POST | `/api/unsubscribe` | Unsubscribe by token |
| POST | `/api/admin/login` | Admin login (username+password → token) |
| DELETE | `/api/admin/complaints/{id}` | Permanently delete complaint (admin token required) |
| GET | `/api/admin/check?token=` | Validate admin session |

---

## 🗺️ Project Structure

```
delhi-issues-map/
├── backend/
│   ├── main.py           # FastAPI server — 15+ endpoints
│   ├── models.py         # SQLAlchemy: Issue, WatchSubscription, 250 MCD_WARDS
│   └── schemas.py        # Pydantic: 10+ request/response schemas
├── frontend/
│   ├── index.html        # Multi-view SPA (map/list/leaderboard/digest)
│   ├── style.css         # Dark header, stats bar, responsive
│   └── script.js         # Map, pagination, upvotes, Telegram, MCD email
├── data/
│   └── delhi_constituencies.geojson  # 70 constituencies, 4.7MB
├── uploads/              # User-submitted photos (on Fly volume in prod)
├── Dockerfile            # Multi-stage build
├── fly.toml              # Fly.io config (Mumbai, 256MB, 1GB volume)
├── docker-compose.yml    # Local PostgreSQL + nginx stack
├── nginx.conf            # Rate limiting, gzip, 20MB upload cap
├── railway.json          # Railway deployment config
├── MARKETING.md          # SEO, Reddit, X, WhatsApp growth playbook
└── requirements.txt
```

---

## 🛠️ Troubleshooting

| Issue | Fix |
|-------|-----|
| Port 8000 occupied | `for /f "tokens=5" %a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do taskkill //PID %a //F` |
| Bot not responding | `fly deploy` then `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo` — check `last_error_message` |
| Register webhook | `curl https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://delhi-civic-watch.fly.dev/api/telegram/webhook` |
| Check webhook status | `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo` |
| Delete & re-register | `curl https://api.telegram.org/bot<TOKEN>/deleteWebhook` then `setWebhook` again |
| Storage full | `fly ssh console` → `df -h` → `fly volumes extend dcw_data --size 2` |
| DB schema changed | `fly ssh console` → `rm /app/storage/issues.db` → `fly deploy` |
| Check app health | `curl https://delhi-civic-watch.fly.dev/api/health` |
| View logs | `fly logs` |
| Reset dev DB | `del issues.db` while server is stopped |

---

## 📈 Technology

| Layer | Choice | Why |
|-------|--------|-----|
| Backend | FastAPI 3.11 | Async, auto-OpenAPI, fastest Python framework |
| Database | SQLite / PostgreSQL | SQLite for free tier; PG for scale |
| Frontend | Leaflet.js + Vanilla JS | No framework overhead, mobile-friendly |
| Map data | GeoJSON (70 polygons, 4.7MB) | Official Delhi delimitation data |
| Hosting | Fly.io free tier | $0 forever, Mumbai region, auto-HTTPS |
| Images | Compressed JPEG, 1200px max | Pillow resize + quality=75, ~150KB/photo |
| Notifications | Telegram Bot API | Instant, free, unlimited |
| CI/CD | Fly.io + Git push | `git push` → auto-deploy |

---

## 🧠 Lessons Learned

- **Volume mounts overwrite directories.** GeoJSON was in `data/`. Volume at `/app/data` hid it. Solution: separate paths (`/app/storage` for DB/uploads, `data/` stays in source).
- **SQLite handles 1K users fine.** Single-writer, reads are fast. Civic complaints aren't high-write-volume.
- **iPhone geolocation requires HTTPS.** iOS blocks GPS without TLS. Fallback: pick-on-map.

---

## 📜 License

Built by Rishabh Rajpurohit. Inspired by NammaKasa, Bangalore. Open source under MIT.
