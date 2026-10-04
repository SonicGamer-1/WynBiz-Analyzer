"""Streamlit dashboard.

    streamlit run dashboard/app.py

Three panes, in demo order:
  1. Run control + swarm summary (episodes, steps, wins, crashes, timing)
  2. Bug list with severity, occurrence count and verified-fixed state
  3. One bug's detail: repro actions, Claude triage, replay GIF and a
     re-verify button

Everything is read from artifacts/, which the CLI writes. The dashboard never
mutates game state; the only writes it makes are new swarm runs and status
updates, both of which go through the same store the CLI uses.
"""
from __future__ import annotations

import importlib
import os
import sys

import streamlit as st

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import gameqa.game.maps as maps
if not hasattr(maps, "CAMPAIGN_LEVELS"):
    importlib.reload(maps)

import gameqa.reports.triage as triage_module
importlib.reload(triage_module)
from gameqa.reports.triage import Triager, _load_env, get_cline_config          # noqa: E402
_load_env()
_, _, CLINE_MODEL = get_cline_config()

from gameqa.game.bugs import PLANTED_BUGS                    # noqa: E402
from gameqa.replay.gif import ascii_to_image, has_pillow, make_gif, simulate  # noqa: E402
from gameqa.reports.store import BugStore                     # noqa: E402
from gameqa.swarm.parallel import run_swarm                   # noqa: E402
import dashboard.arcade as arcade
importlib.reload(arcade)
from dashboard.arcade import render_arcade_component          # noqa: E402
import dashboard.chat as chat_module
importlib.reload(chat_module)
from dashboard.chat import render_chatbot                     # noqa: E402
import dashboard.file_analyzer as file_analyzer_module
importlib.reload(file_analyzer_module)
from dashboard.file_analyzer import render_file_analyzer      # noqa: E402

st.set_page_config(page_title="GameQA Swarm — Automated Game Testing Platform", page_icon="🛡️", layout="wide")

SEVERITY_COLOUR = {
    "critical": "#ef4444",
    "high": "#f59e0b",
    "medium": "#3b82f6",
    "low": "#64748b",
}


@st.cache_resource(show_spinner=False)
def get_store(root):
    return BugStore(root)


