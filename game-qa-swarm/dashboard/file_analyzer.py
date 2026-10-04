"""Upload & Analyze — AI Game Bug Scanner for user-submitted Python game files.

Accepts a .py file upload (or 1-click sample game selection), sends the source code to
Cline AI, and returns a structured vulnerability report with severity,
root cause, code-level fix suggestions, and security/logic audit.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import List, Dict

from gameqa.reports.triage import get_cline_config


# ---------------------------------------------------------------------------
# Analysis prompts
# ---------------------------------------------------------------------------

ANALYZER_SYSTEM_PROMPT = (
    "You are an elite Senior Game QA Engineer and Game Engine Security Auditor. "
    "A developer has submitted a Python game source file for automated vulnerability and bug hunting.\n\n"
    "Your mission is to perform a meticulous audit of the code and report ALL bugs, "
    "exploits, logic errors, runtime exceptions, infinite loops, and edge cases.\n\n"
    "Structure your output cleanly in markdown:\n\n"
    "## 📊 Executive Summary\n"
    "- Total Vulnerabilities Found: <number>\n"
    "- Severity Breakdown: <X> Critical, <Y> High, <Z> Medium, <W> Low\n"
    "- Overall Game Stability Grade: <A/B/C/D/F>\n\n"
    "## 🐛 Discovered Vulnerabilities\n\n"
    "For EACH bug, use this exact template:\n"
    "### Bug #N: <Descriptive Title>\n"
    "- **Severity**: `CRITICAL` / `HIGH` / `MEDIUM` / `LOW`\n"
    "- **Category**: (e.g., Runtime Crash, Softlock, Economy Exploit, Bounds Violation, Race Condition, Security Flaw, Memory Leak)\n"
    "- **Location**: Function / class and approximate line number(s)\n"
    "- **Root Cause**: Explain what goes wrong mechanistically\n"
    "- **Reproduction Trigger**: Input scenario or player actions that trigger the defect\n"
    "- **Suggested Fix Patch**:\n"
    "```python\n"
    "# Show concrete fix code\n"
    "```\n\n"
    "## 🛡️ Recommended Architecture & Hardening Actions\n"
    "Provide 3 top priority engineering recommendations to harden this game engine against bugs.\n\n"
    "Rules:\n"
    "- Analyze real bugs in the code (e.g., division by zero, unhandled exceptions, unbounded growth, mutating lists while iterating, negative values underflow, missing collision checks, eval injection).\n"
    "- Be precise, constructive, and provide actionable Python diffs."
)


def analyze_game_file(source_code: str, filename: str = "uploaded_game.py") -> str:
    """Send game source code to Cline AI for comprehensive bug analysis."""
    key, base_url, model = get_cline_config() 

    if not key:
        return _offline_analysis(source_code, filename)

    prompt = (
        "You are an expert Senior Game QA Engineer and Security Auditor. "
        f"Perform an exhaustive bug audit of this Python game file (`{filename}`).\n\n"
        "Audit for:\n"
        "1. Logic bugs & broken mechanics (e.g. inverted damage, healing bugs, infinite loops)\n"
        "2. Runtime crashes & unhandled exceptions (e.g. division by zero, IndexError, KeyError, NoneType)\n"
        "3. Game exploits (e.g. economy/ammo underflow, boundary bypass, cheating)\n"
        "4. Concurrency, state mutations & iterator hazards (e.g. mutating lists during iteration)\n"
        "5. Memory leaks & performance traps (e.g. unbounded lists/particles)\n"
        "6. Critical security issues (e.g. eval/exec of user commands)\n\n"
        "For each issue, specify:\n"
        "- **Severity**: CRITICAL, HIGH, MEDIUM, or LOW\n"
        "- **Location**: Class/function and line area\n"
        "- **Root Cause**: How and why it fails\n"
        "- **Reproduction**: Input sequence or scenario that triggers it\n"
        "- **Suggested Fix**: Ready-to-use Python patch/diff\n\n"
    )

    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": f"### Code for `{filename}`:\n\n```python\n{source_code}\n```"}],
        "temperature": 0.0,
    }
    print(f"Preparing request to {url} with model {model} and payload size {(json.dumps(payload, indent=2))} bytes")

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, ) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        choices = data.get("choices") or (
            data.get("data", {}).get("choices")
            if isinstance(data.get("data"), dict)
            else []
        )
        if choices and choices[0].get("message", {}).get("content"):
            return choices[0]["message"]["content"].strip()
        return f"⚠️ {model} returned an empty response. The file may be too large or the API is busy. Please try again."
    except Exception as exc:
        return (
            f"⚠️ **API Connection Notice:** `{type(exc).__name__}: {exc}`\n\n"
            "Falling back to static heuristic audit below:\n\n"
            + _offline_analysis(source_code, filename)
        )


def _offline_analysis(source_code: str, filename: str) -> str:
    """Basic offline heuristic analysis when no API key is available."""
    lines = source_code.split("\n")
    issues = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Bare except
        if stripped.startswith("except:") or stripped == "except:":
            issues.append(
                f"- **Line {i}**: Bare `except:` clause catches all exceptions including "
                "`KeyboardInterrupt` and `SystemExit`. Use `except Exception:` instead."
            )
        # eval / exec
        if "eval(" in stripped or "exec(" in stripped:
            issues.append(
                f"- **Line {i}**: Dangerous `eval()`/`exec()` call — potential arbitrary code execution vulnerability."
            )
        # Division without guard
        if any(op in stripped for op in ["/=", "/ len(", "/ count", "/ total", "/ n", "/ size"]):
            issues.append(
                f"- **Line {i}**: Potential division by zero if collection or variable is empty/zero."
            )
        # Unbounded array access
        if any(p in stripped for p in ["[0]", "[-1]", "[i]", "[idx]", "[index]"]):
            if "if " not in stripped and "len(" not in stripped and "def " not in stripped:
                issues.append(
                    f"- **Line {i}**: Direct index subscription without boundary check — potential `IndexError`."
                )
        # Global state mutation
        if stripped.startswith("global "):
            issues.append(
                f"- **Line {i}**: `global` variable mutation — susceptible to race conditions and state desynchronization."
            )
        # Unsafe removal during iteration
        if ".remove(" in stripped:
            issues.append(
                f"- **Line {i}**: List `.remove()` call — if executed during iteration, skips subsequent elements or corrupts iteration."
            )

    return (
        f"### Offline Heuristic Scan of `{filename}`\n\n"
        f"Scanned **{len(lines)} lines** — found **{len(issues)} potential issue(s)**:\n\n"
        + ("\n".join(issues) if issues else "✅ No obvious syntax patterns flagged by heuristic scanner.")
        + "\n\n> ⚠️ For full deep AI analysis, ensure your `CLINE_API_KEY` is configured in `.env`."
    )


# ---------------------------------------------------------------------------
# Streamlit UI component
# ---------------------------------------------------------------------------

def render_file_analyzer():
    """Render the file upload & AI analysis tab in Streamlit."""
    import streamlit as st

    key, _, model = get_cline_config()

    # Header banner
    status_color = "#34d399" if key else "#f59e0b"
    status_bg = "#092f25" if key else "#2e1a08"
    status_border = "#047857" if key else "#92400e"
    status_text = "ONLINE · AI READY" if key else "OFFLINE · HEURISTIC ONLY"

    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, #131b2c 0%, #0d1525 100%); border: 1px solid #23324d; border-radius: 10px; padding: 14px 18px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
          <div>
            <div style="font-size: 1.15rem; font-weight: 800; color: #f8fafc; display: flex; align-items: center; gap: 8px;">
              <span>📂</span> Upload & Analyze — AI Game Bug Scanner
            </div>
            <div style="font-size: 0.82rem; color: #94a3b8; margin-top: 3px;">
              Upload any Python game file and get a comprehensive vulnerability report powered by <b>{model}</b>
            </div>
          </div>
          <span style="background: {status_bg}; color: {status_color}; border: 1px solid {status_border}; padding: 3px 10px; border-radius: 4px; font-size: 0.72rem; font-weight: 700; text-transform: uppercase;">{status_text}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Quick demo / samples row
    st.markdown("<div style='color: #94a3b8; font-size: 0.84rem; margin-bottom: 6px; font-weight: 600;'>TRY WITH SAMPLE GAME FILES:</div>", unsafe_allow_html=True)
    samp_col1, samp_col2, samp_col3 = st.columns(3)
    
    with samp_col1:
        if st.button("🚀 Load 'Space Defender' (8 Bugs)", use_container_width=True):
            sample_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "samples", "sample_buggy_game.py")
            if os.path.exists(sample_path):
                with open(sample_path, "r", encoding="utf-8") as f:
                    st.session_state["loaded_game_code"] = f.read()
                    st.session_state["loaded_game_name"] = "sample_buggy_game.py"
                    # Clear prior report
                    st.session_state.pop("file_analysis_result", None)
                    st.rerun()

    with samp_col2:
        if st.button("🏰 Load 'Grid Dungeon' (4 Planted Bugs)", use_container_width=True):
            sample_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gameqa", "game", "grid_game.py")
            if os.path.exists(sample_path):
                with open(sample_path, "r", encoding="utf-8") as f:
                    st.session_state["loaded_game_code"] = f.read()
                    st.session_state["loaded_game_name"] = "grid_game.py"
                    # Clear prior report
                    st.session_state.pop("file_analysis_result", None)
                    st.rerun()

    with samp_col3:
        if st.session_state.get("loaded_game_code"):
            if st.button("❌ Clear Loaded Code", use_container_width=True):
                st.session_state.pop("loaded_game_code", None)
                st.session_state.pop("loaded_game_name", None)
                st.session_state.pop("file_analysis_result", None)
                st.session_state.pop("file_analysis_filename", None)
                st.rerun()

    # File uploader
    uploaded = st.file_uploader(
        "Or upload your own Python game file (.py)",
        type=["py"],
        help="Upload any Python file containing game logic, engine, physics, or entity loops. The AI will audit it for bugs.",
    )

    # Determine which code is active
    active_code = None
    active_filename = None

    if uploaded is not None:
        active_code = uploaded.read().decode("utf-8", errors="replace")
        active_filename = uploaded.name
        # Keep synced in session
        st.session_state["loaded_game_code"] = active_code
        st.session_state["loaded_game_name"] = active_filename
    elif st.session_state.get("loaded_game_code"):
        active_code = st.session_state["loaded_game_code"]
        active_filename = st.session_state.get("loaded_game_name", "game.py")

    if active_code is not None:
        line_count = len(active_code.split("\n"))
        char_count = len(active_code)

        st.markdown(
            f"""
            <div style="background: #131b2c; border: 1px solid #23324d; border-radius: 8px; padding: 12px 16px; margin: 12px 0; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
              <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.4rem;">🐍</span>
                <div>
                  <div style="color: #f8fafc; font-weight: 700; font-size: 0.95rem;">{active_filename}</div>
                  <div style="color: #94a3b8; font-size: 0.78rem;">{line_count:,} lines · {char_count:,} characters · Ready for AI audit</div>
                </div>
              </div>
              <span style="background: #1e293b; color: #93c5fd; border: 1px solid #334155; padding: 2px 8px; border-radius: 4px; font-size: 0.72rem; font-weight: 700;">ACTIVE TARGET</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("📄 Source Code Preview", expanded=False):
            st.code(active_code, language="python", line_numbers=True)

        # Analyze button
        btn_label = f"🚀 Find Bugs with AI in `{active_filename}`"
        if st.button(btn_label, type="primary", use_container_width=True):
            code_to_send = active_code
            if char_count > 100_000:
                st.warning(
                    "⚠️ File exceeds 100K characters. Truncating for AI context limits to prevent timeouts."
                )
                code_to_send = active_code[:80_000] + "\n\n# ... [TRUNCATED] ..."

            status_box = st.status(f"🤖 {model} is auditing `{active_filename}` for bugs...", expanded=True)
            with status_box:
                st.write(f"📂 **File**: `{active_filename}` ({line_count:,} lines)")
                st.write(f"🧠 **Model**: `{model}`")
                st.write("🔍 Inspecting state mutations, boundaries, race conditions, memory leaks, and unhandled traps...")
                st.write("⏳ Generating structured vulnerability audit...")

                result = analyze_game_file(code_to_send, active_filename)

                status_box.update(
                    label="✅ AI Bug Audit Complete!",
                    state="complete",
                    expanded=False,
                )

            st.session_state["file_analysis_result"] = result
            st.session_state["file_analysis_filename"] = active_filename
            st.rerun()

    # Display results if present
    if "file_analysis_result" in st.session_state:
        rep_filename = st.session_state.get("file_analysis_filename", "game.py")
        report_content = st.session_state["file_analysis_result"]

        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #132238 0%, #0d1a2d 100%); border: 1px solid #3b82f6; border-radius: 10px; padding: 14px 18px; margin: 18px 0 12px 0; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
              <div>
                <div style="font-size: 1.1rem; font-weight: 800; color: #f8fafc; display: flex; align-items: center; gap: 8px;">
                  <span>🎯</span> AI Bug Audit Report: <code>{rep_filename}</code>
                </div>
                <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 2px;">
                  Analyzed by <b>{model}</b> · Includes Root Cause, Repro Scenarios, and Fix Patches
                </div>
              </div>
              <span style="background: #092f25; color: #34d399; border: 1px solid #047857; padding: 4px 12px; border-radius: 4px; font-size: 0.74rem; font-weight: 700; text-transform: uppercase;">ANALYSIS COMPLETE</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(report_content)

        # Action buttons: Download & Clear
        st.divider()
        b_col1, b_col2 = st.columns([1, 1])
        with b_col1:
            st.download_button(
                "📥 Download AI Bug Report (.md)",
                data=report_content,
                file_name=f"ai_bug_report_{rep_filename}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with b_col2:
            if st.button("🧹 Clear Report", key="btn-clear-report", use_container_width=True):
                st.session_state.pop("file_analysis_result", None)
                st.rerun()

    elif active_code is None:
        # No file loaded and no results
        st.markdown(
            """
            <div style="background: #0d1322; border: 1px dashed #23324d; border-radius: 10px; padding: 2rem; margin-top: 12px; text-align: center;">
              <div style="font-size: 3rem; margin-bottom: 10px;">🕹️</div>
              <div style="color: #f8fafc; font-size: 1.05rem; font-weight: 700; margin-bottom: 6px;">
                Submit Any Python Game File for AI Bug Auditing
              </div>
              <div style="color: #94a3b8; font-size: 0.88rem; max-width: 580px; margin: 0 auto; line-height: 1.5;">
                Drag and drop your <code>.py</code> game script, or select one of the built-in sample games above to immediately test our <b>{model}</b> AI vulnerability engine.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
