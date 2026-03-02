#!/usr/bin/env python3
"""
Fix Bug 1 & Bug 2: Callback forwarding and duplicate Telegram webhooks.

Bug 1: In COMMANDS workflow, `Detectar Tipo Mensaje` does JSON.stringify(body)
       into full_body, but `Reenviar Callback` needs an object, not a string.
       Fix: pass body directly (no stringify) so `Reenviar Callback` gets an object.

Bug 2: WRITER has a webhook at path `ma-telegram-v2` that competes with COMMANDS.
       Fix: rename WRITER webhook path to `ma-writer-callback` and update the
       COMMANDS forwarding URL to match.

Usage:
  N8N_API_KEY=<your-key> python fix_callback_forwarding.py
  # or set API_KEY below and run directly
"""
import json
import os
import re
import requests

API_KEY  = os.environ.get("N8N_API_KEY", "N8N_API_KEY_HERE")
BASE_URL = "https://n8n.camiloayala.net/api/v1"
HEADERS  = {"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"}

COMMANDS_ID = "rHiCJjTdBVqwtzPV"
WRITER_ID   = "p71hf2LpPVg7vcSO"

READ_ONLY_FIELDS = {"id", "createdAt", "updatedAt", "versionId"}


def get_workflow(wf_id):
    r = requests.get(f"{BASE_URL}/workflows/{wf_id}", headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


def put_workflow(wf_id, wf):
    payload = {k: v for k, v in wf.items() if k not in READ_ONLY_FIELDS}
    r = requests.put(f"{BASE_URL}/workflows/{wf_id}", headers=HEADERS,
                     json=payload, timeout=15)
    r.raise_for_status()
    return r.json()


def fix_commands(wf):
    """
    1. Detectar Tipo Mensaje: replace JSON.stringify(body) with body
    2. Reenviar Callback*:   update URL from ma-telegram-v2 to ma-writer-callback
    """
    changes = []
    for node in wf.get("nodes", []):
        name = node.get("name", "")

        # Fix 1: Detectar Tipo Mensaje — pass body object, not string
        if "Detectar Tipo Mensaje" in name:
            code = node.get("parameters", {}).get("jsCode", "")
            new_code = re.sub(r"full_body:\s*JSON\.stringify\(body\)", "full_body: body", code)
            if new_code != code:
                node["parameters"]["jsCode"] = new_code
                changes.append(f"  ✅ [{name}] JSON.stringify(body) → body")
            else:
                changes.append(f"  ⚠️  [{name}] pattern not found — already fixed?")

        # Fix 2: Reenviar Callback — update forwarding URL
        if "Reenviar Callback" in name:
            params = node.get("parameters", {})
            url = params.get("url", "")
            if "ma-telegram-v2" in url:
                params["url"] = url.replace("ma-telegram-v2", "ma-writer-callback")
                changes.append(f"  ✅ [{name}] URL ma-telegram-v2 → ma-writer-callback")
            elif url:
                changes.append(f"  ℹ️  [{name}] URL already updated: {url}")

    return changes


def fix_writer(wf):
    """
    Find any webhook node with path ma-telegram-v2 and rename it to ma-writer-callback.
    """
    changes = []
    for node in wf.get("nodes", []):
        params = node.get("parameters", {})
        if node.get("type") == "n8n-nodes-base.webhook":
            path = params.get("path", "")
            if path == "ma-telegram-v2":
                params["path"] = "ma-writer-callback"
                changes.append(
                    f"  ✅ [{node.get('name', '?')}] path ma-telegram-v2 → ma-writer-callback"
                )
    return changes


def main():
    # ── COMMANDS ────────────────────────────────────────────────────────
    print(f"Fetching COMMANDS workflow ({COMMANDS_ID})...")
    commands_wf = get_workflow(COMMANDS_ID)
    print(f"  Nodes: {len(commands_wf.get('nodes', []))}")

    cmd_changes = fix_commands(commands_wf)
    if cmd_changes:
        print("Applying fixes to COMMANDS:")
        for c in cmd_changes:
            print(c)
        print("PUTting COMMANDS workflow...")
        put_workflow(COMMANDS_ID, commands_wf)
        print("  ✅ COMMANDS updated successfully")
    else:
        print("  ℹ️  No changes needed in COMMANDS")

    # ── WRITER ──────────────────────────────────────────────────────────
    print(f"\nFetching WRITER workflow ({WRITER_ID})...")
    writer_wf = get_workflow(WRITER_ID)
    print(f"  Nodes: {len(writer_wf.get('nodes', []))}")

    wrt_changes = fix_writer(writer_wf)
    if wrt_changes:
        print("Applying fixes to WRITER:")
        for c in wrt_changes:
            print(c)
        print("PUTting WRITER workflow...")
        put_workflow(WRITER_ID, writer_wf)
        print("  ✅ WRITER updated successfully")
    else:
        print("  ℹ️  No webhook with path ma-telegram-v2 found in WRITER (already fixed?)")

    print("\nDone.")
    print("  COMMANDS is now the single Telegram entry point.")
    print("  WRITER webhook path: /webhook/ma-writer-callback")
    print("  COMMANDS forwards callbacks to: /webhook/ma-writer-callback")


if __name__ == "__main__":
    main()
