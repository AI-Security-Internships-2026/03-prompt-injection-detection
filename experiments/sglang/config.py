"""
config.py — Shared prefix known to both tenants (public system prompt),
and the VICTIM-ONLY secret. This file simulates the trust boundary:
in a real deployment this would be two separate processes/keys.
Attacker-side code must never import SECRET_SUFFIX directly.
"""

SHARED_PUBLIC_PREFIX = (
    "You are a customer support assistant for a cloud infrastructure company. "
    "Below is the internal knowledge base context shared across all support sessions. "
    "Use this context to answer user questions about billing, deployment, and account "
    "management. Always be concise and professional. The following section contains "
    "account-specific context for the current session: "
) * 3

# GROUND TRUTH — victim-only. Attacker code must never reference this.
VICTIM_SECRET_SUFFIX = "Account tier: ENTERPRISE-GOLD-7734. Support priority: P1."

# --- Level 2: candidate set for information-recovery pilot ---
# Same entropy category (low-entropy, short synthetic status words).
# Victim selects exactly one at random; attacker never imports this list's
# selection directly — only the orchestration loop in run_candidate_recovery.py
# knows the ground truth.
CANDIDATES = [
    "Status: OK.",
    "Status: NO.",
    "Status: YES.",
    "Status: TBD.",
]

# --- Level 2: predictable-prefix candidate set ---
# Shares a common "SK-" sub-prefix before diverging, unlike CANDIDATES
# (low-entropy set) which diverges at the first token. Harder case for
# the cache oracle. Same trust-boundary rules apply: ground truth stays
# only in the orchestration loop.
CANDIDATES_PREFIX = [
    "SK-AB12",
    "SK-CD34",
    "SK-EF56",
    "SK-GH78",
]


# --- Level 2: structured candidate set (synthetic 6-digit PIN) ---
# Numeric, fixed-width, all same length. Fully synthetic values, no
# relation to any real account or credential.
CANDIDATES_PIN = [
    "482913",
    "719045",
    "356820",
    "904271",
]

# --- Level 2: high-entropy candidate set (synthetic UUID-like values) ---
# Long, high-entropy, fixed-width synthetic values. No relation to any
# real identifier, credential, or system.
CANDIDATES_UUID = [
    "a3f9e21c-77db-4e15-9c2a-6f1d8b0e4a92",
    "b7c1029f-4482-4a3e-8d1c-2e9f7a5b0c14",
    "d4e8a736-91fc-4b2a-af05-3c7d1e9b6820",
    "f2091ac8-6b3d-47e9-95a1-8e0c4d3f7b56",
]


# --- Level 3 pilot: per-digit PIN inference (position 1 of 6) ---
PIN_LENGTH = 6
PIN_PLACEHOLDER_DIGIT = "0"

# --- Level 3 pilot v2: comma-separated digits to prevent BPE merging ---
PIN_LABEL = "PIN: "
PIN_SEPARATOR = ","

# --- Level 3 fix: trailing marker so last digit is never the literal end of prompt ---
PIN_TRAILING_MARKER = "."
