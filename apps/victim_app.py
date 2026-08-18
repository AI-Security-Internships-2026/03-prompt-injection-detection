"""
victim_app.py — "Finance Assistant" (Tenant A / User A)
Port 8001. Simple synthetic session auth. Secret lives only in this
process's memory, keyed by session token. Never returned by any endpoint.
"""
import sys, os, secrets
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments", "sglang"))

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from shared_client import send_to_sglang, flush_cache
import sys as _sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments", "sglang"))
from config import PIN_LABEL, PIN_SEPARATOR, PIN_TRAILING_MARKER

app = FastAPI(title="Finance Assistant (User A)")

def format_secret_for_cache(secret: str) -> str:
    """If the secret looks like an all-digit PIN, format it using the
    validated comma-separated + trailing-marker scheme (prevents BPE
    token merging that breaks position-by-position cache detection).
    Otherwise, send as-is."""
    if secret.isdigit():
        return PIN_LABEL + PIN_SEPARATOR.join(list(secret)) + PIN_TRAILING_MARKER
    return secret

SHARED_PUBLIC_PREFIX = (
    "You are a customer support assistant for a cloud infrastructure company. "
    "Below is the internal knowledge base context shared across all support sessions. "
    "Use this context to answer user questions about billing, deployment, and account "
    "management. Always be concise and professional. The following section contains "
    "account-specific context for the current session: "
) * 3

# Synthetic researcher-controlled credentials
_VALID_USERS = {"user_a": "researcher-controlled-password"}
_sessions = {}   # token -> username
_secrets = {}    # token -> submitted secret (process-local only)

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str

class SubmitRequest(BaseModel):
    secret: str

@app.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    if _VALID_USERS.get(req.username) != req.password:
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = secrets.token_hex(16)
    _sessions[token] = req.username
    return LoginResponse(token=token)

@app.post("/logout")
def logout(authorization: Optional[str] = Header(None)):
    token = _sessions.pop(authorization, None) and authorization
    _secrets.pop(authorization, None)
    return {"logged_out": token is not None}

@app.post("/submit")
def submit_secret(req: SubmitRequest, authorization: Optional[str] = Header(None)):
    if authorization not in _sessions:
        raise HTTPException(status_code=401, detail="not logged in")
    _secrets[authorization] = req.secret  # this session's memory only

    formatted = format_secret_for_cache(req.secret)
    prompt = SHARED_PUBLIC_PREFIX + formatted
    result = send_to_sglang(prompt)
    return {"accepted": True, "prompt_tokens": result["prompt_tokens"]}

@app.post("/flush")
def flush():
    return {"flush_result": flush_cache()}

@app.get("/status")
def status(authorization: Optional[str] = Header(None)):
    logged_in = authorization in _sessions
    has_secret = authorization in _secrets
    return {"logged_in": logged_in, "secret_submitted": has_secret}

from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
def victim_ui():
    return """
    <html><body style="font-family:sans-serif;max-width:400px;margin:40px auto;">
    <h2>Finance Assistant (User A)</h2>
    <div id="login">
      <input id="u" placeholder="username" value="user_a"><br><br>
      <input id="p" placeholder="password" type="password" value="researcher-controlled-password"><br><br>
      <button onclick="login()">Login</button>
    </div>
    <div id="app" style="display:none;">
      <p>Logged in. Enter your synthetic PIN:</p>
      <input id="pin" placeholder="e.g. 482913"><br><br>
      <button onclick="submitPin()">Submit PIN</button>
      <button onclick="logout()">Logout</button>
      <p id="msg"></p>
    </div>
    <script>
    let token = null;
    async function login() {
      const r = await fetch('/login', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({username: document.getElementById('u').value, password: document.getElementById('p').value})});
      if (r.ok) {
        const d = await r.json();
        token = d.token;
        document.getElementById('login').style.display = 'none';
        document.getElementById('app').style.display = 'block';
      } else {
        alert('Login failed');
      }
    }
    async function submitPin() {
      const r = await fetch('/submit', {method:'POST', headers:{'Content-Type':'application/json','Authorization':token},
        body: JSON.stringify({secret: document.getElementById('pin').value})});
      const d = await r.json();
      document.getElementById('msg').innerText = 'Submitted. prompt_tokens=' + d.prompt_tokens;
    }
    async function logout() {
      await fetch('/logout', {method:'POST', headers:{'Authorization':token}});
      token = null;
      document.getElementById('app').style.display = 'none';
      document.getElementById('login').style.display = 'block';
      document.getElementById('msg').innerText = 'Logged out.';
    }
    </script>
    </body></html>
    """
