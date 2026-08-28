# Voice OTP API — documentation for frontend (Nuxt, Streamlit, React, etc.)

Base URL (local): `http://127.0.0.1:5000`

CORS is enabled. Send JSON with `Content-Type: application/json`.

Do **not** display OTP codes in the UI except on the user verification screen after the user received them via voice / SMS / email.

---

## 1. User authentication flow

Typical screens:

1. Login (`userId`)
2. Choose channel: `voice` | `sms` | `email`
3. Collect destination (SMS number or email) — voice calls Linphone `1000` automatically
4. Enter the 6-digit code
5. Success

Rate limit on request endpoints: **3 requests / 5 minutes / IP**.  
HTTP `429`:

```json
{ "status": "error", "detail": "Trop de tentatives, réessayez plus tard" }
```

Verify: max **3 wrong codes**. Then HTTP `429`:

```json
{ "ok": false, "reason": "too_many_attempts" }
```

OTP TTL: **180 seconds**.

---

### `GET /auth/countries`

Public list of dial codes for the SMS form.

**Response 200**

```json
{
  "countries": [
    { "iso": "MR", "name": "Mauritanie", "dial": "+222", "minLen": 8, "maxLen": 8 }
  ]
}
```

---

### `POST /auth/request-voice-otp`

Starts a real voice call (Linphone extension 1000) and stores the OTP.

**Body**

```json
{ "userId": "user1" }
```

**Response 200** `{ "status": "sent", "channel": "voice" }`  
**Response 400** `{ "status": "error", "detail": "..." }`  
**Response 502** call failed.

---

### `POST /auth/request-sms-otp`

**Body**

```json
{ "userId": "user1", "phoneNumber": "+22243132854" }
```

`phoneNumber` in international form. `+` / `00` are stripped server-side.

**Response 200** `{ "status": "sent", "demo": false }`  
**Response 400 / 502** `{ "status": "error", "detail": "..." }`

---

### `POST /auth/request-email-otp`

**Body**

```json
{ "userId": "user1", "email": "person@example.com" }
```

**Response 200** `{ "status": "sent" }`  
**Response 400 / 502** `{ "status": "error", "detail": "..." }`

---

### `POST /auth/verify-otp`

Shared for voice, SMS and email.

**Body**

```json
{ "userId": "user1", "otp": "123456" }
```

**Response 200** `{ "ok": true }`  
**Response 400** `{ "ok": false, "reason": "missing" | "invalid" | "expired" }`  
**Response 429** `{ "ok": false, "reason": "too_many_attempts" }`

After `too_many_attempts`, the user must request a **new** OTP.

---

## 2. Admin dashboard API (section 9)

All `/admin/*` routes require header:

```
X-Admin-Key: changeme-admin-key
```

Change the key in `backend/admin_config.py` (`ADMIN_API_KEY`). Never put this key in a public Nuxt/Streamlit client without a backend proxy.

**Response 401** (missing or wrong key)

```json
{ "error": "unauthorized" }
```

Destinations in admin payloads are **always masked** (`joh***@gmail.com`, `+222 43***54`). Never store or show a full phone/email from these endpoints.

Event `status` values: `sent`, `failed`, `verified`, `invalid`, `expired`, `too_many_attempts`.  
Event `channel` values: `voice`, `email`, `sms`.

---

### `GET /admin/stats`

**Response 200**

```json
{
  "total_requests": 128,
  "active_codes": 2,
  "success_rate": 41.7,
  "by_channel": { "voice": 40, "sms": 50, "email": 38 },
  "by_status": { "sent": 90, "verified": 30, "invalid": 8 }
}
```

- `total_requests`: rows in SQLite history  
- `active_codes`: live OTP keys in Redis (`otp:*`)  
- `success_rate`: % of events with `status=verified` in the last 24 hours  

---

### `GET /admin/stats/dashboard`  ⭐ one-shot for Accueil

Returns **all** chart payloads in one call. Prefer this for the modern dashboard homepage.

**Response 200** (shape)

