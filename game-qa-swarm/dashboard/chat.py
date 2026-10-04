"""AI QA Assistant Chatbot Module for GameQA Swarm.

Powered by DeepSeek V4.1 Flash via Cline API.
Answers user queries regarding game mechanics, detected bugs,
repro sequences, invariant detectors, and code fix patches.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Dict, List

from gameqa.reports.triage import get_cline_config


def build_system_context(store) -> str:
    reports = store.all_reports()
    report_summaries = []
    for r in reports:
        triage = r.triage or {}
        report_summaries.append(
            f"- Bug Signature: {r.signature}\n"
            f"  Title: {r.title or r.summary}\n"
            f"  Severity: {r.severity.upper()}\n"
            f"  Occurrences: {r.occurrences}\n"
            f"  Seed: {r.seed}\n"
            f"  Bot: {r.bot}\n"
            f"  Suspected Cause: {triage.get('suspected_cause', 'Unknown')}\n"
            f"  Suggested Fix Area: {triage.get('suggested_fix_area', 'Unknown')}\n"
            f"  Repro Actions (last 10): {r.actions[-10:] if len(r.actions) > 10 else r.actions}"
        )
    reports_text = "\n\n".join(report_summaries) if report_summaries else "No active bug reports loaded."

    return (
        "You are 'SwarmAI', an elite Game QA Engineer and AI Assistant built into the GameQA Swarm platform.\n"
        "You help game developers, QA leads, and players understand:\n"
        "1. The game mechanics of GridGame (2D grid world with walls, keys, locked doors, hazards, coins, inventory).\n"
        "2. The 4 planted bugs:\n"
        "   - 'softlock|level_01|key_destroyed': DROP action deletes key instead of placing it on the ground, making the level unwinnable.\n"
        "   - 'crash|IndexError|grid_game.py:295:_do_use': Calling USE after DROP empties the inventory causes an IndexError when indexing inventory[0].\n"
        "   - 'exploit|coin_overflow': PICKUP action on coins increments the score without removing the coin from the tile, allowing infinite money loop.\n"
        "   - 'map_hole|inside_wall|4|7': Collision grid disagrees with tilemap at coordinate (4,7), letting the player walk into a wall tile.\n"
        "3. The autonomous swarm fleet (Pathing Agent / BFS solver, Boundary Fuzzer, Chaos Glitcher).\n"
        "4. Invariant detectors (Exception trapping, Reachability solver, Collision bounds, Economy conservation).\n"
        "5. Concrete Python code fixes in `gameqa/game/grid_game.py`.\n\n"
        f"CURRENT ACTIVE BUGS IN REPOSITORY:\n{reports_text}\n\n"
        "Style: Confident, technical, concise, gaming/engineering focused. Use Markdown formatting and syntax-highlighted Python diffs or code blocks when suggesting patches."
    )


def ask_ai_chatbot(messages: List[Dict[str, str]], store) -> str:
    key, base_url, model = get_cline_config()
    system_prompt = build_system_context(store)

    if not key:
        # Graceful offline intelligent responder
        last_user_msg = messages[-1]["content"].lower() if messages else ""
        if "softlock" in last_user_msg or "key" in last_user_msg:
            return (
                "### 🔑 Key Destruction Softlock Analysis\n\n"
                "**Mechanism:** In `GridGame.step('DROP')`, when the player drops the key, the item is removed from `inventory` "
                "but fails to spawn back as an active entity on the floor tile. Because the key is permanently destroyed and there is no respawn logic, "
                "the locked door cannot be opened, causing an irreversible progression lock.\n\n"
                "**Fix in `gameqa/game/grid_game.py`:**\n"
                "```python\n"
                "# In _do_drop(self):\n"
                "item = self.inventory.pop()\n"
                "self.items[self.player_pos] = item  # restore item on current tile\n"
                "```"
            )
        elif "crash" in last_user_msg or "indexerror" in last_user_msg or "use" in last_user_msg:
            return (
                "### 💥 IndexError Crash in `_do_use()`\n\n"
                "**Mechanism:** `_do_use()` assumes the inventory is non-empty and directly evaluates `self.inventory[0]`. "
                "When a sequence executes `DROP` followed by `USE`, the inventory has 0 items, triggering an unhandled `IndexError`.\n\n"
                "**Fix in `gameqa/game/grid_game.py`:**\n"
                "```python\n"
                "def _do_use(self):\n"
                "    if not self.inventory:\n"
                "        return {'status': 'empty_inventory', 'reward': -1}\n"
                "    active_item = self.inventory[0]\n"
                "    ...\n"
                "```"
            )
        elif "coin" in last_user_msg or "exploit" in last_user_msg or "overflow" in last_user_msg:
            return (
                "### 💰 Economy Conservation Exploit (Coin Duplication)\n\n"
                "**Mechanism:** When the player issues a `PICKUP` action over a coin tile, the coin value is added to `self.score`, "
                "but the coin entity is never deleted from `self.coins` map. An agent standing on that coordinate can spam `PICKUP` infinitely.\n\n"
                "**Fix in `gameqa/game/grid_game.py`:**\n"
                "```python\n"
                "if self.player_pos in self.coins:\n"
                "    self.score += self.coins.pop(self.player_pos)  # remove after pickup\n"
                "```"
            )
        elif "wall" in last_user_msg or "hole" in last_user_msg or "4,7" in last_user_msg:
            return (
                "### 🧱 Map Hole & Collision Bounds Failure at (4,7)\n\n"
                "**Mechanism:** The tilemap in `maps.py` defines tile `(4, 7)` as a wall character `'#'`, but the collision bitmask "
                "in `GridGame.walkable` mistakenly marks `(4, 7)` as walkable. Agents can phase through boundary geometry.\n\n"
                "**Fix in `gameqa/game/maps.py`:**\n"
                "Ensure collision array syncs 1:1 with `MAP_RAW` tile definitions."
            )
        else:
            return (
                "Hello! I am **SwarmAI**, your QA copilot. You can ask me about:\n"
                "- How the autonomous swarm agents explore maps.\n"
                "- Details, repro seeds, and root causes of the 4 planted vulnerabilities.\n"
                "- Python code patches to fix detected bugs.\n"
                "- How invariant detectors catch anomalies in real time."
            )

    payload_messages = [{"role": "system", "content": system_prompt}]
    # Add conversation history (up to last 10 messages)
    for m in messages[-10:]:
        payload_messages.append({"role": m["role"], "content": m["content"]})

    url = f"{base_url}/chat/completions"
    data = {
        "model": model,
        "messages": payload_messages,
        "max_tokens": 8192,
        "temperature": 0.3,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
        choices = res_json.get("choices") or (res_json.get("data", {}).get("choices") if isinstance(res_json.get("data"), dict) else [])
        if choices and choices[0].get("message", {}).get("content"):
            return choices[0]["message"]["content"].strip()
        return f"I received an empty response from {model} API. Please try asking again."
    except Exception as exc:
        return f"⚠️ **API Connection Error:** {exc}\n\nPlease check your internet connection or verify `.env` settings."


def render_chatbot(store):
    import streamlit as st

    key, base_url, model = get_cline_config()

    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, #131b2c 0%, #0d1525 100%); border: 1px solid #23324d; border-radius: 10px; padding: 14px 18px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
          <div>
            <div style="font-size: 1.15rem; font-weight: 800; color: #f8fafc; display: flex; align-items: center; gap: 8px;">
              <span>🤖</span> SwarmAI — Intelligent Game QA Assistant
            </div>
            <div style="font-size: 0.82rem; color: #94a3b8; margin-top: 3px;">
              Direct conversational interface powered by <b>{model}</b>
            </div>
          </div>
          <span style="background: #092f25; color: #34d399; border: 1px solid #047857; padding: 3px 10px; border-radius: 4px; font-size: 0.72rem; font-weight: 700; text-transform: uppercase;">ONLINE &middot; READY</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = [
            {
                "role": "assistant",
                "content": (
                    "👋 **Greetings! I am SwarmAI.**\n\n"
                    "I have full awareness of the game mechanics, the multi-agent testing swarm, "
                    "and the active defect telemetry. Ask me anything about:\n"
                    "- 🔍 **Why bugs occur** (softlocks, crashes, wall clips, coin duplication)\n"
                    "- 🛠️ **Code patches** to fix vulnerabilities in `gameqa/game/grid_game.py`\n"
                    "- 🤖 **How autonomous agents test boundaries** and invariant checkers\n"
                    "- 🕹️ **Reproducing failures** deterministically with discrete action sequences"
                ),
            }
        ]

    # Quick prompt shortcuts
    st.markdown("<div style='font-size:0.75rem; text-transform:uppercase; color:#94a3b8; font-weight:700; margin-bottom:8px;'>⚡ Suggested Inquiries</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c4, c5, c6 = st.columns(3)
    
    prompt_to_send = None
    if c1.button("🔑 Explain Key Softlock Bug", use_container_width=True):
        prompt_to_send = "Why does dropping the key cause a softlock on level_01?"
    if c2.button("💥 Fix IndexError in _do_use", use_container_width=True):
        prompt_to_send = "How do I fix the IndexError crash in _do_use()?"
    if c3.button("💰 Explain Coin Duplication", use_container_width=True):
        prompt_to_send = "How does the coin overflow exploit violate economy conservation?"
    if c4.button("🧱 Explain Wall Hole at (4,7)", use_container_width=True):
        prompt_to_send = "Why can the agent walk into the wall at (4,7)?"
    if c5.button("🤖 How do Swarm Bots work?", use_container_width=True):
        prompt_to_send = "Explain the differences between the Pathing Agent, Boundary Fuzzer, and Chaos Glitcher."
    if c6.button("🧹 Clear Chat History", use_container_width=True):
        st.session_state["chat_messages"] = [
            {
                "role": "assistant",
                "content": "Conversation cleared. What would you like to investigate next?",
            }
        ]
        st.rerun()

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # Render conversation
    for msg in st.session_state["chat_messages"]:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(msg["content"])

    # Handle suggested prompt click
    if prompt_to_send:
        st.session_state["chat_messages"].append({"role": "user", "content": prompt_to_send})
        with st.chat_message("user"):
            st.markdown(prompt_to_send)
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("SwarmAI is analyzing query with DeepSeek V4.1 Flash..."):
                response = ask_ai_chatbot(st.session_state["chat_messages"], store)
                st.markdown(response)
        st.session_state["chat_messages"].append({"role": "assistant", "content": response})
        st.rerun()

    # User chat input
    user_input = st.chat_input("Ask SwarmAI anything about game bugs, reproduction steps, or code fixes...")
    if user_input:
        st.session_state["chat_messages"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("SwarmAI is analyzing query with DeepSeek V4.1 Flash..."):
                response = ask_ai_chatbot(st.session_state["chat_messages"], store)
                st.markdown(response)
        st.session_state["chat_messages"].append({"role": "assistant", "content": response})
        st.rerun()

