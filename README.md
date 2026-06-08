# Delhi Civic Watch

Crowd-sourced civic issue reporting and tracking for Delhi's 70 assembly constituencies. Report garbage, potholes, sewage, broken lights, and more — then track resolutions publicly.

**Live at** `http://localhost:8000`

---

## Features (Implemented)

| Feature | Status | Description |
|---------|--------|-------------|
| Anonymous Reporting | ✅ Done | No name required — submit issues without personal info |
| Photo Upload (up to 3) | ✅ Done | Camera capture on mobile, up to 3 photos per complaint |
| Location Tagging | ✅ Done | GPS auto-detect + tap-on-map fallback when GPS denied (iOS fix) |
| Red Circle Map | ✅ Done | Constituency-level active complaint counts as red circles (size = severity) |
| 70 Constituencies | ✅ Done | Full Delhi assembly boundaries with MLA details (name, party, contact, email) |
| Email MLA | ✅ Done | One-tap compose email to constituency MLA |
| Pagination | ✅ Done | Browse issues with page controls, 20 per page |
| Filters & Sort | ✅ Done | Filter by category, ward, status; sort by newest/oldest/most upvoted |
| List View | ✅ Done | Tabular browsing of all reported issues |
| Community Upvotes | ✅ Done | Citizens confirm issues with 👍; 3+ upvotes = "Verified" badge |
| Before/After Photos | ✅ Done | Resolution photo upload creates before→after comparison |
| Watch Subscription | ✅ Done | Telegram bot + Email alerts — tap to subscribe, instant notifications |
| Ward-Level Filtering | ✅ Done | 250 real MCD wards (post-2022 delimitation), filtered by constituency |
| Constituency Leaderboard | ✅ Done | Ranked by resolution rate — which MLAs deliver? |
| Weekly Digest | ✅ Done | Auto-generated summary: new vs resolved per constituency this week |
| Resolution Tracking | ✅ Done | Mark as resolved with **required** proof photo + response time tracking |
| Upvote Dedup | ✅ Done | One upvote per browser (localStorage) — no double-voting |
| Mobile Responsive | ✅ Done | Works on phone browsers, camera integration, touch-friendly UI |
| 12 Issue Categories | ✅ Done | Garbage, Sewage, Potholes, Roads, Lights, Water, Manholes, Construction, Toilets, Animals, Air, Noise |

---

## Quick Start

```bash
cd delhi-issues-map
pip install -r requirements.txt

# First time or if port is free:
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# If port 8000 is still occupied from a previous run:
taskkill //F //IM python.exe 2>nul & python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Open http://localhost:8000
```

For phone access on same WiFi: use your PC's local IP (e.g., `http://192.168.x.x:8000`)

---

## Free Deployment ($0/month — Fly.io)

Best option for a civic project: Fly.io free tier never expires.

| Resource | Free tier | Enough for |
|----------|-----------|------------|
| App hosting | 3 VMs, 256MB RAM | ~1,000 concurrent users |
| Storage | 3GB persistent volume | ~10,000 photos + DB |
| HTTPS | Auto-provisioned | Yes |
| Domain | `yourapp.fly.dev` | Free, looks professional |
| Cost | **$0/month forever** | No credit card tricks |

**Deploy in 3 commands:**

```bash
# 1. Install Fly CLI
curl -L https://fly.io/install.sh | sh

# 2. Launch (creates app + provisions VM)
fly launch

# 3. Create persistent volume for DB and uploads
fly volumes create dcw_data --region bom --size 1
fly deploy
```

Your app is live at `https://delhi-civic-watch.fly.dev` (or rename in fly.toml).

**Set up notifications (Telegram + Email):**

### Telegram (instant, free, unlimited)
1. Open Telegram → `@BotFather` → `/newbot` → name: `Delhi Civic Watch` → username: `@DelhiCivicWatchBot`
2. Copy the token:
   ```powershell
   fly secrets set TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234gh
   ```
3. Register the webhook:
   ```powershell
   curl https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://delhi-civic-watch.fly.dev/api/telegram/webhook
   ```