```json
{
  "kpis": {
    "generated_at": "2026-08-19T18:00:00+00:00",
    "total_requests": 128,
    "today": 12,
    "last_24h": 18,
    "last_7d": 90,
    "sent_24h": 10,
    "verified_24h": 6,
    "failed_24h": 1,
    "invalid_24h": 2,
    "success_rate_24h": 33.3,
    "success_rate_7d": 28.8,
    "verify_rate_24h": 60.0,
    "unique_users_7d": 9,
    "avg_per_day_7d": 12.9,
    "active_codes": 2
  },
  "by_channel": { "voice": 40, "sms": 50, "email": 38 },
  "by_status": { "sent": 90, "verified": 30 },
  "timeseries": { "granularity": "day", "days": 7, "points": [] },
  "sparkline_24h": { "points": [{ "hour": "18:00", "total": 3 }], "peak": 3 },
  "channels": { "days": 7, "items": [] },
  "statuses": { "days": 7, "total": 90, "items": [] },
  "funnel": { "days": 7, "conversion": 40.0, "steps": [] },
  "heatmap": { "days": 7, "weekdays": ["mon"], "hours": [0], "grid": [[0]], "max": 4 },
  "top_users": { "days": 7, "items": [] },
  "recent": [],
  "redis": { "connected": true, "total_keys": 2, "oldest_key_age_seconds": 120 }
}
```

Suggested widgets:

| Widget | JSON path | Chart |
|---|---|---|
| KPI cards | `kpis.*` | numbers + sparkline |
| Activity 24h | `sparkline_24h.points` | area / sparkline |
| 7-day trend | `timeseries.points` | line (total, sent, verified) |
| Channels | `channels.items` | donut |
| Status mix | `statuses.items` | bar |
| Conversion | `funnel.steps` | funnel |
| Busy hours | `heatmap.grid` | 7×24 heatmap |
| Top users | `top_users.items` | ranked list |
| Live Redis | `redis` | badge |
| Last events | `recent` | compact table |

---

### `GET /admin/stats/overview`

Rich KPI cards. Same fields as `dashboard.kpis`.

---

### `GET /admin/stats/timeseries`

Line chart. Query: `days` (1–90, default 7), `granularity` = `day` \| `hour`.

**Response 200**

```json
{
  "granularity": "day",
  "days": 7,
  "points": [
    { "label": "2026-08-13", "total": 12, "sent": 8, "verified": 3, "failed": 1, "invalid": 0 }
  ]
}
```

Use `label` on X, `total` / `verified` / `failed` as series.

---

### `GET /admin/stats/channels`

Donut / pie. Query: `days` (default 7).

```json
{
  "days": 7,
  "items": [
    { "channel": "voice", "total": 20, "sent": 14, "verified": 8, "failed": 2, "success_rate": 40.0 }
  ]
}
```

---

### `GET /admin/stats/status`

Horizontal bars. Query: `days`.

```json
{
  "days": 7,
  "total": 90,
  "items": [
    { "status": "sent", "count": 40, "percent": 44.4 },
    { "status": "verified", "count": 20, "percent": 22.2 }
  ]
}
```

---

### `GET /admin/stats/funnel`

Conversion funnel. Query: `days`.

```json
{
  "days": 7,
  "conversion": 40.0,
  "steps": [
    { "key": "sent", "label": "Codes envoyés", "count": 40 },
    { "key": "verified", "label": "Vérifiés", "count": 16 }
  ]
}
```

`conversion` = verified / sent (%).

---

### `GET /admin/stats/heatmap`

Hour × weekday heatmap. Query: `days` (1–30, default 7).

```json
{
  "days": 7,
  "weekdays": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
  "hours": [0, 1, 2],
  "grid": [[0, 1, 0], [2, 0, 0]],
  "max": 2
}
```

`grid[weekdayIndex][hour]` = event count. Color scale 0 → `max`.

---

### `GET /admin/stats/top-users`

Ranked users. Query: `days`, `limit` (1–20, default 8).

```json
{
  "days": 7,
  "items": [
    { "user_id": "user1", "total": 12, "verified": 5, "success_rate": 41.7 }
  ]
}
```

---

### `GET /admin/stats/sparkline`

Last 24 hours, one point per hour — for a KPI sparkline.

```json
{
  "peak": 4,
  "points": [{ "hour": "18:00", "total": 2 }]
}
```

---

### `GET /admin/recent-requests`

Last 20 events, newest first.

**Response 200**

```json
{
  "results": [
    {
      "id": 12,
      "timestamp": "2026-08-19T12:00:00+00:00",
      "user_id": "user1",
      "channel": "sms",
      "status": "sent",
      "destination": "+222 43***54",
      "source_ip": "127.0.0.1"
    }
  ]
}
```

Accueil table columns to display: timestamp, user_id, channel, status, destination, source_ip.

---

### `GET /admin/logs`

Query params (all optional):

