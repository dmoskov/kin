#!/usr/bin/env python3
"""
Fix Letta agent embedding configs that point to deprecated endpoints.

Root cause (2026-08-11): Letta's hosted embedding endpoint
(https://inference.letta.com/v1/) began returning 404 on /v1/embeddings,
breaking archival_memory_insert and archival_memory_search for any agent
whose embedding_config still pointed there (model "letta-free", dim 1536).

The fix is to repoint affected agents to the local sidecar embedding server
(http://localhost:8286/v1, model BAAI/bge-small-en-v1.5, dim 384) — the same
config all other agents already use.

Usage:
    # Dry run — show which agents are affected
    python scripts/fix_letta_embedding_config.py

    # Apply the fix
    python scripts/fix_letta_embedding_config.py --fix

Environment:
    LETTA_BASE_URL          Letta API base (default: http://localhost:8283)
    LETTA_SERVER_PASSWORD   Bearer token for Letta API auth
"""

import json
import os
import sys
import urllib.error
import urllib.request

LETTA_BASE_URL = os.environ.get("LETTA_BASE_URL", "http://localhost:8283")
LETTA_TOKEN = os.environ.get("LETTA_SERVER_PASSWORD", "")

DEPRECATED_ENDPOINTS = [
    "inference.letta.com",
    "embeddings.letta.com",
]

TARGET_CONFIG = {
    "embedding_endpoint_type": "openai",
    "embedding_endpoint": "http://localhost:8286/v1",
    "embedding_model": "BAAI/bge-small-en-v1.5",
    "embedding_dim": 384,
    "embedding_chunk_size": 300,
}


def api_request(method, path, body=None):
    url = f"{LETTA_BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {LETTA_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def find_affected_agents():
    agents = api_request("GET", "/v1/agents/?limit=500")
    affected = []
    for agent in agents:
        ec = agent.get("embedding_config") or {}
        endpoint = ec.get("embedding_endpoint") or ""
        if any(dep in endpoint for dep in DEPRECATED_ENDPOINTS):
            affected.append(
                {
                    "id": agent["id"],
                    "name": agent["name"],
                    "current_endpoint": endpoint,
                    "current_model": ec.get("embedding_model"),
                    "current_dim": ec.get("embedding_dim"),
                }
            )
    return affected


def fix_agent(agent_id):
    return api_request(
        "PATCH",
        f"/v1/agents/{agent_id}",
        {"embedding_config": TARGET_CONFIG},
    )


def main():
    apply = "--fix" in sys.argv

    if not LETTA_TOKEN:
        print("ERROR: LETTA_SERVER_PASSWORD not set", file=sys.stderr)
        sys.exit(1)

    try:
        health = api_request("GET", "/v1/health")
        print(f"Letta server: {LETTA_BASE_URL} (v{health.get('version', '?')})")
    except Exception as e:
        print(f"ERROR: Cannot reach Letta server at {LETTA_BASE_URL}: {e}", file=sys.stderr)
        sys.exit(1)

    affected = find_affected_agents()

    if not affected:
        print("All agents use valid embedding endpoints. Nothing to fix.")
        return

    print(f"\nFound {len(affected)} agent(s) with deprecated embedding endpoints:\n")
    for a in affected:
        print(f"  {a['name']} ({a['id']})")
        print(f"    endpoint: {a['current_endpoint']}")
        print(f"    model:    {a['current_model']} (dim={a['current_dim']})")

    if not apply:
        print(f"\nRun with --fix to update these agents to: {TARGET_CONFIG['embedding_endpoint']}")
        return

    print(f"\nApplying fix (target: {TARGET_CONFIG['embedding_endpoint']})...")
    for a in affected:
        try:
            result = fix_agent(a["id"])
            ec = result.get("embedding_config", {})
            print(
                f"  OK: {a['name']} -> {ec.get('embedding_endpoint')} (dim={ec.get('embedding_dim')})"
            )
        except Exception as e:
            print(f"  FAIL: {a['name']}: {e}", file=sys.stderr)

    print("\nDone. Verify with: archival_memory_insert on an affected agent.")


if __name__ == "__main__":
    main()
