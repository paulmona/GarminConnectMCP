#!/usr/bin/env python3
"""
End-to-end test: full OAuth PKCE flow → POST /mcp with token.
Run from the repo root:  python3 test_mcp_oauth.py
"""
import base64
import hashlib
import json
import os
import secrets
import sys
from urllib.parse import parse_qs, quote, urlparse

import httpx

SERVER = os.environ.get("MCP_SERVER_URL", "").rstrip("/")
if not SERVER:
    print("Error: MCP_SERVER_URL environment variable must be set")
    print("  Example: MCP_SERVER_URL=https://example.com python3 test_mcp_oauth.py")
    sys.exit(1)

# ── 1. PKCE ─────────────────────────────────────────────────────────────────
code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).rstrip(b"=").decode()
state = base64.urlsafe_b64encode(secrets.token_bytes(16)).rstrip(b"=").decode()
redirect_uri = "https://httpbin.org/get"  # just needs to accept the redirect

print("=== Step 1: PKCE values generated ===")
print(f"  code_verifier: {code_verifier[:20]}...")

# ── 2. Dynamic client registration ──────────────────────────────────────────
print("\n=== Step 2: POST /register ===")
r = httpx.post(f"{SERVER}/register", json={
    "redirect_uris": [redirect_uri],
    "grant_types": ["authorization_code", "refresh_token"],
    "response_types": ["code"],
    "token_endpoint_auth_method": "none",
})
print(f"  status: {r.status_code}")
print(f"  body:   {r.text}")
r.raise_for_status()
client_id = r.json()["client_id"]
print(f"  client_id: {client_id}")

# ── 3. /authorize → extract code from redirect ───────────────────────────────
print("\n=== Step 3: GET /authorize ===")
auth_url = (
    f"{SERVER}/authorize"
    f"?response_type=code"
    f"&client_id={client_id}"
    f"&redirect_uri={quote(redirect_uri)}"
    f"&code_challenge={code_challenge}"
    f"&code_challenge_method=S256"
    f"&state={state}"
    f"&scope=claudeai"
    f"&resource={quote(SERVER + '/mcp')}"
)
r = httpx.get(auth_url, follow_redirects=False)
print(f"  status: {r.status_code}")
location = r.headers.get("location", "")
print(f"  location: {location[:100]}...")
qs = parse_qs(urlparse(location).query)
code = qs["code"][0]
print(f"  code: {code[:20]}...")

# ── 4. POST /token ───────────────────────────────────────────────────────────
print("\n=== Step 4: POST /token ===")
r = httpx.post(f"{SERVER}/token", data={
    "grant_type": "authorization_code",
    "code": code,
    "redirect_uri": redirect_uri,
    "client_id": client_id,
    "code_verifier": code_verifier,
    "resource": SERVER + "/mcp",
})
print(f"  status: {r.status_code}")
print(f"  body:   {r.text}")
r.raise_for_status()
access_token = r.json()["access_token"]
print(f"  access_token: {access_token[:20]}...")

# ── 5. POST /mcp with the OAuth token ────────────────────────────────────────
print("\n=== Step 5: POST /mcp (with Bearer token) ===")
r = httpx.post(
    f"{SERVER}/mcp",
    headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    },
    json={
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": 1,
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "mcp-oauth-test", "version": "0.1"},
        },
    },
    follow_redirects=False,
    timeout=30,
)
print(f"  status: {r.status_code}")
print(f"  headers: {dict(r.headers)}")
print(f"  body:   {r.text[:1000]}")

if r.status_code == 200:
    print("\n✓  POST /mcp succeeded — server-side OAuth + MCP is working!")
elif r.status_code == 401:
    print("\n✗  POST /mcp returned 401 — token was not accepted")
else:
    print(f"\n?  Unexpected status {r.status_code}")