| Param       | Description                          | Default |
|-------------|--------------------------------------|---------|
| `channel`   | `voice` \| `email` \| `sms`          | —       |
| `status`    | see status list above                | —       |
| `date_from` | ISO datetime, inclusive              | —       |
| `date_to`   | ISO datetime, inclusive              | —       |
| `page`      | page number                          | `1`     |
| `page_size` | items per page (max 100)             | `20`    |

**Response 200**

```json
{
  "total": 128,
  "page": 1,
  "page_size": 20,
  "results": [
    {
      "id": 12,
      "timestamp": "2026-08-19T12:00:00+00:00",
      "user_id": "user1",
      "channel": "email",
      "status": "verified",
      "destination": "joh***@gmail.com",
      "source_ip": "127.0.0.1"
    }
  ]
}
```

Suggested UI: table + filters (channel, status, date range) + pagination.

---

### `GET /admin/tools/redis-status`

**Response 200**

```json
{
  "connected": true,
  "total_keys": 2,
  "oldest_key_age_seconds": 141
}
```

`oldest_key_age_seconds` is the **smallest remaining TTL** among `otp:*` keys, or `null` if none.  
If Redis is down, `connected` is `false` (in-memory OTP fallback may still hold keys).

---

### `POST /admin/tools/flush-redis`

Deletes all `otp:*` keys. Active user codes become unusable.

**Response 200**

```json
{ "status": "flushed", "keys_removed": 2 }
```

---

### `POST /admin/tools/test-otp`

Send a real test OTP without the user frontend. Stored as `userId=admin-test`.

**Body**

```json
{ "channel": "email", "destination": "dev@example.com" }
```

- `channel`: `voice` | `email` | `sms`  
- `destination`: email, phone (`+222...`), or SIP extension for voice (default `1000`)

**Response 200** `{ "status": "sent", "channel": "email", "userId": "admin-test" }`  
**Response 400 / 502** `{ "status": "error", "detail": "..." }`

To verify the test code, call `POST /auth/verify-otp` with `"userId": "admin-test"`.

---

### `POST /admin/tools/cleanup`

Deletes SQLite history older than **30 days**. Does not touch Redis.

**Response 200**

```json
{ "status": "cleaned", "rows_removed": 4 }
```

---

## 3. Frontend mapping (section 9)

| Cahier des charges | Endpoint | UI idea |
|---|---|---|
| Accueil | `GET /admin/stats/dashboard` | KPI + graphs (one call) |
| Accueil (léger) | `GET /admin/stats` + `GET /admin/recent-requests` | KPI cards + last 20 rows |
| Journaux | `GET /admin/logs` | Filterable table |
| Outils | redis-status, flush-redis, test-otp, cleanup | Status badge + action buttons |

Confirm flush / cleanup with a modal (destructive).

---

## 4. Nuxt 3 example

```ts
const API = "http://127.0.0.1:5000";
const ADMIN_KEY = process.env.NUXT_ADMIN_API_KEY; // server-only

export function adminFetch(path: string, options: RequestInit = {}) {
  return $fetch(API + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Key": ADMIN_KEY as string,
      ...(options.headers || {}),
    },
  });
}

// Accueil moderne (un seul appel)
await adminFetch("/admin/stats/dashboard");

// Graphiques séparés
await adminFetch("/admin/stats/overview");
await adminFetch("/admin/stats/timeseries?days=7&granularity=day");
await adminFetch("/admin/stats/channels?days=7");
await adminFetch("/admin/stats/status?days=7");
await adminFetch("/admin/stats/funnel?days=7");
await adminFetch("/admin/stats/heatmap?days=7");
await adminFetch("/admin/stats/top-users?days=7&limit=8");
await adminFetch("/admin/stats/sparkline");


// Journaux
await adminFetch("/admin/logs?channel=sms&status=sent&page=1&page_size=20");

// Outils
await adminFetch("/admin/tools/redis-status");
await adminFetch("/admin/tools/flush-redis", { method: "POST" });
await adminFetch("/admin/tools/test-otp", {
  method: "POST",
  body: { channel: "sms", destination: "+22243132854" },
});
await adminFetch("/admin/tools/cleanup", { method: "POST" });
```

Keep `X-Admin-Key` on the **Nuxt server** (Nitro / server routes), not in the browser bundle.

---

## 5. Streamlit example

