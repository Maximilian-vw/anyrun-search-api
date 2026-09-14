from fastapi import FastAPI, HTTPException, Depends, Security, Request, Response, status
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
import threading
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from contextlib import asynccontextmanager

BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)

# API_KEY - generate once, persist via env var
API_KEY = os.environ.get("API_KEY")
if not API_KEY:
    API_KEY = secrets.token_urlsafe(32)
    print(f"[+] Generated new API_KEY: {API_KEY}")
    print("[*] Save this key - required for all API requests")
    print(f"[*] Set API_KEY={API_KEY} in .env to persist across restarts")

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

# Rate limiter - thread-safe with lock
rate_limit_lock = threading.Lock()
request_counts = {}

def check_rate_limit(ip: str) -> bool:
    with rate_limit_lock:
        now = time.time()
        if ip not in request_counts:
            request_counts[ip] = []
        request_counts[ip] = [t for t in request_counts[ip] if time.time() - t < 60]
        if len(request_counts[ip]) >= 10:
            return False
        request_counts[ip].append(time.time())
        return True

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("ANY.RUN Search API starting up...")
    yield
    # Shutdown
    logger.info("ANY.RUN Search API shutting down...")

app = FastAPI(
    title="ANY.RUN Search API",
    version="1.0.0",
    description="REST API for searching ANY.RUN public malware submissions",
    docs_url="/api/v1/docs" if os.environ.get("DEBUG") == "true" else None,
    redoc_url="/api/v1/redoc" if os.environ.get("DEBUG") == "true" else None,
    openapi_url="/api/v1/openapi.json" if os.environ.get("DEBUG") == "true" else None,
    lifespan=lifespan,
)

# CORS - only allow specific origins, no wildcard with credentials
allowed_origins = os.environ.get("ALLOWED_ORIGINS", "").split(",") if os.environ.get("ALLOWED_ORIGINS") else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["none"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)

# Rate limiter - thread-safe with lock
rate_limit_lock = threading.Lock()
request_counts = {}

def check_rate_limit(ip: str) -> bool:
    with rate_limit_lock:
        now = time.time()
        if ip not in request_counts:
            request_counts[ip] = []
        request_counts[ip] = [t for t in request_counts[ip] if time.time() - t < 60]
        if len(request_counts[ip]) >= 10:
            return False
        request_counts[ip].append(time.time())
        return True

# Global rate limiter (thread-safe via slowapi)
limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Security middleware
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > 1024:
                return Response(
                    content=json.dumps({"error": {"code": "PAYLOAD_TOO_LARGE", "message": "Payload too large (max 1KB)"}}),
                    status_code=status.HTTP_413_PAYLOAD_TOO_LARGE,
                    media_type="application/json"
                )
        except ValueError:
            return Response(
                content=json.dumps({"error": {"code": "INVALID_CONTENT_LENGTH", "message": "Invalid content-length"}}),
                status_code=status.HTTP_400_BAD_REQUEST,
                media_type="application/json"
            )
    return await call_next(request)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# CORS - only allow specific origins, no wildcard with credentials
allowed_origins = os.environ.get("ALLOWED_ORIGINS", "").split(",") if os.environ.get("ALLOWED_ORIGINS") else []
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["none"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)

# Global rate limiter (thread-safe via slowapi)
limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Rate limiter - thread-safe with lock
rate_limit_lock = threading.Lock()
request_counts = {}

def check_rate_limit(ip: str) -> bool:
    with rate_limit_lock:
        now = time.time()
        if ip not in request_counts:
            request_counts[ip] = []
        request_counts[ip] = [t for t in request_counts[ip] if time.time() - t < 60]
        if len(request_counts[ip]) >= 10:
            return False
        request_counts[ip].append(time.time())
        return True

# API Key validation
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def verify_api_key(request: Request, api_key: str = Security(api_key_header)):
    if not api_key or api_key != API_KEY:
        safe_key = api_key[:8].replace('\n', '').replace('\r', '') if api_key else 'None'
        logger.warning(f"Invalid API key attempt from {request.client.host}: {api_key[:8] if api_key else 'None'}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Invalid API Key"}}
        )
    return api_key

# Request/Response Models
class HashSearchRequest(BaseModel):
    hash: str
    
    @field_validator('hash')
    @classmethod
    def validate_hash(cls, v):
        if not v:
            raise ValueError("Hash is required")
        v = v.strip()
        if not re.fullmatch(r'[a-fA-F0-9]{32,64}', v):
            raise ValueError("Invalid hash format: must be 32-64 hex characters (MD5/SHA1/SHA256)")
        if not re.fullmatch(r'^[a-fA-F0-9]+$', v):
            raise ValueError("Hash contains invalid characters")
        return v.lower()