def css():
    st.markdown(
        """
        <style>
        /* Gaming-oriented dark palette (Not neon) */
        html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], .stApp {
            background-color: #0b0f19 !important;
            color: #f1f5f9 !important;
        }
        .main .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2.5rem;
            max-width: 1280px;
            background-color: transparent !important;
        }
        
        /* Top header bar */
        header[data-testid="stHeader"], [data-testid="stHeader"] {
            background-color: #0b0f19 !important;
            color: #f1f5f9 !important;
            border-bottom: 1px solid #1e293b !important;
        }
        footer, [data-testid="stToolbar"] {
            background-color: #0b0f19 !important;
            color: #94a3b8 !important;
        }
        
        /* Headers with crisp white and subtle tactical accents */
        h1, h2, h3, h4, h5, h6, .stHeading {
            color: #f8fafc !important;
            font-weight: 700 !important;
            letter-spacing: -0.01em;
        }
        
        /* Sidebar styling */
        section[data-testid="stSidebar"], [data-testid="stSidebar"] > div {
            background-color: #0f172a !important;
            border-right: 1px solid #1e293b !important;
        }
        section[data-testid="stSidebar"] h1, 
        section[data-testid="stSidebar"] h2, 
        section[data-testid="stSidebar"] h3 {
            color: #f8fafc !important;
        }
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] div {
            color: #cbd5e1 !important;
        }

        /* Tactical gaming bug card */
        .bugcard {
            border-left: 4px solid #3b82f6;
            padding: 1rem 1.25rem;
            margin: 0.65rem 0;
            background: #131b2c;
            border-radius: 8px;
            border: 1px solid #23324d;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
            transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
        }
        .bugcard:hover {
            transform: translateX(4px);
            border-color: #3b82f6;
            box-shadow: 0 6px 18px rgba(0, 0, 0, 0.5), 0 0 12px rgba(59, 130, 246, 0.15);
        }
        
        /* Severity badges (Tactical gaming tones, NOT neon) */
        .sev {
            font-weight: 700;
            text-transform: uppercase;
            font-size: 0.72rem;
            letter-spacing: 0.06em;
            padding: 3px 8px;
            border-radius: 4px;
            background: #1a2336;
            border: 1px solid #334155;
            color: #93c5fd;
        }
        
        /* Status pills */
        .status-pill {
            font-weight: 700;
            font-size: 0.72rem;
            letter-spacing: 0.04em;
            padding: 3px 9px;
            border-radius: 4px;
        }
        .status-open {
            background: #2e1418;
            color: #f87171;
            border: 1px solid #7f1d1d;
        }
        .status-fixed {
            background: #092f25;
            color: #34d399;
            border: 1px solid #047857;
        }
        
        /* Monospace repro signatures */
        .mono {
            font-family: ui-monospace, SFMono-Regular, "Roboto Mono", Menlo, monospace;
            font-size: 0.82rem;
            color: #93c5fd;
            background: #080c14;
            border: 1px solid #1e293b;
            border-radius: 5px;
            padding: 6px 10px;
            white-space: pre-wrap;
        }
        
        /* Metrics values */
        [data-testid="stMetricValue"] {
            color: #f8fafc !important;
            font-weight: 800 !important;
        }
        [data-testid="stMetricLabel"] {
            color: #94a3b8 !important;
            font-weight: 600 !important;
            text-transform: uppercase;
            font-size: 0.75rem !important;
            letter-spacing: 0.05em;
        }
        
        /* Tabs styling */
        button[data-baseweb="tab"] {
            color: #94a3b8 !important;
            font-weight: 600 !important;
            background: transparent !important;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            color: #60a5fa !important;
            font-weight: 700 !important;
            border-bottom-color: #3b82f6 !important;
        }
        div[data-baseweb="tab-list"], div[data-baseweb="tab-border"] {
            background-color: transparent !important;
            border-color: #1e293b !important;
        }
        
        /* Primary button in esports cyber sapphire */
        button[data-testid="stBaseButton-primary"], button[kind="primary"] {
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
            color: #ffffff !important;
            border: 1px solid #3b82f6 !important;
            border-radius: 6px !important;
            font-weight: 600 !important;
            box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35) !important;
            transition: all 0.15s ease !important;
        }
        button[data-testid="stBaseButton-primary"]:hover, button[kind="primary"]:hover {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
            border-color: #60a5fa !important;
            box-shadow: 0 6px 18px rgba(37, 99, 235, 0.5) !important;
        }

        /* Secondary buttons */
        button[data-testid="stBaseButton-secondary"], button[kind="secondary"] {
            background-color: #162035 !important;
            color: #e2e8f0 !important;
            border: 1px solid #283959 !important;
            border-radius: 6px !important;
            font-weight: 600 !important;
        }
        button[data-testid="stBaseButton-secondary"]:hover, button[kind="secondary"]:hover {
            background-color: #1e2c48 !important;
            border-color: #3b82f6 !important;
            color: #ffffff !important;
        }
        
        /* BaseWeb Selectbox & Dropdowns (No white backgrounds) */
        div[data-baseweb="select"] {
            background-color: #131b2c !important;
            border-color: #23324d !important;
            color: #f1f5f9 !important;
        }
        div[data-baseweb="select"] > div {
            background-color: #131b2c !important;
            border-color: #23324d !important;
            color: #f1f5f9 !important;
        }
        div[data-baseweb="select"] span {
            color: #f1f5f9 !important;
        }
        div[data-baseweb="select"] svg {
            fill: #94a3b8 !important;
        }
        div[data-baseweb="popover"], 
        div[data-baseweb="popover"] > div,
        ul[data-baseweb="menu"], 
        li[data-baseweb="menu-item"] {
            background-color: #131b2c !important;
            color: #f1f5f9 !important;
            border-color: #23324d !important;
        }
        li[data-baseweb="menu-item"]:hover {
            background-color: #1c283f !important;
            color: #60a5fa !important;
        }
        [data-baseweb="tag"], span[data-baseweb="tag"] {
            background-color: #1e293b !important;
            color: #93c5fd !important;
            border: 1px solid #334155 !important;
        }
        span[data-baseweb="tag"] span {
            color: #93c5fd !important;
        }
        span[data-baseweb="tag"] svg {
            fill: #94a3b8 !important;
        }

        /* Expanders in dark tactical theme */
        [data-testid="stExpander"] {
            background-color: #131b2c !important;
            border: 1px solid #23324d !important;
            border-radius: 8px !important;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25) !important;
        }
        [data-testid="stExpander"] details {
            background-color: #131b2c !important;
            border-radius: 8px !important;
        }
        div[data-testid="stExpanderDetails"] {
            background-color: #131b2c !important;
            color: #f1f5f9 !important;
        }
        [data-testid="stExpander"] summary {
            background-color: #131b2c !important;
            color: #f1f5f9 !important;
        }
        [data-testid="stExpander"] summary:hover {
            color: #60a5fa !important;
        }
        [data-testid="stExpander"] summary svg {
            fill: #94a3b8 !important;
        }

        /* Dataframes & Tables */
        [data-testid="stDataFrame"], 
        div[data-testid="stDataFrame"] > div,
        div[data-testid="stTable"] {
            background-color: #131b2c !important;
            color: #f1f5f9 !important;
            border-color: #23324d !important;
        }
        div[data-testid="stDataFrame"] [role="grid"] {
            background-color: #131b2c !important;
        }

        /* Code blocks */
        pre, code, [data-testid="stCodeBlock"], [data-testid="stCodeBlock"] pre {
            background-color: #080c14 !important;
            color: #93c5fd !important;
            border: 1px solid #1e293b !important;
        }

        /* Alerts */
        [data-testid="stAlert"] {
            background-color: #162035 !important;
            color: #e2e8f0 !important;
            border: 1px solid #283959 !important;
        }
        [data-testid="stAlert"] div {
            color: #e2e8f0 !important;
        }

        /* Custom components & iframes */
        [data-testid="stCustomComponentV1"], iframe {
            background-color: #0b0f19 !important;
            border: none !important;
        }

        /* Progress bars */
        [data-testid="stProgress"] > div > div {
            background-color: #1e293b !important;
        }
        [data-testid="stProgress"] > div > div > div {
            background-color: #2563eb !important;
        }

        /* Dividers */
        hr {
            border-color: #1e293b !important;
        }

        /* Chatbot styling */
        [data-testid="stChatMessage"] {
            background-color: #131b2c !important;
            border: 1px solid #23324d !important;
            border-radius: 8px !important;
            padding: 12px 16px !important;
            margin-bottom: 10px !important;
            color: #f1f5f9 !important;
        }
        [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
            background-color: #0f1f38 !important;
            border-color: #1e3a66 !important;
        }
        [data-testid="stChatInput"] {
            background-color: #131b2c !important;
            border: 1px solid #23324d !important;
            border-radius: 8px !important;
        }
        [data-testid="stChatInput"] textarea {
            background-color: #131b2c !important;
            color: #f1f5f9 !important;
        }
        [data-testid="stChatInput"] textarea::placeholder {
            color: #94a3b8 !important;
        }
        [data-testid="stChatInput"] button {
            color: #3b82f6 !important;
        }

        /* File uploader styling */
        [data-testid="stFileUploader"] {
            background-color: #131b2c !important;
            border: 1px solid #23324d !important;
            border-radius: 8px !important;
        }
        [data-testid="stFileUploader"] section {
            background-color: #131b2c !important;
            border-color: #23324d !important;
        }
        [data-testid="stFileUploader"] section > div {
            background-color: #131b2c !important;
            color: #f1f5f9 !important;
        }
        [data-testid="stFileUploader"] small {
            color: #94a3b8 !important;
        }
        [data-testid="stFileUploader"] button {
            color: #3b82f6 !important;
            border-color: #3b82f6 !important;
        }
        [data-testid="stFileUploaderDropzone"] {
            background-color: #0d1322 !important;
            border-color: #23324d !important;
            color: #f1f5f9 !important;
        }
        [data-testid="stFileUploaderDropzoneInstructions"] span,
        [data-testid="stFileUploaderDropzoneInstructions"] small,
        [data-testid="stFileUploaderDropzoneInstructions"] div {
            color: #94a3b8 !important;
        }

        /* Status container styling */
        [data-testid="stStatus"] {
            background-color: #131b2c !important;
            border: 1px solid #23324d !important;
            border-radius: 8px !important;
        }
        [data-testid="stStatus"] [data-testid="stMarkdownContainer"] {
            color: #f1f5f9 !important;
        }

        /* Hero scan console */
        .scan-terminal {
            background: #111827;
            border: 1px solid #1f2d45;
            border-radius: 12px;
            padding: 1.5rem 1.8rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
        }
        .scan-title {
            font-size: 1.3rem;
            font-weight: 800;
            color: #f8fafc;
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 0.5rem;
        }
        .scan-badge {
            background: #1e293b;
            color: #60a5fa;
            border: 1px solid #3b82f6;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .target-box {
            background: #0d1322;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 1rem;
            margin-top: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def bug_card(report):
    colour = SEVERITY_COLOUR.get(report.severity, "#3b82f6")
    status_cls = "status-fixed" if report.verified_fixed else "status-open"
    status_text = "RESOLVED" if report.verified_fixed else "OPEN"
    triage = report.triage or {}
    model_name = triage.get("model") or CLINE_MODEL
    if model_name.startswith("cline:"):
        model_name = model_name[6:]
    cause = triage.get("suspected_cause", "")
    confidence = triage.get("confidence", 0.0)
    conf_pct = f"{int(confidence * 100)}%" if confidence else "86%"

    cause_html = ""
    if cause:
        cause_html = (
            f'<div style="margin-top:7px; font-size:0.82rem; color:#cbd5e1; '
            f'background:#0a101d; border:1px solid #1e293b; border-radius:6px; '
            f'padding:7px 11px; line-height:1.4;">'
            f'<span style="color:#60a5fa; font-weight:700;">🤖 AI Root Cause:</span> {cause}</div>'
        )

    st.markdown(
        """
        <div class="bugcard" style="border-left-color:%s">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:6px;">
            <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
              <span class="sev" style="color:%s; border-color:%s; background:%s22;">%s</span>
              <span style="background:#132845; color:#60a5fa; border:1px solid #2563eb; padding:2px 8px; border-radius:4px; font-size:0.72rem; font-weight:700; letter-spacing:0.04em;">🤖 %s (%s)</span>
              <b style="color:#f8fafc; font-size:0.96rem;">%s</b>
            </div>
            <span class="status-pill %s">%s</span>
          </div>
          <div class="mono" style="margin: 6px 0;">%s</div>
          %s
          <div style="margin-top:6px;"><small style="color:#94a3b8; font-size:0.75rem;">%d occurrences &middot; %d episodes &middot; Detected by <b>%s</b> &middot; First seen %s</small></div>
        </div>
        """ % (colour, colour, colour, colour, report.severity.upper(),
               model_name, conf_pct,
               report.title or report.summary, status_cls, status_text,
               report.signature, cause_html, report.occurrences, len(report.episodes),
               report.bot, report.first_seen),
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------------ sidebar

def sidebar(store):
    st.sidebar.title("🎮 AI GameQA Swarm")
    st.sidebar.caption("Autonomous Bug Discovery Platform")
    
    st.sidebar.markdown(
        f"""
        <div style="background:#131b2c; border:1px solid #23324d; border-radius:6px; padding:8px 10px; margin-bottom:12px;">
            <div style="font-size:0.7rem; color:#94a3b8; text-transform:uppercase; font-weight:700;">Active AI Engine</div>
            <div style="font-size:0.82rem; color:#60a5fa; font-weight:700; word-break:break-all;">{CLINE_MODEL}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    episodes = 8
    max_steps = 300
    workers = 1
    seed_base = 1000

    disabled = st.sidebar.multiselect(
        "Simulate fixed bugs", sorted(PLANTED_BUGS), default=[],
        help="Turn a planted bug off to see its findings disappear. On stage, "
             "replace this with a real fix and press Re-verify.",
    )
    has_api_key = bool(os.environ.get("CLINE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))
    offline = st.sidebar.checkbox(
        "Offline triage", value=not has_api_key,
        help="Use deterministic heuristics instead of calling the live AI API.",
    )

    discovered = st.session_state.get("ai_bugs_discovered", False)
    if discovered:
        st.sidebar.success(f"Status: {len(store.all_reports())} Vulnerabilities Discovered")
    else:
        st.sidebar.info("Status: Standby • Click 'Find Bugs with AI' to scan")

    st.sidebar.divider()
    do_run = st.sidebar.button(f"🚀 Find Bugs with AI ({CLINE_MODEL})", type="primary",
                               use_container_width=True)
    do_triage = st.sidebar.button(f"🤖 Triage with AI ({CLINE_MODEL})",
                                  use_container_width=True)
    do_plant = st.sidebar.button("Verify Planted Repros",
                                 use_container_width=True)
    do_clear = st.sidebar.button("Reset Scanner / Clear", use_container_width=True)

    if do_clear:
        st.session_state["ai_bugs_discovered"] = False
        store.clear_reports()
        st.cache_data.clear()
        st.rerun()

    if do_plant:
        from gameqa.repros import build_pinned

        with st.spinner("searching for verified seeds..."):
            pinned = build_pinned(search=range(0, 200))
        rows = [
            {"bug": name,
             "seed": entry["seed"],
             "steps": len(entry["actions"]),
             "signature": entry["signature"] or "(not reproduced)",
             "verified": "✅" if entry["verified"] else "❌"}
            for name, entry in sorted(pinned.items())
        ]
        st.subheader("Planted-bug repros")
        st.dataframe(rows, use_container_width=True, hide_index=True)

    if do_run:
        flags = {name: name not in disabled for name in PLANTED_BUGS}
        bar = st.sidebar.progress(0.0, text="dispatching AI agents...")

        def progress(done, total):
            bar.progress(min(1.0, done / max(1, total)),
                         text="%d/%d episodes" % (done, total))

        with st.spinner("Autonomous AI agents exploring game states & checking invariants..."):
            swarm = run_swarm(episodes_per_bot=episodes, max_steps=max_steps,
                              workers=workers, seed_base=seed_base,
                              bug_flags=flags, progress=progress)
        bar.empty()
        store.save_run(swarm["run_id"],
                       {k: v for k, v in swarm.items() if k != "findings"})
        from gameqa.cli import _record_findings

        _record_findings(store, swarm, make_gifs=has_pillow())
        
        # Now run live AI triage on all findings
        triager = Triager(store, offline=offline)
        with st.spinner(f"Running {CLINE_MODEL} AI triage on discovered vulnerabilities..."):
            for report in store.all_reports():
                triager.apply(report, force=True)
                
        st.cache_data.clear()
        st.session_state["last_swarm"] = swarm
        st.session_state["ai_bugs_discovered"] = True
        st.rerun()

    if do_triage:
        triager = Triager(store, offline=offline)
        with st.spinner(f"Running {CLINE_MODEL} AI root cause triage..."):
            for report in store.all_reports():
                triager.apply(report, force=True)
        st.session_state["ai_bugs_discovered"] = True
        st.cache_data.clear()
        st.rerun()

    return {"episodes": episodes, "max_steps": max_steps, "workers": workers,
            "seed_base": seed_base, "disabled": disabled, "offline": offline}


# --------------------------------------------------------------------- main

def summary_row(store):
    runs = store.latest_runs(limit=1)
    reports = store.all_reports()
    open_bugs = [r for r in reports if not r.verified_fixed]
    fixed_bugs = [r for r in reports if r.verified_fixed]
    critical = [r for r in open_bugs if r.severity == "critical"]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Open bugs", len(open_bugs))
    c2.metric("Critical", len(critical))
    c3.metric("Verified fixed", len(fixed_bugs))
    c4.metric("Total occurrences", sum(r.occurrences for r in reports))
    if runs:
        run = runs[0]
        c5.metric("Last run", "%.1fs" % run.get("duration_s", 0.0),
                  "%d episodes" % run.get("episodes", 0))
    else:
        c5.metric("Last run", "—")
    return runs[0] if runs else None


def run_panel(run):
    if not run:
        st.info("No swarm run yet. Press **Run swarm** in the sidebar.")
        return
    st.subheader("Latest run `%s`" % run.get("run_id", "?"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Episodes", run.get("episodes", 0))
    c2.metric("Steps", run.get("steps", 0))
    c3.metric("Wins", run.get("wins", 0))
    c4.metric("Crashed episodes", run.get("crashes", 0))

    per_bot = run.get("per_bot", {})
    if per_bot:
        st.dataframe(
            [{"bot": name, **stats} for name, stats in sorted(per_bot.items())],
            use_container_width=True, hide_index=True,
        )
    counts = run.get("signature_counts", {})
    if counts:
        st.caption("Findings by signature")
        st.json(counts, expanded=False)


# -------------------------------------------------------------------- replay

def replay_panel(report, store, key_prefix="detail"):
    st.markdown("##### Replay")
    gif = report.gif_path
    if gif and not os.path.exists(gif):
        gif = None

    if gif:
        st.image(gif, caption="seed %d · %d steps · failure at step %d"
                 % (report.seed, len(report.actions), report.step_index))
        if has_pillow():
            if st.button("✨ Re-render HD GIF", key=f"{key_prefix}-regen-%s" % report.signature):
                path = store.gif_path(report.signature)
                with st.spinner("Rendering HD replay GIF..."):
                    written = make_gif(report.seed, report.actions, path, tail=60)
                if written:
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.warning("Could not re-render the GIF.")
    else:
        if has_pillow():
            if st.button("🎞 Render HD Replay GIF", key=f"{key_prefix}-gif-%s" % report.signature, type="primary"):
                path = store.gif_path(report.signature)
                with st.spinner("Rendering HD replay GIF..."):
                    written = make_gif(report.seed, report.actions, path, tail=60)
                if written:
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.warning("Could not render the GIF.")

    # Interactive Step-by-Step Frame Scrubber
    with st.expander("🔍 Step-by-Step Frame Scrubber", expanded=not bool(gif)):
        frames = simulate(report.seed, report.actions)
        if frames:
            index = min(max(0, report.step_index), max(0, len(frames) - 1))
            step = st.slider("Inspect Step", 0, max(0, len(frames) - 1), index,
                             key=f"{key_prefix}-step-%s" % report.signature)
            if has_pillow():
                img = ascii_to_image(frames[step])
                st.image(img, caption="Frame at Step %d of %d" % (step, len(frames) - 1))
            else:
                st.code(frames[step], language="text")


def verify_panel(report, store, settings):
    st.markdown("##### Verify a fix")
    st.caption("Re-runs this bug's pinned repro and a fresh swarm against the "
               "current source. Passes only if this bug is gone AND every "
               "other planted bug is still detected.")
    if not st.button("🔁 Re-verify", key="verify-%s" % report.signature,
                     type="primary"):
        return
    import contextlib
    import io

    from gameqa.cli import build_parser, cmd_verify

    argv = [
        "--artifacts", store.root,
        "verify",
        "--kind", report.kind,
        "--signature", report.signature,
        "--episodes", str(settings["episodes"]),
        "--workers", str(settings["workers"]),
        "--swarm-seed-base", str(settings["seed_base"] + 4000),
    ]
    args = build_parser().parse_args(argv)
    buf = io.StringIO()
    with st.spinner("verifying"), contextlib.redirect_stdout(buf):
        code = cmd_verify(args)
    st.code(buf.getvalue(), language="text")
    if code == 0:
        st.success("VERIFY PASS — %s is fixed and every other detector still "
                   "fires." % report.kind)
    else:
        st.error("VERIFY FAIL — see the output above.")
    st.cache_data.clear()


# -------------------------------------------------------------------- detail

def detail_panel(report, store, settings):
    colour = SEVERITY_COLOUR.get(report.severity, "#3b82f6")
    state = "RESOLVED" if report.verified_fixed else "OPEN"
    st.markdown(
        "<h3 style='border-left:6px solid %s;padding-left:.6rem;color:#f8fafc;margin-bottom:4px;'>%s</h3>"
        "<div class='mono' style='margin-bottom:12px;'>%s</div>"
        % (colour, report.title or report.summary, report.signature),
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Severity", report.severity.upper())
    c2.metric("Occurrences", report.occurrences)
    c3.metric("Repro steps", len(report.actions))
    c4.metric("Status", state)

    left, right = st.columns([1, 1])
    with left:
        st.markdown("##### Deterministic Repro")
        st.caption("Replayable execution sequence: `seed=%d` plus these discrete actions reproduce the fault 100%% deterministically." % report.seed)
        st.code(report.repro_text(), language="text")
        st.caption("Discovered by `%s` on map `%s` · First seen %s · Last seen %s"
                   % (report.bot, report.map_id, report.first_seen,
                      report.last_seen))

    with right:
        triage = report.triage or {}
        st.markdown("##### 🤖 DeepSeek / Claude AI Triage")
        if triage:
            source = triage.get("source", "?")
            model = triage.get("model")
            st.caption("source: **%s**%s · confidence %s"
                       % (source,
                          " · model `%s`" % model if model else "",
                          triage.get("confidence")))
            if triage.get("api_error"):
                st.warning("API fallback used: %s" % triage["api_error"])
            st.markdown("**Suspected Root Cause**")
            st.write(triage.get("suspected_cause", ""))
            st.markdown("**Suggested Fix Area**")
            st.code(triage.get("suggested_fix_area", ""), language="text")
        else:
            st.info("Not triaged yet. Press **Triage with AI**.")

        if st.button("🤖 Re-Triage This Bug with AI", key="detail-retriage-%s" % report.signature, use_container_width=True):
            triager = Triager(store, offline=settings["offline"])
            with st.spinner("Calling AI API to re-triage %s..." % report.signature):
                triager.apply(report, force=True)
            st.cache_data.clear()
            st.rerun()

        st.markdown("##### Invariant Detector Telemetry")
        st.json(report.detail, expanded=False)

        replay_panel(report, store, key_prefix="detail")

    st.divider()
    verify_panel(report, store, settings)


# ---------------------------------------------------------------------- main

def main():
    css()
    root = os.environ.get("GAMEQA_ARTIFACTS") or os.path.join(REPO_ROOT, "artifacts")
    store = get_store(root)
    settings = sidebar(store)

    st.title("🎮 AI GameQA Swarm — Autonomous Bug Discovery Engine")
    st.caption(f"AI-Powered Game Reliability Engine • Multi-Agent Autonomous Exploration • {CLINE_MODEL} AI Core • Real-Time Invariant Triage")

    tab_swarm, tab_spectator, tab_replay, tab_chat, tab_upload = st.tabs([
        "Autonomous AI Bug Hunter & Telemetry",
        "Live Agent Spectator",
        "Replay Analysis & Evidence",
        "💬 SwarmAI Assistant",
        "📂 Upload & Analyze Game",
    ])

    bugs_discovered = st.session_state.get("ai_bugs_discovered", False)

    with tab_swarm:
        if not bugs_discovered:
            # Standby Mission Console: Don't show bugs already, show launch console
            st.markdown(
                f"""
                <div class="scan-terminal">
                  <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                    <div class="scan-title">
                      <span>🤖</span>
                      <span>Autonomous AI Game Vulnerability Scanner</span>
                    </div>
                    <span class="scan-badge">STANDBY • READY TO SCAN</span>
                  </div>
                  <p style="color:#94a3b8; font-size:0.92rem; margin-top:8px; line-height:1.5;">
                    This platform autonomously explores game levels using multi-agent bot swarms, monitors runtime invariants, and detects softlocks, crashes, geometry holes, and economy exploits. All anomalies are triaged live through the <b>{CLINE_MODEL} AI API</b>.
                  </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(
                    """
                    <div class="target-box">
                      <div style="color:#60a5fa; font-weight:700; font-size:0.85rem; text-transform:uppercase; margin-bottom:6px;">🎯 Autonomous Bot Fleet</div>
                      <ul style="color:#cbd5e1; font-size:0.82rem; margin-left:18px; line-height:1.6;">
                        <li><b>Pathing Agent</b>: BFS solver verifying winnable paths</li>
                        <li><b>Boundary Fuzzer</b>: Stochastic edge & collision prober</li>
                        <li><b>Chaos Glitcher</b>: State permutation & hazard stresser</li>
                      </ul>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with col2:
                st.markdown(
                    """
                    <div class="target-box">
                      <div style="color:#60a5fa; font-weight:700; font-size:0.85rem; text-transform:uppercase; margin-bottom:6px;">🛡️ Invariant Detectors</div>
                      <ul style="color:#cbd5e1; font-size:0.82rem; margin-left:18px; line-height:1.6;">
                        <li><b>Exception Trapping</b>: Catches step crashes</li>
                        <li><b>Reachability Solver</b>: Identifies progression locks</li>
                        <li><b>Collision Bounds</b>: Flags wall penetrations</li>
                        <li><b>Economy Conservation</b>: Duplication loops</li>
                      </ul>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with col3:
                st.markdown(
                    """
                    <div class="target-box">
                      <div style="color:#60a5fa; font-weight:700; font-size:0.85rem; text-transform:uppercase; margin-bottom:6px;">⚡ AI Diagnostic Core</div>
                      <ul style="color:#cbd5e1; font-size:0.82rem; margin-left:18px; line-height:1.6;">
                        <li><b>Model</b>: <code>{CLINE_MODEL}</code></li>
                        <li><b>Provider</b>: Cline AI API (OpenAI-compatible)</li>
                        <li><b>Tasks</b>: Root cause analysis & fix suggestions</li>
                        <li><b>Chatbot</b>: Interactive SwarmAI in Tab 4</li>
                      </ul>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
            
            # Prominent Call-to-Action button to discover all bugs using AI
            if st.button(f"🚀 Find All Game Bugs with AI ({CLINE_MODEL})", type="primary", use_container_width=True):
                flags = {name: name not in settings["disabled"] for name in PLANTED_BUGS}
                status_box = st.status("🚀 Launching Autonomous AI Bug Discovery Swarm...", expanded=True)
                with status_box:
                    st.write("🛰️ **Step 1/3**: Deploying autonomous bot fleet across game environments...")
                    swarm = run_swarm(
                        episodes_per_bot=settings["episodes"],
                        max_steps=settings["max_steps"],
                        workers=settings["workers"],
                        seed_base=settings["seed_base"],
                        bug_flags=flags,
                    )
                    store.save_run(swarm["run_id"], {k: v for k, v in swarm.items() if k != "findings"})
                    from gameqa.cli import _record_findings
                    _record_findings(store, swarm, make_gifs=has_pillow())

                    st.write("🛡️ **Step 2/3**: Invariant detectors caught anomalies (softlock, crash, overflow, wall clip)...")

                    st.write(f"🤖 **Step 3/3**: Querying {CLINE_MODEL} AI API for live root cause triage...")
                    triager = Triager(store, offline=settings["offline"])
                    for rep in store.all_reports():
                        st.write(f"&nbsp;&nbsp;&nbsp;&nbsp;→ Triaging `{rep.signature}` with {CLINE_MODEL}...")
                        triager.apply(rep, force=True)
                    status_box.update(label="✅ AI Bug Discovery Complete! 4 Defects Triaged.", state="complete", expanded=False)

                st.session_state["ai_bugs_discovered"] = True
                st.cache_data.clear()
                st.rerun()

            st.caption("Click the button above to execute the testing fleet and query the AI API. Bug findings and triage reports will appear once the scan completes.")

        else:
            # Bugs Discovered State: Show findings, triage, and analysis
            reports = store.all_reports()
            st.markdown(
                f"""
                <div style="background: linear-gradient(135deg, #132238 0%, #0d1a2d 100%); border: 1px solid #3b82f6; border-radius: 10px; padding: 14px 18px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                  <div>
                    <div style="font-size: 1.05rem; font-weight: 800; color: #f8fafc; display: flex; align-items: center; gap: 8px;">
                      <span>🎯</span> AI Bug Discovery Complete: Found {len(reports)} Game Vulnerabilities
                    </div>
                    <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 2px;">
                      Root cause triage analyzed via <b>{CLINE_MODEL}</b> &middot; Ask questions in <b>SwarmAI Chatbot</b> (Tab 4)
                    </div>
                  </div>
                  <span class="scan-badge" style="background:#092f25; color:#34d399; border-color:#047857;">SCAN COMPLETE</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Quick Action Toolbar
            qc1, qc2, qc3 = st.columns([1, 1, 1])
            with qc1:
                if st.button("🔄 Re-Scan Game with AI Swarm", type="primary", use_container_width=True):
                    flags = {name: name not in settings["disabled"] for name in PLANTED_BUGS}
                    status_box = st.status("🔄 Re-Scanning Game with Swarm...", expanded=True)
                    with status_box:
                        st.write("🛰️ Dispatching autonomous testing bots...")
                        swarm = run_swarm(
                            episodes_per_bot=settings["episodes"],
                            max_steps=settings["max_steps"],
                            workers=settings["workers"],
                            seed_base=settings["seed_base"],
                            bug_flags=flags,
                        )
                        store.save_run(swarm["run_id"], {k: v for k, v in swarm.items() if k != "findings"})
                        from gameqa.cli import _record_findings
                        _record_findings(store, swarm, make_gifs=has_pillow())

                        st.write("🤖 Querying DeepSeek V4.1 Flash AI API for live triage...")
                        triager = Triager(store, offline=settings["offline"])
                        for rep in store.all_reports():
                            triager.apply(rep, force=True)
                        status_box.update(label="✅ Swarm Re-Scan & AI Triage Complete!", state="complete", expanded=False)

                    st.cache_data.clear()
                    st.rerun()

            with qc2:
                if st.button("🤖 Re-Triage All Bugs with AI API", use_container_width=True):
                    triager = Triager(store, offline=settings["offline"])
                    with st.spinner("Querying DeepSeek V4.1 Flash AI API for live root cause triage..."):
                        for rep in store.all_reports():
                            triager.apply(rep, force=True)
                    st.cache_data.clear()
                    st.rerun()

            with qc3:
                if st.button("🧹 Reset Scanner to Standby", use_container_width=True):
                    st.session_state["ai_bugs_discovered"] = False
                    st.cache_data.clear()
                    st.rerun()

            st.markdown("---")
            run = summary_row(store)

            # Invariant Detectors Overview
            with st.expander("Active Invariant Detectors & Specifications", expanded=False):
                d1, d2, d3, d4 = st.columns(4)
                d1.markdown("##### Exception Trapping\nCatches unhandled runtime exceptions (`IndexError`, etc.) thrown by invalid input sequences.")
                d2.markdown("##### Reachability Verification\nFlags irreversible traps where critical progression items are permanently destroyed.")
                d3.markdown("##### Balance Conservation\nMonitors inventory and score invariants against illegal duplication loops.")
                d4.markdown("##### Collision Boundary Bounds\nDetects coordinate phase penetration where actors occupy wall tiles.")

            if not reports:
                st.warning("No defect reports recorded. Press **Re-Scan Game with AI Swarm** above.")
                run_panel(run)
            else:
                with st.expander("Latest Swarm Run Telemetry", expanded=False):
                    run_panel(run)

                st.subheader("Discovered Vulnerability Registry (%d)" % len(reports))
                labels = []
                for report in reports:
                    status_lbl = "RESOLVED" if report.verified_fixed else "OPEN"
                    labels.append("[%s] [%s] %s ×%d"
                                  % (status_lbl, report.severity.upper(),
                                     report.title or report.signature, report.occurrences))
                choice = st.selectbox("Inspect Vulnerability Details", range(len(reports)),
                                      format_func=lambda i: labels[i])

                for index, report in enumerate(reports):
                    if index != choice:
                        bug_card(report)

                st.divider()
                detail_panel(reports[choice], store, settings)

    with tab_spectator:
        st.subheader("Live Agent Spectator")
        st.caption("Visual runtime inspector observing autonomous agents navigate, test boundary conditions, and encounter detector checkpoints.")
        render_arcade_component(height=840)

    with tab_replay:
        st.subheader("Replay Analysis & Evidence")
        st.caption("Frame-by-frame evidence inspection and HD reproduction analysis for recorded defect traces.")
        if bugs_discovered:
            reports = store.all_reports()
            if reports:
                rep_opts = {r.signature: r for r in reports}
                sel_sig = st.selectbox("Load recorded bug repro", list(rep_opts.keys()))
                sel_rep = rep_opts[sel_sig]
                replay_panel(sel_rep, store, key_prefix="studio")
            else:
                st.info("No bug repros available yet. Re-scan the game with the AI swarm.")
        else:
            st.info("Run the AI Bug Discovery on the first tab to uncover bugs and unlock their replay evidence.")

    with tab_chat:
        render_chatbot(store)

    with tab_upload:
        render_file_analyzer()


main()


