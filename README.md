# ANY.RUN Search API

Self-hosted REST API for searching ANY.RUN public malware submissions via secure web scraping. Designed for threat intelligence workflows and n8n automation.

## Features

- 🔍 **Hash Search** - SHA256, SHA1, MD5 lookup in ANY.RUN public submissions
- 🔐 **API Key Authentication** - Secure header-based auth (`X-API-Key`)
- 🐳 **Docker Ready** - Single container with headless Chrome + Xvfb
- 🌐 **n8n Compatible** - REST API v1 for workflow automation
- 🛡️ **Secure by Default** - Credentials in `.env`, auto gitignored
- 🖥️ **Headless Server Deploy** - No GUI required

---

## API Endpoints (v1)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/search` | POST | Search by hash (MD5/SHA1/SHA256) |

### Request Format

```bash
POST /api/v1/search
Content-Type: application/json
X-API-Key: YOUR_API_KEY

{
  "hash": "A35AC53B052B669ADD060BE266BBFB98DD72F53212A2B4E817D692EA2AB7B934"
}
```

### Success Response

```json
{
  "success": true,
  "data": [
    {
      "os": "Windows 10 Professional 64 bit",
      "time": "Sep 11, 2026, 10:58",
      "verdict": "No threats detected",
      "object": "https://mebelinterierdacha.icu:443",
      "type": "Open in browser",
      "tags": [],
      "md5": "e1fac7ae43df1b59fb704aaf5fd54f19",
      "sha1": "393e6028931d03ac0a763d48fc464c4eb7cbde50",
      "sha256": "a35ac53b052b669add060be266bbfb98dd72f53212a2b4e817d692ea2ab7b934",
      "task_uuid": "found_via_search",
      "report_url": "https://app.any.run/submissions/"
    }
  ],
  "error": null
}
```

### Error Response

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Description"
  }
}
```

---

## Quick Start (3 Steps)

### 1. Clone & Configure

```bash
git clone https://github.com/Maximilian-vw/anyrun-search-api.git
cd anyrun-search-api
cp .env.example .env
nano .env
```

**Edit `.env` - ADD YOUR ANY.RUN CREDENTIALS, leave API_KEY empty:**
```env
ANYRUN_EMAIL=your@email.com
ANYRUN_PASSWORD=yourpassword
# API_KEY will be auto-generated
```

### 2. Deploy (Auto-generates API_KEY)

```bash
docker compose up -d --build
```

**Get your unique API_KEY from logs:**
```bash
docker compose logs anyrun-api | grep "Generated new API_KEY"
# [+] Generated new API_KEY: Npa5Whbl_5eAOWiQx3kzkycvVEVXKRy0iXWzIg4SS24
```

### 3. Test & Use

```bash
# Health check
curl http://localhost:8000/api/v1/health
# {"status":"ok","version":"1.0.0"}

# Search (replace YOUR_KEY)
curl -X POST http://localhost:8000/api/v1/search \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"hash": "A35AC53B052B669ADD060BE266BBFB98DD72F53212A2B4E817D692EA2AB7B934"}'
```

---

## n8n Integration

**HTTP Request Node:**

| Setting | Value |
|---------|-------|
| **URL** | `http://YOUR_SERVER_IP:8080/api/v1/search` |
| **Method** | POST |
| **Headers** | `X-API-Key: YOUR_GENERATED_KEY` |
| **Body (JSON)** | `{"hash": "{{ $json.hash }}"} |`

---

## How It Works

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   n8n /     │────▶│  ANY.RUN Search  │────▶│   ANY.RUN       │
│   Client    │     │  API (FastAPI)   │     │   Public        │
└─────────────┘     └────────┬─────────┘     │   Submissions   │
                             │               └─────────────────┘
                             ▼
                    ┌──────────────────┐
                    │  Selenium +      │
                    │  Chrome (Headless)│
                    └──────────────────┘
```

1. **API starts** → reads `.env` → generates unique `API_KEY` if missing
2. **Client calls** `/api/v1/search` with hash + `X-API-Key` header
3. **Server** launches headless Chrome → logs into ANY.RUN → searches hash
4. **Returns** JSON with verdict, object, tags, hashes

---

## Security Model

| Layer | Protection |
|-------|------------|
| **API Key** | Auto-generated 256-bit token per install (`secrets.token_urlsafe(32)`) |
| **ANY.RUN Creds** | Your personal credentials in `.env` only |
| **No Defaults** | No hardcoded secrets anywhere |
| **Container Isolation** | Docker with memory/CPU limits |
| **Git Safe** | `.env` in `.gitignore` |
| **Hash Validation** | Only 32-64 hex chars accepted (MD5/SHA1/SHA256) |
| **Rate Limiting** | 10 req/min per IP |
| **Payload Limit** | 1KB max request size |
| **Security Headers** | X-Content-Type-Options, X-Frame-Options, etc. |

---

## Requirements

- Linux server (Ubuntu/Debian/RHEL)
- Docker + Docker Compose
- 2GB+ RAM
- Network access to `app.any.run:443`

---

## Maintenance

```bash
# View logs
docker compose logs -f anyrun-api

# Restart
docker compose restart

# Update
git pull && docker compose build --no-cache && docker compose up -d

# Stop
docker compose down

# Check resources
docker stats anyrun-search-api

# Get API_KEY again
grep API_KEY .env
```

---

## For Public GitHub Repo

1. `.env` is in `.gitignore` - never committed
2. Users clone → `cp .env.example .env` → add their ANY.RUN creds
3. Each gets unique `API_KEY` on first `docker compose up`
4. No shared secrets possible

---

## License

MIT - Open source for the community