class SubmissionResponse(BaseModel):
    os: Optional[str] = None
    time: Optional[str] = None
    verdict: Optional[str] = None
    object: Optional[str] = None
    type: Optional[str] = None
    tags: List[str] = []
    md5: Optional[str] = None
    sha1: Optional[str] = None
    sha256: Optional[str] = None
    task_uuid: Optional[str] = None
    report_url: Optional[str] = None

class SearchResponse(BaseModel):
    success: bool
    data: Optional[List[SubmissionResponse]] = None
    error: Optional[dict] = None

class ErrorResponse(BaseModel):
    error: dict

class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"

# API Key validation
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def verify_api_key(request: Request, api_key: str = Security(api_key_header)):
    if not api_key or api_key != API_KEY:
        safe_key = api_key[:8].replace('\n', '').replace('\r', '') if api_key else 'None'
        logger.warning(f"Invalid API key attempt from {request.client.host}: {api_key[:8] if api_key else 'None'}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Invalid API Key"}}
        )
    return api_key

# Rate limiting
rate_limit_lock = threading.Lock()
request_counts = {}

def check_rate_limit(ip: str) -> bool:
    with rate_limit_lock:
        now = time.time()
        if ip not in request_counts:
            request_counts[ip] = []
        request_counts[ip] = [t for t in request_counts[ip] if time.time() - t < 60]
        if len(request_counts[ip]) >= 10:
            return False
        request_counts[ip].append(time.time())
        return True

# Middleware
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > 1024:
                return Response(
                    content=json.dumps({"error": {"code": "PAYLOAD_TOO_LARGE", "message": "Payload too large (max 1KB)"}}),
                    status_code=status.HTTP_413_PAYLOAD_TOO_LARGE,
                    media_type="application/json"
                )
        except ValueError:
            return Response(
                content=json.dumps({"error": {"code": "INVALID_CONTENT_LENGTH", "message": "Invalid content-length"}}),
                status_code=status.HTTP_400_BAD_REQUEST,
                media_type="application/json"
            )
    return await call_next(request)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# Health check
@app.get("/api/v1/health", response_model=HealthResponse, tags=["Health"])
async def health():
    return {"status": "ok", "version": "1.0.0"}

# Search endpoint
@app.post(
    "/api/v1/search",
    response_model=SearchResponse,
    responses={
        200: {"model": SearchResponse, "description": "Successful search"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        413: {"model": ErrorResponse, "description": "Payload too large"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        504: {"model": ErrorResponse, "description": "Gateway timeout"},
    },
    tags=["Search"],
    summary="Search ANY.RUN submissions by hash",
    description="Search for malware submissions by hash (MD5, SHA1, or SHA256)"
)
@limiter.limit("10/minute")
async def search_hash(request: Request, req: HashSearchRequest, api_key: str = Depends(verify_api_key)):
    client_ip = request.client.host
    
    if not check_rate_limit(client_ip):
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {"code": "RATE_LIMIT_EXCEEDED", "message": "Rate limit exceeded: max 10 requests per minute"}}
        )
    
    hash_value = req.hash
    safe_hash_log = hash_value[:8].replace('\n', '').replace('\r', '')
    logger.info(f"Search request from {client_ip}: hash={safe_hash_log}...")
    
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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": {"code": "SEARCH_FAILED", "message": "Search failed"}}
            )
        
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
                        return SearchResponse(success=True, data=data)
                    except json.JSONDecodeError:
                        pass
        
        logger.error(f"No valid JSON in scraper output for hash {hash_value[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "SEARCH_FAILED", "message": "Search failed"}}
        )
    
    except subprocess.TimeoutExpired:
        logger.error(f"Search timeout for hash {hash_value[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"error": {"code": "TIMEOUT", "message": "Search timeout"}}
        )
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in scraper output")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INVALID_JSON", "message": "Search failed"}}
        )
    except Exception:
        logger.error(f"Internal error for hash {hash_value[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}
        )

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return Response(
            content=json.dumps({"success": False, "error": exc.detail}),
            status_code=exc.status_code,
            media_type="application/json"
        )
    return Response(
        content=json.dumps({"success": False, "error": {"code": "HTTP_ERROR", "message": str(exc.detail)}}),
        status_code=exc.status_code,
        media_type="application/json"
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return Response(
        content=json.dumps({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}),
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        media_type="application/json"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info", timeout_keep_alive=30)