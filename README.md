# ANY.RUN Search API

Self-hosted API for searching ANY.RUN public malware submissions via secure web scraping. Designed for threat intelligence workflows and n8n automation.

## Features

- 🔍 **Hash Search** - SHA256, SHA1, MD5 lookup in ANY.RUN public submissions
- 🔐 **Auto-Generated API Keys** - Unique per installation, no shared secrets
- 🐳 **Docker Ready** - Single container with headless Chrome + Xvfb
- 🌐 **n8n Compatible** - REST API for workflow automation
- 🛡️ **Secure by Default** - Credentials in `.env`, auto gitignored
- 🖥️ **Headless Server Deploy** - No GUI required

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
sudo -S docker exec anyrun-search-api env | grep API_KEY
# API_KEY: K7x9mN2pQ4vL8wE5rT6yU1iO3pA6sD9fG2hJ5kL8mN1
```

### 3. Test & Use

```bash
# Health check
curl http://localhost:8000/health
# {"status":"ok"}

# Search (replace YOUR_KEY)
curl -X POST http://localhost:8000/search \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"hash": "A35AC53B052B669ADD060BE266BBFB98DD72F53212A2B4E817D692EA2AB7B934"}'
```

---

## n8n Integration

**HTTP Request Node:**

| Setting | Value |
|---------|-------|
| **URL** | `http://YOUR_SERVER_IP:8000/search` |
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
2. **Client calls** `/search` with hash + `X-API-Key` header
3. **Server** launches headless Chrome → logs into ANY.RUN → searches hash
4. **Returns** JSON with verdict, object, tags, hashes

---

## Security Model

| Layer | Protection |
|-------|------------|
| **API Key** | Auto-generated 256-bit token per install (`secrets.token_urlsafe(32)`) |
| **ANY.RUN Creds** | Your personal credentials in `.env` only |
| **No Defaults** | No hardcoded secrets anywhere |
| **Container Isolation** | Docker with memory limits |
| **Git Safe** | `.env` in `.gitignore` |

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
