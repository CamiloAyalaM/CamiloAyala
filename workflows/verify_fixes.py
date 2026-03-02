#!/usr/bin/env python3
"""
Verify that the callback-forwarding fixes are live in N8N production.

Checks:
  COMMANDS workflow (rHiCJjTdBVqwtzPV):
    1. `Detectar Tipo Mensaje` jsCode does NOT contain JSON.stringify(body)
    2. `Reenviar Callback` URL contains ma-writer-callback (not ma-telegram-v2)
  WRITER workflow (p71hf2LpPVg7vcSO):
    3. No webhook node has path ma-telegram-v2 (should be ma-writer-callback)

Usage:
  N8N_API_KEY=<your-key> python3 verify_fixes.py
"""
import os
import sys
import requests

API_KEY  = os.environ.get("N8N_API_KEY", "N8N_API_KEY_HERE")
BASE_URL = "https://n8n.camiloayala.net/api/v1"
HEADERS  = {"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"}

COMMANDS_ID = "rHiCJjTdBVqwtzPV"
WRITER_ID   = "p71hf2LpPVg7vcSO"


def get_workflow(wf_id):
    try:
        r = requests.get(f"{BASE_URL}/workflows/{wf_id}", headers=HEADERS, timeout=15)
        r.raise_for_status()
    except requests.exceptions.ConnectionError as exc:
        sys.exit(f"Connection error — is N8N reachable? ({exc})")
    except requests.exceptions.HTTPError as exc:
        sys.exit(f"HTTP {exc.response.status_code} for workflow {wf_id} — check API key.")
    return r.json()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    return condition


def main():
    all_pass = True

    # ── COMMANDS ────────────────────────────────────────────────────────
    print(f"Fetching COMMANDS workflow ({COMMANDS_ID})...")
    commands_wf = get_workflow(COMMANDS_ID)
    print(f"  Nodes: {len(commands_wf.get('nodes', []))}")
    print("Checking COMMANDS fixes:")

    detectar_ok = False
    reenviar_ok = False
    for node in commands_wf.get("nodes", []):
        name = node.get("name", "")
        if "Detectar Tipo Mensaje" in name:
            code = node.get("parameters", {}).get("jsCode", "")
            detectar_ok = "JSON.stringify(body)" not in code
        if "Reenviar Callback" in name:
            url = node.get("parameters", {}).get("url", "")
            reenviar_ok = "ma-writer-callback" in url and "ma-telegram-v2" not in url

    all_pass &= check(
        "Detectar Tipo Mensaje: no JSON.stringify(body) in jsCode", detectar_ok
    )
    all_pass &= check(
        "Reenviar Callback: URL contains ma-writer-callback", reenviar_ok
    )

    # ── WRITER ──────────────────────────────────────────────────────────
    print(f"\nFetching WRITER workflow ({WRITER_ID})...")
    writer_wf = get_workflow(WRITER_ID)
    print(f"  Nodes: {len(writer_wf.get('nodes', []))}")
    print("Checking WRITER fixes:")

    webhook_ok = True
    for node in writer_wf.get("nodes", []):
        if node.get("type") == "n8n-nodes-base.webhook":
            path = node.get("parameters", {}).get("path", "")
            if path == "ma-telegram-v2":
                webhook_ok = False

    all_pass &= check(
        "WRITER: no webhook with path ma-telegram-v2 (should be ma-writer-callback)",
        webhook_ok,
    )

    print()
    if all_pass:
        print("✅ All checks PASSED — fixes are live in production.")
    else:
        print("❌ Some checks FAILED — review output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
