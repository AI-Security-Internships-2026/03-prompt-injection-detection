"""
victim_app.py — "Finance Assistant" (Tenant A / User A)
Port 8001. Secret lives only in this process's memory, keyed by session.
"""
import sys, os, secrets
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments", "sglang"))

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from shared_client import send_to_sglang, flush_cache
from config import PIN_LABEL, PIN_SEPARATOR, PIN_TRAILING_MARKER

app = FastAPI(title="Finance Assistant (User A)")

SHARED_PUBLIC_PREFIX = (
    "You are a customer support assistant for a cloud infrastructure company. "
    "Below is the internal knowledge base context shared across all support sessions. "
    "Use this context to answer user questions about billing, deployment, and account "
    "management. Always be concise and professional. The following section contains "
    "account-specific context for the current session: "
) * 3

_VALID_USERS = {"user_a": "researcher-controlled-password"}
_sessions = {}
_secrets = {}

def format_secret_for_cache(secret: str) -> str:
    if secret.isdigit():
        return PIN_LABEL + PIN_SEPARATOR.join(list(secret)) + PIN_TRAILING_MARKER
    return secret

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
    _secrets[authorization] = req.secret

    formatted = format_secret_for_cache(req.secret)
    prompt = SHARED_PUBLIC_PREFIX + formatted
    result = send_to_sglang(prompt, cache_salt="tenant_victim")
    return {"accepted": True, "prompt_tokens": result["prompt_tokens"]}

@app.post("/flush")
def flush():
    return {"flush_result": flush_cache()}

@app.get("/status")
def status(authorization: Optional[str] = Header(None)):
    return {"logged_in": authorization in _sessions, "secret_submitted": authorization in _secrets}

from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
def victim_ui():
    return """
    <!DOCTYPE html>
    <html><head><meta charset="utf-8"><title>Finance Assistant</title>
    <style>
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
             background: #0f172a; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
      .card { background: #fff; border-radius: 16px; box-shadow: 0 20px 60px rgba(0,0,0,0.3);
              width: 380px; overflow: hidden; }
      .header { background: linear-gradient(135deg, #1e3a8a, #1e40af); color: #fff; padding: 28px 32px; }
      .header .logo { font-size: 13px; font-weight: 600; letter-spacing: 1px; opacity: 0.7; text-transform: uppercase; }
      .header h1 { font-size: 22px; font-weight: 700; margin-top: 6px; }
      .body { padding: 28px 32px 32px; }
      label { display: block; font-size: 13px; font-weight: 600; color: #475569; margin-bottom: 6px; margin-top: 16px; }
      label:first-child { margin-top: 0; }
      input { width: 100%; padding: 11px 14px; border: 1.5px solid #e2e8f0; border-radius: 8px;
              font-size: 14px; outline: none; }
      input:focus { border-color: #1e40af; }
      button { width: 100%; padding: 12px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600;
               cursor: pointer; margin-top: 20px; }
      .btn-primary { background: #1e40af; color: #fff; }
      .btn-flush { background: #f97316; color: #fff; margin-top: 10px; }
      .btn-secondary { background: #f1f5f9; color: #475569; margin-top: 10px; }
      .status-bar { display: flex; align-items: center; gap: 8px; background: #f0fdf4; border: 1px solid #bbf7d0;
                    border-radius: 8px; padding: 10px 14px; margin-bottom: 20px; font-size: 13px; color: #166534; }
      .dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; }
      .msg { margin-top: 16px; font-size: 13px; color: #64748b; min-height: 18px; }
      .hint { font-size: 12px; color: #94a3b8; margin-top: 4px; }
    </style></head>
    <body>
    <div class="card">
      <div class="header">
        <div class="logo">Tenant A</div>
        <h1>Finance Assistant</h1>
      </div>
      <div class="body">
        <div id="login">
          <label>Username</label>
          <input id="u" value="user_a">
          <label>Password</label>
          <input id="p" type="password" value="researcher-controlled-password">
          <button class="btn-primary" onclick="login()">Sign in</button>
        </div>
        <div id="app" style="display:none;">
          <div class="status-bar"><span class="dot"></span> Signed in as user_a</div>
          <button class="btn-flush" onclick="flushCache()">1. Flush cache first</button>
          <label>Account PIN</label>
          <input id="pin" placeholder="e.g. 482913" maxlength="6">
          <button class="btn-primary" onclick="submitPin()">2. Submit PIN</button>
          <button class="btn-secondary" onclick="logout()">Sign out</button>
          <div class="msg" id="msg"></div>
        </div>
      </div>
    </div>
    <script>
    let token = null;
    async function login() {
      const r = await fetch('/login', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({username: document.getElementById('u').value, password: document.getElementById('p').value})});
      if (r.ok) {
        token = (await r.json()).token;
        document.getElementById('login').style.display = 'none';
        document.getElementById('app').style.display = 'block';
      } else { alert('Login failed'); }
    }
    async function flushCache() {
      await fetch('/flush', {method:'POST'});
      document.getElementById('msg').innerText = 'Cache flushed. Now submit the PIN.';
    }
    async function submitPin() {
      const r = await fetch('/submit', {method:'POST', headers:{'Content-Type':'application/json','Authorization':token},
        body: JSON.stringify({secret: document.getElementById('pin').value})});
      await r.json();
      document.getElementById('msg').innerText = 'Submitted. Now go to the attacker app and click Detect PIN once.';
    }
    async function logout() {
      await fetch('/logout', {method:'POST', headers:{'Authorization':token}});
      token = null;
      document.getElementById('app').style.display = 'none';
      document.getElementById('login').style.display = 'block';
      document.getElementById('pin').value = '';
    }
    </script>
    </body></html>
    """
