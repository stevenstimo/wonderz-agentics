#!/usr/bin/env python3
"""
Verificatie script voor Agent Lifecycle UI (AL-1 t/m AL-4).

Token ophalen via browser console:
  Object.keys(localStorage)
    .filter(k => k.startsWith('sb-') && k.endsWith('-auth-token'))
    .map(k => JSON.parse(localStorage.getItem(k)).access_token)[0]

Dan in terminal:
  TOKEN="<token>" python3 scripts/verify_agents.py
"""
import os
import re
import sys

try:
    import httpx
except ImportError:
    print("pip install httpx")
    sys.exit(1)

API = os.environ.get("API_URL", "http://localhost:8090")
TOKEN = os.environ.get("TOKEN")


def main():
    if not TOKEN:
        print("Token ophalen via browser console:")
        print("  Object.keys(localStorage)")
        print("    .filter(k => k.startsWith('sb-') && k.endsWith('-auth-token'))")
        print("    .map(k => JSON.parse(localStorage.getItem(k)).access_token)[0]")
        print()
        print("Dan in terminal:")
        print('  TOKEN="<token>" python3 scripts/verify_agents.py')
        sys.exit(1)

    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    results = []

    # 1. GET /api/agents — grid laadt met bestaande agents
    r = httpx.get(f"{API}/api/agents", headers=headers, timeout=10)
    ok = r.status_code == 200
    data = r.json() if ok else {}
    agents = data.get("agents", data) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    if isinstance(agents, dict):
        agents = agents.get("agents", [])
    grid_ok = ok and isinstance(agents, list)
    results.append(("1. /agents grid laadt met bestaande agents", "OK" if grid_ok else f"FAIL {r.status_code}"))
    if grid_ok:
        print(f"  agents in grid: {len(agents)}")

    # 2. POST new agent — agent:<role>:<slug> ID in URL
    r2 = httpx.post(
        f"{API}/api/agents",
        headers=headers,
        json={
            "agent_name": "Verify Test Agent",
            "role": "seo",
            "category": "Marketing",
            "goal": "Test voor verificatie script van Agent Lifecycle UI",
            "system_prompt": "Je bent een test agent voor verificatie. Minimaal 20 tekens.",
            "tool_whitelist": ["read_seo", "optimize_seo"],
        },
        timeout=10,
    )
    created = r2.status_code == 201
    resp2 = r2.json() if created else {}
    agent_id = resp2.get("agent_id", "")
    slug_pattern = re.compile(r"^agent:[a-z0-9-]+:[a-z0-9-]+$")
    slug_ok = created and bool(slug_pattern.match(agent_id))
    results.append(
        ("2. Nieuwe agent aanmaken → agent:<role>:<slug> ID", "OK" if slug_ok else f"FAIL {r2.status_code} id={agent_id}")
    )
    if created:
        print(f"  agent_id: {agent_id}")
    else:
        print(f"  response: {r2.text[:300]}")
        agent_id = agents[0]["agent_id"] if agents else None

    if not agent_id:
        print("\n--- Verificatie (onvolledig) ---")
        for name, status in results:
            print(f"  {name}: {status}")
        sys.exit(1)

    # 3. Deactiveer → agent wordt grijs, verdwijnt niet (PATCH is_active: false)
    r3 = httpx.patch(
        f"{API}/api/agents/{agent_id}",
        headers=headers,
        json={"is_active": False},
        timeout=10,
    )
    patch3_ok = r3.status_code == 200
    r3_after = httpx.get(f"{API}/api/agents", headers=headers, timeout=10)
    agents_after = r3_after.json().get("agents", []) if r3_after.status_code == 200 else []
    still_in_list = any(a.get("agent_id") == agent_id for a in agents_after)
    is_inactive = False
    for a in agents_after:
        if a.get("agent_id") == agent_id:
            is_inactive = a.get("is_active") is False
            break
    deact_ok = patch3_ok and still_in_list and is_inactive
    results.append(
        ("3. Deactiveer → agent wordt grijs, verdwijnt niet", "OK" if deact_ok else f"FAIL patch={patch3_ok} in_list={still_in_list} inactive={is_inactive}")
    )

    # 4. Profiel tab — Opslaan stuurt één PATCH (meerdere velden)
    r4 = httpx.patch(
        f"{API}/api/agents/{agent_id}",
        headers=headers,
        json={
            "name": "Verify Test Updated",
            "goal": "Bijgewerkt doel voor verificatie",
            "system_prompt": "Bijgewerkte system prompt voor verificatie. Minimaal 20 tekens.",
            "tool_access_whitelist": ["read_seo", "optimize_seo", "web_search"],
        },
        timeout=10,
    )
    patch4_ok = r4.status_code == 200
    resp4 = r4.json() if patch4_ok else {}
    name_ok = resp4.get("name") == "Verify Test Updated"
    goal_ok = resp4.get("goal", "").startswith("Bijgewerkt")
    tools_ok = set(resp4.get("tool_access_whitelist", [])) >= {"read_seo", "optimize_seo", "web_search"}
    profile_ok = patch4_ok and name_ok and goal_ok and tools_ok
    results.append(
        ("4. Profiel tab — Opslaan stuurt één PATCH", "OK" if profile_ok else f"FAIL {r4.status_code} name={name_ok} goal={goal_ok} tools={tools_ok}")
    )
    # Annuleren reset zonder API-call: niet te verifiëren via API (frontend-only)

    # 5. is_active toggle — directe activatie (PATCH is_active: true)
    r5 = httpx.patch(
        f"{API}/api/agents/{agent_id}",
        headers=headers,
        json={"is_active": True},
        timeout=10,
    )
    patch5_ok = r5.status_code == 200
    resp5 = r5.json() if patch5_ok else {}
    active_ok = resp5.get("is_active") is True
    toggle_ok = patch5_ok and active_ok
    results.append(
        ("5. is_active toggle — directe activatie zonder modal", "OK" if toggle_ok else f"FAIL {r5.status_code} active={active_ok}")
    )
    # Modal bij deactiveren: niet te verifiëren via API (frontend-only)

    print("\n--- Verificatierapport ---")
    for name, status in results:
        print(f"  {name}: {status}")
    all_ok = all(s == "OK" for _, s in results)
    print()
    print("(Check 4 Annuleren / Check 5 modal: handmatig in UI verifiëren)")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
