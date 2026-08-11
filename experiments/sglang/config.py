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