```python
import os
import requests
import streamlit as st

API = "http://127.0.0.1:5000"
HEADERS = {"X-Admin-Key": os.environ["ADMIN_API_KEY"]}

stats = requests.get(f"{API}/admin/stats", headers=HEADERS).json()
st.metric("Demandes", stats["total_requests"])
st.metric("Codes actifs", stats["active_codes"])
st.metric("Succès 24h", f"{stats['success_rate']} %")

logs = requests.get(
    f"{API}/admin/logs",
    headers=HEADERS,
    params={"page": 1, "page_size": 20},
).json()
st.dataframe(logs["results"])
```

---

## 6. PowerShell tests (admin)

Set once:

```powershell
$base = "http://127.0.0.1:5000"
$headers = @{ "X-Admin-Key" = "changeme-admin-key" }
```

Unauthorized (expect 401):

```powershell
Invoke-RestMethod -Uri "$base/admin/stats" -Method GET
```

a) Stats

```powershell
Invoke-RestMethod -Uri "$base/admin/stats" -Headers $headers -Method GET
```

Dashboard complet (graphiques) :

```powershell
Invoke-RestMethod -Uri "$base/admin/stats/dashboard" -Headers $headers -Method GET
```

Timeseries 7 jours :

```powershell
Invoke-RestMethod -Uri "$base/admin/stats/timeseries?days=7&granularity=day" -Headers $headers -Method GET
```

Funnel / canaux / heatmap :

```powershell
Invoke-RestMethod -Uri "$base/admin/stats/funnel?days=7" -Headers $headers -Method GET
Invoke-RestMethod -Uri "$base/admin/stats/channels?days=7" -Headers $headers -Method GET
Invoke-RestMethod -Uri "$base/admin/stats/heatmap?days=7" -Headers $headers -Method GET
```

b) Recent requests

```powershell
Invoke-RestMethod -Uri "$base/admin/recent-requests" -Headers $headers -Method GET
```

c) Logs (filtered)

```powershell
Invoke-RestMethod -Uri "$base/admin/logs?channel=sms&status=sent&page=1&page_size=20" -Headers $headers -Method GET
```

d) Redis status

```powershell
Invoke-RestMethod -Uri "$base/admin/tools/redis-status" -Headers $headers -Method GET
```

e) Flush Redis

```powershell
Invoke-RestMethod -Uri "$base/admin/tools/flush-redis" -Headers $headers -Method POST
```

f) Test OTP (email)

```powershell
Invoke-RestMethod -Uri "$base/admin/tools/test-otp" -Headers $headers -Method POST -ContentType "application/json" -Body '{"channel":"email","destination":"dev@example.com"}'
```

f) Test OTP (SMS)

```powershell
Invoke-RestMethod -Uri "$base/admin/tools/test-otp" -Headers $headers -Method POST -ContentType "application/json" -Body '{"channel":"sms","destination":"+22243132854"}'
```

f) Test OTP (voice)

```powershell
Invoke-RestMethod -Uri "$base/admin/tools/test-otp" -Headers $headers -Method POST -ContentType "application/json" -Body '{"channel":"voice","destination":"1000"}'
```

g) Cleanup (> 30 days)

```powershell
Invoke-RestMethod -Uri "$base/admin/tools/cleanup" -Headers $headers -Method POST
```

---

## 7. AI Control Center (independent of OTP core)

Header: `X-Admin-Key` (same as admin).  
The AI layer **never** generates OTP codes and **never** receives secrets, full phones, or raw OTP.

ML: IsolationForest (fallback: z-score).  
LLM: Ollama local if available (`http://127.0.0.1:11434`), otherwise a deterministic template that only uses aggregated metrics.

A background worker refreshes a snapshot every 5 minutes. The dashboard should call `GET /admin/ai/control-center` on load (no "Analyze" button required).

`insufficient` / `insufficient_data` is **true only when there are 0 OTP events in 24h**. KPIs, channels and charts are still returned as soon as there is history.

### `GET /admin/ai/control-center`

One-shot payload for the **AI Control Center** page (Nuxt `/ai`).

Query: `refresh=1` to recompute now.

**Response 200** (fields the Nuxt page reads)

