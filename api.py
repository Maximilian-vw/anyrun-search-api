from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
import subprocess
import json
import os
import sys
import secrets
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv, set_key

BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / ".env"

# Load existing .env
load_dotenv(ENV_FILE)

# Ensure API_KEY exists - generate on first run
API_KEY = os.environ.get("API_KEY")
if not API_KEY:
    API_KEY = secrets.token_urlsafe(32)
    set_key(str(ENV_FILE), "API_KEY", API_KEY)
    print(f"[+] Generated new API_KEY: {API_KEY}")
    print("[*] Save this key - required for all API requests")
    print(f"[*] Added to {ENV_FILE}")

# Require ANY.RUN credentials
ANYRUN_EMAIL = os.environ.get("ANYRUN_EMAIL")
ANYRUN_PASSWORD = os.environ.get("ANYRUN_PASSWORD")
if not ANYRUN_EMAIL or not ANYRUN_PASSWORD:
    print("[-] Missing ANYRUN_EMAIL or ANYRUN_PASSWORD in .env")
    print("[*] Edit .env and add your ANY.RUN credentials")
    sys.exit(1)

app = FastAPI(title="ANY.RUN Search API", version="1.0.0")

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


class HashRequest(BaseModel):
    hash: str


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


async def verify_api_key(api_key: str = Security(api_key_header)):
    if not api_key or api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return api_key


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/search", response_model=list[HashResponse])
async def search_hash(req: HashRequest, api_key: str = Depends(verify_api_key)):
    hash_value = req.hash.strip()
    if not hash_value:
        raise HTTPException(status_code=400, detail="Hash is required")
    
    try:
        result = subprocess.run(
            ["python3", "anyrun_search.py", hash_value],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(BASE_DIR),
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Scraper failed: {result.stderr[:500]}")
        
        # Parse JSON from scraper output (after "Hash found in search results!")
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
                        return data
                    except json.JSONDecodeError:
                        pass
        
        raise HTTPException(status_code=500, detail="No valid JSON in scraper output")
    
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Search timeout")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)