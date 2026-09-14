from fastapi import FastAPI, HTTPException, Depends, Security, Request, Response
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
import subprocess
import json
import os
import sys
import secrets
import re
import shlex
import logging
import time
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)

API_KEY = os.environ.get("API_KEY")
if not API_KEY:
    API_KEY = secrets.token_urlsafe(32)
    print(f"[+] Generated new API_KEY: {API_KEY}")
    print("[*] Save this key - required for all API requests")

ANYRUN_EMAIL = os.environ.get("ANYRUN_EMAIL")
ANYRUN_PASSWORD = os.environ.get("ANYRUN_PASSWORD")
if not ANYRUN_EMAIL or not ANYRUN_PASSWORD:
    print("[-] Missing ANYRUN_EMAIL or ANYRUN_PASSWORD in .env")
    print("[*] Edit .env and add your ANY.RUN credentials")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ANY.RUN Search API",
    version="1.0.0",
    docs_url="/docs" if os.environ.get("DEBUG") == "true" else None,
    redoc_url="/redoc" if os.environ.get("DEBUG") == "true" else None,
    openapi_url="/openapi.json" if os.environ.get("DEBUG") == "true" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "").split(",") if os.environ.get("ALLOWED_ORIGINS") else [],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)

limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

class HashRequest(BaseModel):
    hash: str
    
    @field_validator('hash')
    @classmethod
    def validate_hash(cls, v):
        if not v:
            raise ValueError("Hash is required")
        v = v.strip()
        if not re.fullmatch(r'[a-fA-F0-9]{32,64}', v):
            raise ValueError("Invalid hash format: must be 32-64 hex characters (MD5/SHA1/SHA256)")
        return v.lower()

class HashResponse(BaseModel):
    os: Optional[str] = None
    time: Optional[str] = None
    verdict: Optional[str] = None
    object: Optional[str] = None
    type: Optional[str] = None
    tags: list = []
    md5: Optional[str] = None
    sha1: Optional[str] = None
    sha256: Optional[str] = None
    task_uuid: Optional[str] = None
    report_url: Optional[str] = None

async def verify_api_key(request: Request, api_key: str = Security(api_key_header)):
    if not api_key or api_key != API_KEY:
        logger.warning(f"Invalid API key attempt from {request.client.host}: {api_key[:8] if api_key else 'None'}...")
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return api_key

request_counts = {}

def check_rate_limit(ip: str) -> bool:
    now = time.time()
    if ip not in request_counts:
        request_counts[ip] = []
    request_counts[ip] = [t for t in request_counts[ip] if now - t < 60]
    if len(request_counts[ip]) >= 10:
        return False
    request_counts[ip].append(now)
    return True

@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 1024:
        return Response("Payload too large", status_code=413)
    return await call_next(request)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/search")
@limiter.limit("10/minute")
async def search_hash(request: Request, req: HashRequest, api_key: str = Depends(verify_api_key)):
    client_ip = request.client.host
    
    if not check_rate_limit(client_ip):
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(status_code=429, detail="Rate limit exceeded: max 10 requests per minute")
    
    hash_value = req.hash
    logger.info(f"Search request from {client_ip}: hash={hash_value[:8]}...")
    
    try:
        safe_hash = shlex.quote(hash_value)
        
        result = subprocess.run(
            ["python3", "anyrun_search.py", safe_hash],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(BASE_DIR),
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        
        if result.returncode != 0:
            logger.error(f"Scraper failed for hash {hash_value[:8]}...: {result.stderr[:500]}")
            raise HTTPException(status_code=500, detail="Search failed")
        
        stdout = result.stdout
        marker = "Hash found in search results!"
        idx = stdout.rfind(marker)
        
        if idx >= 0:
            json_start = stdout.find('[', idx)
            if json_start >= 0:
                bracket_count = 0
                json_end = -1
                for i in range(json_start, len(stdout)):
                    if stdout[i] == '[':
                        bracket_count += 1
                    elif stdout[i] == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            json_end = i + 1
                            break
                
                if json_end > json_start:
                    json_str = stdout[json_start:json_end]
                    try:
                        data = json.loads(json_str)
                        logger.info(f"Search successful for hash {hash_value[:8]}... from {request.client.host}")
                        return data
                    except json.JSONDecodeError:
                        pass
        
        logger.error(f"No valid JSON in scraper output for hash {hash_value[:8]}...")
        raise HTTPException(status_code=500, detail="Search failed")
    
    except subprocess.TimeoutExpired:
        logger.error(f"Search timeout for hash {hash_value[:8]}...")
        raise HTTPException(status_code=504, detail="Search timeout")
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in scraper output")
        raise HTTPException(status_code=500, detail="Search failed")
    except Exception:
        logger.error(f"Internal error for hash {hash_value[:8]}...")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")