```json
{
  "generated_at": "2026-08-20T10:00:00+00:00",
  "provider": "ollama",
  "insufficient": false,
  "insufficient_data": false,
  "period_label": "13/08/2026 → 20/08/2026",
  "health": { "score": 86.5, "label": "Good", "status": "healthy", "risk_level": "MEDIUM" },
  "kpis": {
    "success_rate": 33.3,
    "failure_rate": 12.5,
    "total_sends": 22,
    "anomaly_score": 0.72,
    "anomaly_risk": "HIGH",
    "sparklines": { "health": [90], "success": [10], "failure": [12], "sends": [3], "anomaly": [0.1] }
  },
  "channels": [
    { "channel": "sms", "sent": 4, "success": 0, "failed": 2, "success_rate": 0, "trend": [0, 1, 2], "requests": 4 }
  ],
  "timeseries": [
    { "label": "2026-08-19", "total": 12, "sent": 12, "verified": 1, "failed": 2 }
  ],
  "anomaly": {
    "detected": true,
    "anomaly_score": 0.72,
    "risk_level": "HIGH",
    "model": "IsolationForest",
    "reasons": ["too_many_attempts rate is 13.6% in 24h."]
  },
  "anomalies": [{ "reason": "too_many_attempts rate is 13.6% in 24h.", "score": 0.72 }],
  "predictions": [
    { "channel": "sms", "failure_rate": 18, "predicted": 18, "level": "HIGH", "risk": "HIGH" }
  ],
  "insights": {
    "anomalies_count": 1,
    "risk_level": "HIGH",
    "confidence": 72,
    "items": ["too_many_attempts rate is 13.6% in 24h."]
  },
  "recommendations": [{ "text": "Investigate the flagged channel before increasing OTP traffic.", "requires_admin_approval": true }],
  "daily_summary": {
    "date": "Dernières 24h",
    "total_sends": 22,
    "verified": 1,
    "success_rate": 4.5,
    "main_issue": "too_many_attempts rate is 13.6% in 24h.",
    "risk_level": "HIGH",
    "best_channel": "voice"
  },
  "notifications": [{ "level": "warning", "title": "AI detected an anomaly", "detail": "...", "text": "..." }],
  "system": { "redis": true, "database": "OK", "uptime": null }
}
```

Nuxt page sections: System Health, AI Insights, Predictions, Recommendations, Channel Intelligence, Daily Summary, Copilot, Notifications.

---

### Other AI endpoints (same snapshot)

| Method | Path | Use |
|---|---|---|
| GET | `/admin/ai/health` | Health score + label + risk |
| GET | `/admin/ai/insights` | Auto insights |
| GET | `/admin/ai/anomalies` | IsolationForest + reasons |
| GET | `/admin/ai/predictions` | Next-hour failure / volume |
| GET | `/admin/ai/recommendations` | `{ "results": [ { "text", "requires_admin_approval" } ] }` |
| GET | `/admin/ai/daily-summary` | Daily summary |
| GET | `/admin/ai/channels` | SMS / Voice / Email intelligence |
| GET | `/admin/ai/notifications` | Alert cards |
| GET | `/admin/ai/guide` | Voice tour scripts (French) |
| GET | `/admin/ai/guide?section=ai` | One spoken section |
| GET | `/admin/ai/guide/audio?section=home` | WAV voiceover |
| POST | `/admin/ai/refresh` | Force recompute |
| POST | `/admin/ai/ask` | Copilot |

### `POST /admin/ai/ask`

Rate limit: 10 / minute / IP.

```json
{ "question": "Pourquoi le taux de succès SMS a diminué ?" }
```

**Response 200**

```json
{
  "answer": "SMS 24h: 40 requêtes, succès 89%...",
  "provider": "ollama",
  "context_used": { "period": "last_24_hours", "sms": { "requests": 40, "success_rate": 89 } }
}
```

The LLM only receives aggregated JSON (no OTP, no phones, no keys).  
If it cannot answer: `Les données disponibles sont insuffisantes pour répondre avec certitude.`

---

### Nuxt — AI Control Center

```ts
const center = await adminFetch("/admin/ai/control-center");
// center.health.score, center.kpis, center.channels, center.predictions,
// center.insights, center.daily_summary, center.notifications

const chat = await adminFetch("/admin/ai/ask", {
  method: "POST",
  body: { question: "Compare SMS et Voice." },
});
```

---

## 8. Guide vocal (micro) — pour le frontend Nuxt

Header: `X-Admin-Key` (même clé admin).  
Langue: **français parlé**, tutoiement de visiteur / vouvoiement console.  
Aucun OTP, mot de passe ou numéro complet n’est inclus.

Au clic sur le micro, appeler l’API puis lire le `script` (Web Speech) **ou** jouer le WAV serveur.

### Sections (`section=`)