### Email (Brevo — 300 free emails/day)
1. Sign up at [brevo.com](https://brevo.com) → get API key from SMTP & API → API Keys
2. Verify a sender email in Brevo (e.g. `alerts@delhicivicwatch.in`)
3. Set the secrets:
   ```powershell
   fly secrets set BREVO_API_KEY=xkeysib-...  NOTIFICATION_EMAIL=alerts@delhicivicwatch.in
   ```
4. Redeploy: `fly deploy`

Test both: tap "🔔 Watch" on any constituency → pick Telegram or Email → submit an issue in that area → you'll get notified.

**Free custom domain:** If you want a real domain instead of `.fly.dev`, `.xyz` domains are ~$1/year on Namecheap. Cloudflare offers free DNS + SSL. Or use `freedns.afraid.org` for a free subdomain like `delhiwatch.mooo.com`.

---

## Paid Deployment (Railway — $15–22/month)

```bash
# Local dev with prod-like stack (PostgreSQL + nginx):
docker compose up -d

# Open http://localhost
```

**Railway (free tier → $18–25/month):**

1. Install Railway CLI: `npm i -g @railway/cli`
2. `railway login`
3. `railway init`
4. `railway up` (deploys from Dockerfile)
5. Add PostgreSQL: `railway add` → choose PostgreSQL
6. Railway auto-injects `DATABASE_URL` — no config needed
7. `railway domain` → get your public URL

**Railway cost breakdown (1,000-user scale):**

| Resource | Spec | Monthly cost |
|----------|------|-------------|
| App container | 512MB RAM, 1 vCPU (shared) | ~$12–18 |
| PostgreSQL | Smallest (1GB storage, 0.5 vCPU) | ~$2–3 |
| Network egress | ~5GB/month (photos + traffic) | ~$0.50 |
| **Total** | | **~$15–22/month** |

Railway gives $5 free credit on signup. First month: ~$10–17 out of pocket.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Storage health check (disk %, DB size, accepting_reports flag) |
| GET | `/api/stats` | Total/active/resolved/upvotes counts |
| GET | `/api/constituencies` | All 70 constituencies + MLA details + counts + avg resolution time |
| GET | `/api/constituencies/leaderboard` | Ranked by resolution rate |
| GET | `/api/map-data` | Full GeoJSON boundary data |
| GET | `/api/issues?offset=&limit=&category=&ward=&status=&sort=` | Paginated issue list |
| POST | `/api/issues` | Submit issue (multipart: photos, location, anonymous OK) |
| POST | `/api/issues/{id}/upvote` | Community confirmation upvote |
| POST | `/api/issues/{id}/resolve` | Mark resolved (**resolution photo required**) |
| GET | `/api/categories` | List of 12 issue categories |
| GET | `/api/wards?constituency_id=` | 250 MCD wards (optionally filtered by constituency) |
| POST | `/api/subscribe` | Subscribe to constituency alerts |
| GET | `/api/unsubscribe?token=` | Unsubscribe from alerts |
| GET | `/api/digest` | Weekly activity summary |
| GET | `/uploads/{filename}` | Serve uploaded images |

---

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, SQLite
- **Frontend**: Leaflet.js, Vanilla JavaScript, CSS3
- **Data**: 70-constituency GeoJSON with MLA details

---

## Future Roadmap

### Phase 2: Accountability & Virality
| # | Feature | Impact |
|---|---------|--------|
| 4 | Auto-escalation chain: 7d → re-email MLA, 14d → email MP, 21d → RTI draft | Creates real pressure |
| 5 | One-tap Share on Twitter/X (tags MLA + municipal handle with photo) | Public tagging = faster response |
| 6 | PWA install (offline draft + home screen icon) | Works during connectivity gaps |
| 7 | Browser push notifications for watched constituencies | Instant alerts without email |
| 8 | Auto-categorization from uploaded photos (on-device ML) | Less friction in reporting |

### Phase 3: Data & Trust
| # | Feature | Impact |
|---|---------|--------|
| 10 | Annual report card PDF per constituency (auto-generated) | Media-ready accountability |
| 11 | Issue dispute system (community can flag false "resolved" claims) | Prevents gaming |
| 12 | Heatmap view (density instead of circles) | Better spatial understanding |
| 13 | CSV/JSON export for researchers & journalists | Open data |
| 14 | Admin dashboard with moderation queue | Anti-spam at scale |

---

## Project Structure

```
delhi-issues-map/
├── backend/
│   ├── main.py           # FastAPI server (15 endpoints)
│   ├── models.py         # SQLAlchemy: Issue + WatchSubscription + 250 MCD_WARDS
│   └── schemas.py        # Pydantic: 10 response/request schemas
├── frontend/
│   ├── index.html        # Multi-view SPA (map/list/leaderboard/digest)
│   ├── style.css         # Dark header, stats bar, responsive
│   └── script.js         # Map, pagination, upvotes, before/after, subscriptions
├── data/
│   └── delhi_constituencies.geojson  # 70 constituencies, 4.7MB
├── uploads/              # User-submitted photos
└── requirements.txt
```