| id | Page / bloc | Route Nuxt |
|---|---|---|
| `intro` | Bienvenue console | — |
| `sidebar` | Menu gauche (4 pages + bloc Système) | — |
| `home` | Tableau de bord | `/` |
| `logs` | Journaux | `/logs` |
| `ai` | AI Control Center (vue d’ensemble + chiffres live) | `/ai` |
| `tools` | Outils Redis / test / cleanup | `/tools` |
| `system` | Voyants Redis, base, uptime | — |
| `kpis` | 5 cartes du haut | `/ai` |
| `channels` | Performance par canal | `/ai` |
| `timeseries` | Graphique envois & succès | `/ai` |
| `alerts` | Alertes intelligentes | `/ai` |
| `insights` | Analyse IA du jour | `/ai` |
| `predictions` | Prédictions | `/ai` |
| `recommendations` | Recommandations | `/ai` |
| `summary` | Résumé quotidien | `/ai` |
| `copilot` | Copilote | `/ai` |
| `ai-page` | Toute la page `/ai` d’une traite | `/ai` |
| `full` | Visite du menu complet | toutes |

Mapping page → section: `mic.page_section` dans la réponse globale.

### `GET /admin/ai/guide`

Sans query: playlist complète + scripts.

`?section=home` : un seul bloc.

**200 (liste)**

```json
{
  "language": "fr-FR",
  "voice": "Windows SAPI, voix française si installée (Hortense / fr-FR)",
  "generated_at": "2026-08-20T12:00:00+00:00",
  "mic": {
    "label": "Écouter le guide",
    "default_section": "full",
    "page_section": { "/": "home", "/logs": "logs", "/ai": "ai-page", "/tools": "tools" }
  },
  "playlist": [
    {
      "id": "home",
      "title": "Tableau de bord",
      "route": "/",
      "hint": "Aperçu général & AI",
      "language": "fr-FR",
      "script": "Vous êtes sur le Tableau de bord...",
      "audio": "/admin/ai/guide/audio?section=home",
      "duration_hint_seconds": 28
    }
  ]
}
```

**200 (`?section=ai`)** : l’objet playlist item seul (`id`, `title`, `script`, `audio`, …).

**404** `{ "error": "unknown_section", "allowed": ["intro", "sidebar", ...] }`

### `GET /admin/ai/guide/audio?section=home`

WAV (`audio/wav`) généré par Windows SAPI (voix `fr-FR` si installée).  
Limite: **8 / minute**. Premier appel ~ quelques secondes (puis cache).

**503** si TTS échoue: le body JSON contient `script` → fallback navigateur.

### Nuxt — bouton micro

```ts
const path = useRoute().path
const map: Record<string, string> = {
  "/": "home",
  "/logs": "logs",
  "/ai": "ai-page",
  "/tools": "tools",
}
const section = map[path] || "intro"

// 1) Texte immédiat (recommandé)
const item = await $fetch("/api/admin/ai/guide", { query: { section } })
const u = new SpeechSynthesisUtterance(item.script)
u.lang = "fr-FR"
speechSynthesis.speak(u)

// 2) Voix serveur (optionnel)
const blob = await $fetch("/api/admin/ai/guide/audio", {
  query: { section },
  responseType: "blob",
})
const url = URL.createObjectURL(blob)
new Audio(url).play()
```

Stop: `speechSynthesis.cancel()` et `audio.pause()`.

### PowerShell — guide

```powershell
Invoke-RestMethod -Uri "$base/admin/ai/guide" -Headers $headers
Invoke-RestMethod -Uri "$base/admin/ai/guide?section=sidebar" -Headers $headers
Invoke-WebRequest -Uri "$base/admin/ai/guide/audio?section=intro" -Headers $headers -OutFile guide-intro.wav
```

---

### PowerShell — AI

```powershell
Invoke-RestMethod -Uri "$base/admin/ai/control-center" -Headers $headers -Method GET
Invoke-RestMethod -Uri "$base/admin/ai/health" -Headers $headers -Method GET
Invoke-RestMethod -Uri "$base/admin/ai/anomalies" -Headers $headers -Method GET
Invoke-RestMethod -Uri "$base/admin/ai/predictions" -Headers $headers -Method GET
Invoke-RestMethod -Uri "$base/admin/ai/recommendations" -Headers $headers -Method GET
Invoke-RestMethod -Uri "$base/admin/ai/daily-summary" -Headers $headers -Method GET
Invoke-RestMethod -Uri "$base/admin/ai/channels" -Headers $headers -Method GET
Invoke-RestMethod -Uri "$base/admin/ai/notifications" -Headers $headers -Method GET
Invoke-RestMethod -Uri "$base/admin/ai/ask" -Headers $headers -Method POST -ContentType "application/json" -Body '{"question":"Donne-moi un résumé du système."}'
```



