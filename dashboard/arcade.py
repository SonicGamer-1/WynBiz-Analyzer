"""Interactive production-level game arcade embedded component.

Features:
- 60 FPS HTML5 Canvas engine with smooth movement interpolation and lighting
- Web Audio API real-time retro synthesizer (footsteps, coins, keys, doors, fanfare, chiptune ambient arpeggio)
- Dynamic particle systems (coin sparks, key bursts, stone dust, confetti, floating text, screen shake)
- Interactive Player Campaign (WASD / Arrows / Virtual touch gamepad)
- Live AI Swarm Bot Spectator mode (Goal Seeker BFS, Random Walker, Chaos Tester) with path breadcrumbs & thought bubbles
- Glitch Hunter / Bug Discovery HUD tracking the 4 famous vulnerabilities with achievement popups
- 3 Campaign Levels & 3 Visual Themes (Dark Dungeon, Cyberpunk Neon, GameBoy Retro)
- Star rating and high-score evaluation
"""
from __future__ import annotations

import importlib
import json
import streamlit as st
import streamlit.components.v1 as components

from gameqa.game import maps
if not hasattr(maps, "CAMPAIGN_LEVELS"):
    importlib.reload(maps)


def render_arcade_component(height: int = 860):
    """Renders the self-contained production game arcade inside Streamlit."""
    if not hasattr(maps, "CAMPAIGN_LEVELS"):
        importlib.reload(maps)

    if hasattr(maps, "CAMPAIGN_LEVELS"):
        levels_data = maps.CAMPAIGN_LEVELS
    elif hasattr(maps, "get_level"):
        levels_data = {
            "level_01": maps.get_level("level_01"),
            "level_02": maps.get_level("level_02"),
            "level_03": maps.get_level("level_03"),
        }
    else:
        levels_data = {
            "level_01": {
                "id": "level_01",
                "name": "The Forgotten Crypt",
                "theme": "dungeon",
                "raw": getattr(maps, "MAP_RAW", []),
                "par_steps": 28,
                "enemy_paths": [[(5, 7), (6, 7), (7, 7), (8, 7)]],
            }
        }
    levels_json = json.dumps(levels_data)

    html_code = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Game QA Swarm Arcade</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; user-select: none; -webkit-user-select: none; }}
  html {{
    background: #0b0f19;
    color: #f1f5f9;
  }}
  body {{
    background: #0b0f19;
    color: #f1f5f9;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
    padding: 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    overflow-x: hidden;
  }}

  /* Top Bar */
  .arcade-header {{
    width: 100%;
    max-width: 900px;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    background: #131b2c;
    border: 1px solid #23324d;
    border-radius: 12px;
    padding: 10px 16px;
    margin-bottom: 12px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  }}
  .brand {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 800;
    font-size: 0.95rem;
    letter-spacing: 0.04em;
    background: linear-gradient(135deg, #60a5fa, #818cf8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .controls-bar {{
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }}
  select, button.bar-btn {{
    background: #1c283f;
    color: #e2e8f0;
    border: 1px solid #2e4368;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
    outline: none;
  }}
  select:hover, button.bar-btn:hover {{
    background: #253655;
    border-color: #3b82f6;
    color: #ffffff;
  }}
  button.bar-btn.active {{
    background: #2563eb;
    color: #fff;
    border-color: #3b82f6;
    box-shadow: 0 2px 10px rgba(37, 99, 235, 0.4);
  }}

  /* Main Stage Layout */
  .stage-container {{
    width: 100%;
    max-width: 900px;
    display: grid;
    grid-template-columns: 1fr 280px;
    gap: 14px;
  }}
  @media (max-width: 820px) {{
    .stage-container {{ grid-template-columns: 1fr; }}
  }}

  /* Canvas Box */
  .canvas-wrapper {{
    position: relative;
    background: #0d121e;
    border: 2px solid #23324d;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
    display: flex;
    flex-direction: column;
    align-items: center;
  }}
  canvas#gameCanvas {{
    display: block;
    width: 100%;
    max-width: 576px;
    height: auto;
    image-rendering: pixelated;
    background: #0d121e;
  }}

  /* Thought bubble / Bot banner */
  .bot-hud {{
    position: absolute;
    top: 8px;
    left: 8px;
    right: 8px;
    background: rgba(19, 27, 44, 0.95);
    border: 1px solid #3b82f6;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 0.78rem;
    color: #e2e8f0;
    display: none;
    align-items: center;
    gap: 6px;
    z-index: 10;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
  }}
  .bot-hud.visible {{ display: flex; }}

  /* Achievement Notification */
  .glitch-toast {{
    position: absolute;
    bottom: 12px;
    left: 12px;
    right: 12px;
    background: linear-gradient(135deg, #1e293b, #0f172a);
    border: 1px solid #3b82f6;
    border-radius: 8px;
    padding: 8px 12px;
    color: #fff;
    display: none;
    align-items: center;
    justify-content: space-between;
    z-index: 20;
    animation: toastPop 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.5);
  }}
  @keyframes toastPop {{
    from {{ transform: translateY(20px); opacity: 0; }}
    to {{ transform: translateY(0); opacity: 1; }}
  }}

  /* Sidebar Panels */
  .sidebar-panel {{
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}
  .panel-card {{
    background: #131b2c;
    border: 1px solid #23324d;
    border-radius: 10px;
    padding: 12px 14px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  }}
  .panel-title {{
    font-size: 0.75rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #93c5fd;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}

  /* Status Stats */
  .stats-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }}
  .stat-box {{
    background: #0d1424;
    border: 1px solid #1f2c45;
    border-radius: 6px;
    padding: 8px;
    text-align: center;
  }}
  .stat-val {{
    font-size: 1.15rem;
    font-weight: 800;
    color: #f1f5f9;
  }}
  .stat-lbl {{
    font-size: 0.68rem;
    color: #94a3b8;
    text-transform: uppercase;
  }}

  /* Glitch checklist */
  .glitch-item {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 8px;
    margin-bottom: 4px;
    border-radius: 6px;
    background: #0d1424;
    border: 1px solid #1f2c45;
    font-size: 0.74rem;
    color: #cbd5e1;
    transition: all 0.2s;
  }}
  .glitch-item.unlocked {{
    background: #0c2820;
    border-color: #10b981;
    color: #6ee7b7;
  }}
  .glitch-badge {{
    font-size: 0.65rem;
    padding: 2px 6px;
    border-radius: 4px;
    background: #1e293b;
    color: #94a3b8;
    font-weight: 700;
  }}
  .glitch-item.unlocked .glitch-badge {{
    background: #10b981;
    color: #fff;
  }}

  /* Virtual Gamepad */
  .gamepad {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    grid-template-rows: repeat(3, 38px);
    gap: 4px;
    max-width: 140px;
    margin: 4px auto;
  }}
  .pad-btn {{
    background: #1c283f;
    color: #e2e8f0;
    border: 1px solid #2e4368;
    border-radius: 6px;
    font-weight: 700;
    font-size: 0.85rem;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    touch-action: manipulation;
  }}
  .pad-btn:active {{
    background: #2563eb;
    color: #ffffff;
    transform: scale(0.94);
  }}
  .action-row {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 4px;
    margin-top: 6px;
  }}
  .act-btn {{
    background: #1c283f;
    color: #e2e8f0;
    border: 1px solid #2e4368;
    border-radius: 6px;
    padding: 6px 0;
    font-size: 0.72rem;
    font-weight: 700;
    cursor: pointer;
    text-align: center;
  }}
  .act-btn:active {{
    background: #2563eb;
    color: #fff;
  }}

  /* Victory modal overlay */
  .victory-modal {{
    position: absolute;
    inset: 0;
    background: rgba(15, 43, 92, 0.92);
    backdrop-filter: blur(8px);
    display: none;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 24px;
    text-align: center;
    z-index: 30;
    color: #ffffff;
  }}
  .victory-modal.show {{ display: flex; }}
  .stars {{ font-size: 2.2rem; color: #fbbf24; margin: 8px 0; }}
  .vic-btn {{
    margin-top: 14px;
    background: linear-gradient(135deg, #10b981, #059669);
    color: #fff;
    border: none;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 0.95rem;
    font-weight: 700;
    cursor: pointer;
    box-shadow: 0 4px 14px rgba(16, 185, 129, 0.4);
  }}

  /* Game Over modal overlay */
  .game-over-modal {{
    position: absolute;
    inset: 0;
    background: rgba(18, 5, 8, 0.95);
    backdrop-filter: blur(10px);
    display: none;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 24px;
    text-align: center;
    z-index: 30;
    animation: deathFadeIn 0.4s ease-out;
  }}
  .game-over-modal.show {{ display: flex; }}
  @keyframes deathFadeIn {{
    from {{ opacity: 0; transform: scale(0.92); }}
    to {{ opacity: 1; transform: scale(1.0); }}
  }}
</style>
</head>
<body>

<div class="arcade-header">
  <div class="brand">
    <span>🤖</span>
    <span>GAME ENVIRONMENT INSPECTOR · LIVE AI BOT SPECTATOR</span>
  </div>
  <div class="controls-bar">
    <select id="levelSelect" onchange="changeLevel(this.value)">
      <option value="level_01">Level 1: The Crypt (4 Planted Bugs)</option>
      <option value="level_02">Level 2: Inferno Bastion</option>
      <option value="level_03">Level 3: Cyber Void Citadel</option>
    </select>
    <select id="themeSelect" onchange="changeTheme(this.value)">
      <option value="dungeon">🏰 Dungeon Theme</option>
      <option value="cyber">⚡ Cyber Neon</option>
      <option value="gameboy">👾 Retro GameBoy</option>
    </select>
    <button class="bar-btn" id="soundBtn" onclick="toggleSound()">🔊 Audio ON</button>
    <button class="bar-btn" id="resetBtn" onclick="resetGame()">🔄 Reset Environment</button>
  </div>
</div>

<div class="stage-container">
  <!-- Game Canvas Stage -->
  <div class="canvas-wrapper">
    <div class="bot-hud" id="botHud">
      <span id="botIcon">🤖</span>
      <span id="botText">Bot idle...</span>
    </div>

    <canvas id="gameCanvas" width="576" height="480"></canvas>

    <div class="glitch-toast" id="glitchToast">
      <div>
        <b id="glitchToastTitle">🚨 DETECTOR TRIGGERED BY BOT!</b><br/>
        <small id="glitchToastDesc">Automated detector caught an engine invariant violation</small>
      </div>
      <button class="bar-btn" style="background:#2563eb; color:#ffffff; border:1px solid #3b82f6; padding:4px 10px; border-radius:6px; cursor:pointer;" onclick="closeToast()">OK</button>
    </div>

    <div class="victory-modal" id="victoryModal">
      <h2 style="font-size:1.8rem; color:#34d399;">🏆 LEVEL CLEARED BY BOT!</h2>
      <div class="stars" id="vicStars">⭐⭐⭐</div>
      <p style="color:#94a3b8; font-size:0.9rem;" id="vicSummary">Escaped in 24 steps with 160 score!</p>
      <button class="vic-btn" onclick="nextLevelOrRestart()">Next Level ➔</button>
    </div>

    <div class="game-over-modal" id="gameOverModal">
      <div style="font-size:3.5rem; margin-bottom:4px; filter: drop-shadow(0 0 16px rgba(239,68,68,0.8));">💀</div>
      <h2 style="font-size:2.2rem; color:#ef4444; font-weight:900; letter-spacing:0.08em; text-shadow: 0 0 20px rgba(220,38,38,0.7);">BOT TERMINATED</h2>
      <p style="color:#fca5a5; font-weight:700; margin:8px 0; font-size:1.05rem;" id="gameOverSource">Slain by Shadow Fiend</p>
      <p style="color:#94a3b8; font-size:0.9rem;" id="gameOverSummary">Score: 0 · Coins: 0 / 6</p>
      <button class="vic-btn" style="background:linear-gradient(135deg, #dc2626, #991b1b); box-shadow: 0 4px 18px rgba(220,38,38,0.5); margin-top:16px;" onclick="resetGame()">🔄 Reset Environment</button>
    </div>
  </div>

  <!-- Sidebar Controls & Automated Detectors -->
  <div class="sidebar-panel">
    <!-- Live HUD Status -->
    <div class="panel-card">
      <div class="panel-title">
        <span>Engine Telemetry</span>
        <span id="heartsSpan">❤️❤️❤️</span>
      </div>
      <div class="stats-grid">
        <div class="stat-box">
          <div class="stat-val" id="scoreVal" style="color:#f59e0b;">0</div>
          <div class="stat-lbl">Score</div>
        </div>
        <div class="stat-box">
          <div class="stat-val" id="stepsVal">0 / 28</div>
          <div class="stat-lbl">Steps / Par</div>
        </div>
        <div class="stat-box">
          <div class="stat-val" id="coinsVal" style="color:#fbbf24;">0 / 6</div>
          <div class="stat-lbl">Coins</div>
        </div>
        <div class="stat-box">
          <div class="stat-val" id="keyVal" style="color:#a78bfa;">NO</div>
          <div class="stat-lbl">Key Held</div>
        </div>
      </div>
    </div>

    <!-- Mode Selector & AI Bot Spectator -->
    <div class="panel-card">
      <div class="panel-title">
        <span>Autonomous Bot Control</span>
        <span id="modeBadge" style="color:#a855f7;">AI BOT</span>
      </div>
      <div style="display:flex; gap:6px; margin-bottom:8px;">
        <button class="bar-btn active" id="modeBotBtn" style="flex:1;" onclick="setMode('bot')">🤖 AI Bot</button>
        <button class="bar-btn" id="modeHumanBtn" style="flex:1;" onclick="setMode('human')">👤 Manual</button>
      </div>
      <div id="botControls" style="display:flex; flex-direction:column; gap:6px;">
        <select id="botTypeSelect" style="width:100%;">
          <option value="goal_seeker">🎯 Goal Seeker (BFS Route Agent)</option>
          <option value="random_walker">🎲 Random Walker (Exploration Agent)</option>
          <option value="chaos_tester">🌀 Chaos Tester (Glitcher Agent)</option>
        </select>
        <div style="display:flex; gap:6px; align-items:center;">
          <button class="bar-btn" id="botPlayBtn" style="flex:1; background:#059669; color:#fff;" onclick="toggleBotPlay()">▶ Start Bot</button>
          <button class="bar-btn" style="flex:1;" onclick="stepBot()">Step ➔</button>
          <select id="botSpeedSelect" style="width:70px;">
            <option value="400">1x</option>
            <option value="200" selected>2x</option>
            <option value="80">5x</option>
            <option value="30">10x</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Automated QA Detectors Tracker -->
    <div class="panel-card">
      <div class="panel-title">
        <span>Active QA Detectors</span>
        <span id="glitchScore" style="color:#ec4899;">0 / 4 Caught</span>
      </div>
      <div class="glitch-item" id="glitch-map_hole">
        <div>🕳️ <b>Map Hole Detector</b> (Wall collision)</div>
        <span class="glitch-badge">MONITORING</span>
      </div>
      <div class="glitch-item" id="glitch-softlock">
        <div>💀 <b>Softlock Detector</b> (Progression loss)</div>
        <span class="glitch-badge">MONITORING</span>
      </div>
      <div class="glitch-item" id="glitch-exploit">
        <div>💰 <b>Exploit Detector</b> (Coin balance)</div>
        <span class="glitch-badge">MONITORING</span>
      </div>
      <div class="glitch-item" id="glitch-crash">
        <div>💥 <b>Crash Detector</b> (Unhandled exception)</div>
        <span class="glitch-badge">MONITORING</span>
      </div>
    </div>

    <!-- Virtual Gamepad (Manual override) -->
    <div class="panel-card">
      <div class="panel-title">Manual Override Controls</div>
      <div class="gamepad">
        <div></div>
        <button class="pad-btn" onclick="handleAction('UP')">▲</button>
        <div></div>
        <button class="pad-btn" onclick="handleAction('LEFT')">◀</button>
        <button class="pad-btn" style="background:#2e384d;" onclick="handleAction('PICKUP')">⬬</button>
        <button class="pad-btn" onclick="handleAction('RIGHT')">▶</button>
        <div></div>
        <button class="pad-btn" onclick="handleAction('DOWN')">▼</button>
        <div></div>
      </div>
      <div class="action-row">
        <button class="act-btn" onclick="handleAction('PICKUP')">Grab [E]</button>
        <button class="act-btn" onclick="handleAction('USE')">Use [F]</button>
        <button class="act-btn" onclick="handleAction('DROP')">Drop [X]</button>
      </div>
    </div>
  </div>
</div>

<script>
// Campaign Levels Definition from Python maps.py
const LEVELS = {levels_json};

let currentLevelId = "level_01";
let theme = "dungeon";
let soundEnabled = true;
let musicEnabled = false;
let audioCtx = null;
let musicTimer = null;

// Game State
let state = {{}};
let playerVisual = {{ x: 1, y: 1, targetX: 1, targetY: 1, lerp: 1.0 }};
let enemiesVisual = [];
let particles = [];
let floatingTexts = [];
let screenShake = 0;
let actionHistory = [];

// AI Bot Mode State
let currentMode = "bot"; // "bot" | "human"
let botRunning = false;
let botTimer = null;
let botBreadcrumbPath = [];

// Glitches Tracker
let unlockedGlitches = {{
  "map_hole": false,
  "softlock": false,
  "exploit": false,
  "crash": false
}};

// Audio Engine (Web Audio API Synthesizer)
function getAudioContext() {{
  if (!audioCtx) {{
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    audioCtx = new AudioContext();
  }}
  if (audioCtx.state === "suspended") {{
    audioCtx.resume();
  }}
  return audioCtx;
}}

function playSynthTone(freq, type, duration, endFreq = null, gainVal = 0.15) {{
  if (!soundEnabled) return;
  try {{
    const ctx = getAudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, ctx.currentTime);
    if (endFreq !== null) {{
      osc.frequency.exponentialRampToValueAtTime(Math.max(20, endFreq), ctx.currentTime + duration);
    }}
    gain.gain.setValueAtTime(gainVal, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + duration);
  }} catch (e) {{}}
}}

function sfx(name) {{
  if (!soundEnabled) return;
  switch (name) {{
    case "step":
      playSynthTone(120, "triangle", 0.04, 60, 0.04);
      break;
    case "coin":
      playSynthTone(587, "sine", 0.08, 880, 0.2);
      setTimeout(() => playSynthTone(880, "sine", 0.12, 1174, 0.2), 60);
      break;
    case "key":
      playSynthTone(523, "triangle", 0.1, 659, 0.25);
      setTimeout(() => playSynthTone(784, "sine", 0.15, 1046, 0.25), 90);
      break;
    case "door":
      playSynthTone(140, "sawtooth", 0.25, 40, 0.3);
      break;
    case "win":
      [523, 659, 784, 1046].forEach((f, i) => {{
        setTimeout(() => playSynthTone(f, "triangle", 0.25, f * 1.05, 0.25), i * 110);
      }});
      break;
    case "glitch":
      playSynthTone(800, "sawtooth", 0.2, 90, 0.35);
      break;
    case "bump":
      // Bump feature removed
      break;
    case "damage":
      playSynthTone(180, "sawtooth", 0.16, 50, 0.35);
      break;
    case "death":
      [320, 240, 180, 100].forEach((f, i) => {{
        setTimeout(() => playSynthTone(f, "sawtooth", 0.25, f * 0.7, 0.35), i * 130);
      }});
      break;
  }}
}}

// Ambient Chiptune Synth Music
const CHIPTUNE_NOTES = [220, 261, 329, 392, 440, 523, 659, 784];
let noteIdx = 0;
function playMusicStep() {{
  if (!musicEnabled || !soundEnabled) return;
  const f = CHIPTUNE_NOTES[noteIdx % CHIPTUNE_NOTES.length];
  noteIdx++;
  playSynthTone(f, "sine", 0.15, f * 0.98, 0.02);
}}

function toggleSound() {{
  soundEnabled = !soundEnabled;
  document.getElementById("soundBtn").innerText = soundEnabled ? "🔊 Audio ON" : "🔇 Audio OFF";
  document.getElementById("soundBtn").classList.toggle("active", soundEnabled);
}}

function toggleMusic() {{
  musicEnabled = !musicEnabled;
  document.getElementById("musicBtn").innerText = musicEnabled ? "🎵 Music ON" : "🎵 Music OFF";
  document.getElementById("musicBtn").classList.toggle("active", musicEnabled);
  if (musicEnabled) {{
    if (!musicTimer) musicTimer = setInterval(playMusicStep, 240);
  }} else {{
    if (musicTimer) {{ clearInterval(musicTimer); musicTimer = null; }}
  }}
}}

// Game Engine Initialization
function initGame(levelId) {{
  currentLevelId = levelId;
  const level = LEVELS[levelId] || LEVELS["level_01"];
  const raw = level.raw;
  const height = raw.length;
  const width = raw[0].length;

  let start = [1, 1];
  let key = null;
  let door = null;
  let goal = null;
  let coins = [];

  for (let y = 0; y < height; y++) {{
    for (let x = 0; x < width; x++) {{
      const ch = raw[y][x];
      if (ch === "P") start = [x, y];
      else if (ch === "K") key = [x, y];
      else if (ch === "D") door = [x, y];
      else if (ch === "G") goal = [x, y];
      else if (ch === "C") coins.push({{ id: coins.length, x, y, taken: false }});
    }}
  }}

  // Build walkable set
  const walkable = new Set();
  for (let y = 0; y < height; y++) {{
    for (let x = 0; x < width; x++) {{
      const ch = raw[y][x];
      if (ch !== "#") {{
        walkable.add(`${{x}},${{y}}`);
      }}
    }}
  }}
  // Planted Map Hole Bug in level_01:
  if (levelId === "level_01") {{
    walkable.add("4,7"); // Player can walk through the wall pillar!
  }}

  // Enemies
  const paths = level.enemy_paths || [[ [5,7], [6,7], [7,7], [8,7] ]];
  const enemies = [];
  paths.forEach((p, idx) => {{
    enemies.push({{
      path: p,
      idx: 0,
      dir: idx % 2 === 0 ? 1 : -1
    }});
  }});

  state = {{
    levelId,
    level,
    width,
    height,
    raw,
    walkable,
    pos: [...start],
    inventory: [],
    keyPos: key,
    keyDestroyed: false,
    doorPos: door,
    doorOpen: false,
    goalPos: goal,
    coins,
    enemies,
    score: 0,
    steps: 0,
    combo: 0,
    won: false,
    done: false,
    holdingKeyFlag: false, // for crash bug simulation
    paidFor: new Set(),    // for exploit bug simulation
    health: 3,
    maxHealth: 3,
    invulnerableTimer: 0,
    damageFlash: 0.0,
  }};

  playerVisual = {{ x: start[0], y: start[1], targetX: start[0], targetY: start[1], lerp: 1.0 }};
  enemiesVisual = state.enemies.map(e => {{
    const pt = e.path[e.idx];
    return {{ x: pt[0], y: pt[1], targetX: pt[0], targetY: pt[1], lerp: 1.0 }};
  }});

  particles = [];
  floatingTexts = [];
  actionHistory = [];
  botBreadcrumbPath = [];
  updateHUD();
  document.getElementById("victoryModal").classList.remove("show");
  document.getElementById("gameOverModal").classList.remove("show");
}}

function updateHUD() {{
  document.getElementById("scoreVal").innerText = state.score;
  const par = state.level.par_steps || 28;
  document.getElementById("stepsVal").innerText = `${{state.steps}} / ${{par}}`;
  const taken = state.coins.filter(c => c.taken).length;
  document.getElementById("coinsVal").innerText = `${{taken}} / ${{state.coins.length}}`;
  const hasKey = state.inventory.includes("key");
  document.getElementById("keyVal").innerText = hasKey ? "HELD 🗝️" : (state.keyDestroyed ? "LOST 💀" : "NO");
  document.getElementById("keyVal").style.color = hasKey ? "#34d399" : (state.keyDestroyed ? "#ef4444" : "#a78bfa");

  const currentHealth = Math.max(0, state.health || 0);
  const heartsStr = "❤️".repeat(currentHealth) + "🖤".repeat(Math.max(0, 3 - currentHealth));
  document.getElementById("heartsSpan").innerText = currentHealth > 0 ? heartsStr : "💀 DEAD";

  let glitchCount = Object.values(unlockedGlitches).filter(Boolean).length;
  document.getElementById("glitchScore").innerText = `${{glitchCount}} / 4`;
}}

function takeDamage(amount, source) {{
  if (state.done || state.invulnerableTimer > 0) return;
  state.health = Math.max(0, state.health - amount);
  state.invulnerableTimer = 45; // ~0.75s i-frames
  state.damageFlash = 1.0;
  screenShake = 16;
  sfx("damage");

  const [px, py] = state.pos;
  spawnDamageSparks(px, py);
  addFloatingText(`-${{amount}} ❤️ [${{source}}]`, px, py, "#ef4444");
  updateHUD();

  if (state.health <= 0) {{
    triggerDeath(source);
  }}
}}

function triggerDeath(source) {{
  state.done = true;
  sfx("death");
  screenShake = 24;
  const [px, py] = state.pos;
  spawnDeathExplosion(px, py);
  document.getElementById("gameOverSource").innerText = `Slain by: ${{source}}`;
  document.getElementById("gameOverSummary").innerText = `Level: ${{state.level.name}} · Steps: ${{state.steps}} · Score: ${{state.score}}`;
  setTimeout(() => {{
    document.getElementById("gameOverModal").classList.add("show");
  }}, 450);
}}

// Engine Step Execution
function executeAction(act) {{
  if (state.done) return;
  actionHistory.push(act);
  state.steps++;
  let moved = false;

  const dxMap = {{ "UP": 0, "DOWN": 0, "LEFT": -1, "RIGHT": 1 }};
  const dyMap = {{ "UP": -1, "DOWN": 1, "LEFT": 0, "RIGHT": 0 }};

  if (act in dxMap) {{
    const targetX = state.pos[0] + dxMap[act];
    const targetY = state.pos[1] + dyMap[act];
    const keyStr = `${{targetX}},${{targetY}}`;

    let passable = state.walkable.has(keyStr);
    if (state.doorPos && targetX === state.doorPos[0] && targetY === state.doorPos[1] && !state.doorOpen) {{
      passable = false;
    }}
    // Enemy check
    let hitEnemy = false;
    for (const e of state.enemies) {{
      const ep = e.path[e.idx];
      if (ep[0] === targetX && ep[1] === targetY) {{
        passable = false;
        hitEnemy = true;
        break;
      }}
    }}

    if (hitEnemy) {{
      takeDamage(1, "Shadow Fiend");
      if (state.done) return;
    }}

    if (passable) {{
      state.pos = [targetX, targetY];
      playerVisual.targetX = targetX;
      playerVisual.targetY = targetY;
      playerVisual.lerp = 0.0;
      moved = true;
      sfx("step");

      // Check Hazard Pit damage
      const tileCh = state.raw[targetY][targetX];
      if (tileCh === "~") {{
        takeDamage(1, "Pit Hazard");
        if (state.done) return;
      }}

      // Check Bug 1: Map Hole (Walking on pillar at (4,7))
      if (currentLevelId === "level_01" && targetX === 4 && targetY === 7) {{
        triggerGlitch("map_hole", "Wall Phase Exploit", "Walked right through a solid stone wall pillar at (4,7)!");
      }}

      // Exploit Bug logic: moving wipes paidFor guard so coins can be re-collected
      state.paidFor = new Set();

      // Dust particles on step
      spawnDust(targetX, targetY);

      // Check Goal
      if (targetX === state.goalPos[0] && targetY === state.goalPos[1]) {{
        state.won = true;
        state.done = true;
        state.score += 100;
        sfx("win");
        spawnConfetti();
        triggerVictory();
      }}
    }} else {{
      // Wall / obstacle collision: silently block movement without bump screen shake, sfx, or text
    }}
  }}
  else if (act === "PICKUP") {{
    const [px, py] = state.pos;
    let foundCoin = state.coins.find(c => !c.taken && c.x === px && c.y === py);

    // Exploit Bug: coin duplication
    if (foundCoin) {{
      state.score += 10;
      state.combo++;
      sfx("coin");
      spawnSparkles(px, py, "#fbbf24");
      addFloatingText(`+10 COIN! x${{state.combo}}`, px, py, "#f59e0b");

      // In level_01 with exploit enabled, coin isn't marked permanently taken if stepped back
      if (currentLevelId === "level_01" && state.paidFor.has(`${{px}},${{py}}`)) {{
        // already paid on this tile
      }} else {{
        state.paidFor.add(`${{px}},${{py}}`);
        // Check if coin collected > total
        foundCoin.taken = true; // normal, but if player re-triggers duplicate:
        const totalCoins = state.coins.length;
        const countTaken = state.coins.filter(c => c.taken).length;
        if (state.score > totalCoins * 10 + 100) {{
          triggerGlitch("exploit", "Coin Duplication Exploit", "Infinite coin harvest triggered!");
        }}
      }}
    }}
    else if (state.keyPos && state.keyPos[0] === px && state.keyPos[1] === py && !state.inventory.includes("key")) {{
      state.inventory.push("key");
      state.keyPos = null;
      state.holdingKeyFlag = true;
      sfx("key");
      spawnSparkles(px, py, "#a855f7");
      addFloatingText("KEY ACQUIRED! 🗝️", px, py, "#c084fc");
    }} else {{
      // No item to pickup
    }}
  }}
  else if (act === "DROP") {{
    if (state.inventory.includes("key")) {{
      const [px, py] = state.pos;
      const tileCh = state.raw[py][px];

      // Bug 2: Softlock if dropped into pit '~'
      if (tileCh === "~") {{
        state.inventory = state.inventory.filter(i => i !== "key");
        state.keyPos = null;
        state.keyDestroyed = true;
        sfx("glitch");
        screenShake = 8;
        addFloatingText("KEY DESTROYED IN PIT! 💀", px, py, "#ef4444");
        triggerGlitch("softlock", "Key Lost in Void", "Dropped the key into a bottomless pit! The door can never open!");
      }} else {{
        state.inventory = state.inventory.filter(i => i !== "key");
        state.keyPos = [px, py];
        sfx("step");
        addFloatingText("KEY DROPPED", px, py, "#94a3b8");
      }}
    }}
  }}
  else if (act === "USE") {{
    const [px, py] = state.pos;
    const [dx, dy] = state.doorPos;
    const isAdjacent = Math.abs(px - dx) + Math.abs(py - dy) === 1;

    if (isAdjacent && !state.doorOpen) {{
      // Bug 4: Stale key flag crash!
      if (state.holdingKeyFlag && !state.inventory.includes("key")) {{
        sfx("glitch");
        screenShake = 12;
        addFloatingText("💥 CRASH: IndexError!", px, py, "#dc2626");
        triggerGlitch("crash", "Ghost Key Crash", "USE indexed an empty inventory due to stale _holding_key flag!");
        return;
      }}

      if (state.inventory.includes("key")) {{
        state.doorOpen = true;
        state.inventory = state.inventory.filter(i => i !== "key");
        state.holdingKeyFlag = false;
        sfx("door");
        screenShake = 6;
        spawnDust(dx, dy);
        addFloatingText("DOOR UNLOCKED! 🚪", dx, dy, "#34d399");
      }} else {{
        addFloatingText("LOCKED (Needs Key)", dx, dy, "#fbbf24");
      }}
    }}
  }}

  // Advance patrolling enemies
  for (let i = 0; i < state.enemies.length; i++) {{
    const e = state.enemies[i];
    let nxt = e.idx + e.dir;
    if (nxt >= e.path.length || nxt < 0) {{
      e.dir = -e.dir;
      nxt = e.idx + e.dir;
    }}
    e.idx = nxt;
    const pt = e.path[nxt];
    enemiesVisual[i].targetX = pt[0];
    enemiesVisual[i].targetY = pt[1];
    enemiesVisual[i].lerp = 0.0;

    // Ambush: enemy steps onto player position
    if (pt[0] === state.pos[0] && pt[1] === state.pos[1]) {{
      takeDamage(1, "Patrol Ambush");
    }}
  }}

  // Contact damage: if player stopped or ended action on an enemy tile
  for (const e of state.enemies) {{
    const ep = e.path[e.idx];
    if (ep[0] === state.pos[0] && ep[1] === state.pos[1]) {{
      takeDamage(1, "Shadow Fiend");
      break;
    }}
  }}

  updateHUD();
}}

function triggerGlitch(kind, title, desc) {{
  unlockedGlitches[kind] = true;
  sfx("glitch");
  screenShake = 10;
  const item = document.getElementById(`glitch-${{kind}}`);
  if (item) {{
    item.classList.add("unlocked");
    item.querySelector(".glitch-badge").innerText = "DETECTED 🚨";
  }}
  document.getElementById("glitchToastTitle").innerText = `🚨 DETECTED: ${{title}}`;
  document.getElementById("glitchToastDesc").innerText = desc;
  document.getElementById("glitchToast").style.display = "flex";
  updateHUD();
}}

function closeToast() {{
  document.getElementById("glitchToast").style.display = "none";
}}

function triggerVictory() {{
  const par = state.level.par_steps || 28;
  let stars = "⭐";
  if (state.steps <= par + 10) stars = "⭐⭐";
  if (state.steps <= par) stars = "⭐⭐⭐";

  document.getElementById("vicStars").innerText = stars;
  document.getElementById("vicSummary").innerText = `Cleared ${{state.level.name}} in ${{state.steps}} steps with score ${{state.score}}! (Par: ${{par}})`;
  document.getElementById("victoryModal").classList.add("show");
}}

function nextLevelOrRestart() {{
  document.getElementById("victoryModal").classList.remove("show");
  if (currentLevelId === "level_01") changeLevel("level_02");
  else if (currentLevelId === "level_02") changeLevel("level_03");
  else changeLevel("level_01");
}}

// Particle System
function spawnSparkles(x, y, color) {{
  for (let i = 0; i < 16; i++) {{
    const angle = Math.random() * Math.PI * 2;
    const speed = 1.0 + Math.random() * 3.0;
    particles.push({{
      x: (x + 0.5) * 48,
      y: (y + 0.5) * 48,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      life: 1.0,
      decay: 0.03 + Math.random() * 0.03,
      size: 2.5 + Math.random() * 3.5,
      color
    }});
  }}
}}

function spawnDamageSparks(x, y) {{
  for (let i = 0; i < 22; i++) {{
    const angle = Math.random() * Math.PI * 2;
    const speed = 1.8 + Math.random() * 4.2;
    particles.push({{
      x: (x + 0.5) * 48,
      y: (y + 0.5) * 48,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      life: 1.0,
      decay: 0.04 + Math.random() * 0.04,
      size: 3.0 + Math.random() * 3.0,
      color: Math.random() > 0.4 ? "#ef4444" : "#f59e0b"
    }});
  }}
}}

function spawnDeathExplosion(x, y) {{
  const colors = ["#ef4444", "#dc2626", "#7f1d1d", "#f59e0b", "#ffffff"];
  for (let i = 0; i < 48; i++) {{
    const angle = Math.random() * Math.PI * 2;
    const speed = 2.0 + Math.random() * 6.0;
    particles.push({{
      x: (x + 0.5) * 48,
      y: (y + 0.5) * 48,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      life: 1.0,
      decay: 0.018 + Math.random() * 0.02,
      size: 4.0 + Math.random() * 5.0,
      color: colors[Math.floor(Math.random() * colors.length)]
    }});
  }}
}}

function spawnDust(x, y) {{
  for (let i = 0; i < 8; i++) {{
    particles.push({{
      x: (x + 0.5) * 48 + (Math.random() - 0.5) * 16,
      y: (y + 0.5) * 48 + 14,
      vx: (Math.random() - 0.5) * 1.5,
      vy: -Math.random() * 1.5,
      life: 1.0,
      decay: 0.05 + Math.random() * 0.04,
      size: 2.0 + Math.random() * 2.5,
      color: "#94a3b8"
    }});
  }}
}}

function spawnConfetti() {{
  const colors = ["#fbbf24", "#34d399", "#60a5fa", "#f43f5e", "#a855f7"];
  for (let i = 0; i < 60; i++) {{
    particles.push({{
      x: 288 + (Math.random() - 0.5) * 200,
      y: 200,
      vx: (Math.random() - 0.5) * 6,
      vy: -2 - Math.random() * 6,
      life: 1.0,
      decay: 0.015,
      size: 4 + Math.random() * 4,
      color: colors[Math.floor(Math.random() * colors.length)]
    }});
  }}
}}

function addFloatingText(text, x, y, color) {{
  floatingTexts.push({{
    text,
    x: (x + 0.5) * 48,
    y: (y + 0.2) * 48,
    life: 1.0,
    color
  }});
}}

// AI Swarm Bot BFS Route Planner
function bfsFindPath(start, target) {{
  if (!start || !target) return null;
  const queue = [[start]];
  const visited = new Set([`${{start[0]}},${{start[1]}}`]);

  while (queue.length > 0) {{
    const path = queue.shift();
    const [cx, cy] = path[path.length - 1];
    if (cx === target[0] && cy === target[1]) return path;

    for (const [dx, dy] of [[0,-1], [0,1], [-1,0], [1,0]]) {{
      const nx = cx + dx;
      const ny = cy + dy;
      const nKey = `${{nx}},${{ny}}`;
      if (state.walkable.has(nKey) && !visited.has(nKey)) {{
        // Door check
        if (state.doorPos && nx === state.doorPos[0] && ny === state.doorPos[1] && !state.doorOpen) {{
          if (nx === target[0] && ny === target[1]) {{
            // Can target door to unlock
          }} else {{
            continue;
          }}
        }}
        visited.add(nKey);
        queue.push([...path, [nx, ny]]);
      }}
    }}
  }}
  return null;
}}

function getNextBotAction() {{
  const botType = document.getElementById("botTypeSelect").value;
  const [px, py] = state.pos;

  if (botType === "random_walker") {{
    const acts = ["UP", "DOWN", "LEFT", "RIGHT", "PICKUP", "WAIT"];
    return acts[Math.floor(Math.random() * acts.length)];
  }}

  if (botType === "chaos_tester") {{
    const chaos = ["PICKUP", "DROP", "USE", "WAIT", "UP", "DOWN", "LEFT", "RIGHT"];
    return chaos[Math.floor(Math.random() * chaos.length)];
  }}

  // Goal Seeker Bot: Smart BFS
  const hasKey = state.inventory.includes("key");

  if (!hasKey && state.keyPos) {{
    if (px === state.keyPos[0] && py === state.keyPos[1]) {{
      updateBotHud("🎯 [Goal Seeker] Grabbing Key! [PICKUP]");
      return "PICKUP";
    }}
    const path = bfsFindPath([px, py], state.keyPos);
    if (path && path.length > 1) {{
      botBreadcrumbPath = path;
      const nextStep = path[1];
      updateBotHud(`🎯 [Goal Seeker] Routing to Key (${{state.keyPos[0]}},${{state.keyPos[1]}}) · ${{path.length - 1}} steps left`);
      return getMoveDir([px, py], nextStep);
    }}
  }}

  if (!state.doorOpen && state.doorPos) {{
    const [dx, dy] = state.doorPos;
    const isAdjacent = Math.abs(px - dx) + Math.abs(py - dy) === 1;
    if (isAdjacent) {{
      updateBotHud("🗝️ [Goal Seeker] Unlocking Door with Key! [USE]");
      return "USE";
    }}
    // Approach door
    const path = bfsFindPath([px, py], state.doorPos);
    if (path && path.length > 2) {{
      botBreadcrumbPath = path;
      updateBotHud(`🚪 [Goal Seeker] Navigating to Locked Door · ${{path.length - 2}} steps`);
      return getMoveDir([px, py], path[1]);
    }}
  }}

  // Route to Goal
  const path = bfsFindPath([px, py], state.goalPos);
  if (path && path.length > 1) {{
    botBreadcrumbPath = path;
    updateBotHud(`🏆 [Goal Seeker] Heading to Exit Portal · ${{path.length - 1}} steps`);
    return getMoveDir([px, py], path[1]);
  }}

  return "WAIT";
}}

function getMoveDir(curr, next) {{
  if (next[0] > curr[0]) return "RIGHT";
  if (next[0] < curr[0]) return "LEFT";
  if (next[1] > curr[1]) return "DOWN";
  if (next[1] < curr[1]) return "UP";
  return "WAIT";
}}

function updateBotHud(text) {{
  const hud = document.getElementById("botHud");
  hud.classList.add("visible");
  document.getElementById("botText").innerText = text;
}}

function toggleBotPlay() {{
  botRunning = !botRunning;
  const btn = document.getElementById("botPlayBtn");
  btn.innerText = botRunning ? "⏸ Pause Bot" : "▶ Start Bot";
  btn.style.background = botRunning ? "#f59e0b" : "#059669";
  if (botRunning) {{
    runBotLoop();
  }} else {{
    if (botTimer) clearTimeout(botTimer);
  }}
}}

function runBotLoop() {{
  if (!botRunning || state.done) {{
    botRunning = false;
    document.getElementById("botPlayBtn").innerText = "▶ Start Bot";
    document.getElementById("botPlayBtn").style.background = "#059669";
    return;
  }}
  stepBot();
  const speed = parseInt(document.getElementById("botSpeedSelect").value) || 200;
  botTimer = setTimeout(runBotLoop, speed);
}}

function stepBot() {{
  if (state.done) return;
  const act = getNextBotAction();
  executeAction(act);
}}

function setMode(mode) {{
  currentMode = mode;
  document.getElementById("modeHumanBtn").classList.toggle("active", mode === "human");
  document.getElementById("modeBotBtn").classList.toggle("active", mode === "bot");
  document.getElementById("botControls").style.display = mode === "bot" ? "flex" : "none";
  document.getElementById("modeBadge").innerText = mode.toUpperCase();
  document.getElementById("modeBadge").style.color = mode === "bot" ? "#a855f7" : "#38bdf8";
  if (mode === "human") {{
    botRunning = false;
    if (botTimer) clearTimeout(botTimer);
    document.getElementById("botHud").classList.remove("visible");
  }}
}}

// Keyboard Controls
window.addEventListener("keydown", (e) => {{
  if (currentMode !== "human") return;
  const key = e.key.toUpperCase();
  if (["ARROWUP", "W"].includes(key)) {{ e.preventDefault(); executeAction("UP"); }}
  else if (["ARROWDOWN", "S"].includes(key)) {{ e.preventDefault(); executeAction("DOWN"); }}
  else if (["ARROWLEFT", "A"].includes(key)) {{ e.preventDefault(); executeAction("LEFT"); }}
  else if (["ARROWRIGHT", "D"].includes(key)) {{ e.preventDefault(); executeAction("RIGHT"); }}
  else if ([" ", "E"].includes(key)) {{ e.preventDefault(); executeAction("PICKUP"); }}
  else if (key === "F") {{ e.preventDefault(); executeAction("USE"); }}
  else if (key === "X") {{ e.preventDefault(); executeAction("DROP"); }}
  else if (key === ".") {{ e.preventDefault(); executeAction("WAIT"); }}
}});

function handleAction(act) {{
  executeAction(act);
}}

function changeLevel(lvl) {{
  document.getElementById("levelSelect").value = lvl;
  initGame(lvl);
}}

function changeTheme(th) {{
  theme = th;
}}

function resetGame() {{
  initGame(currentLevelId);
}}

// Main 60 FPS Canvas Rendering Engine
const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");
const CELL = 48;

let animFrame = 0;

function renderLoop() {{
  animFrame++;
  ctx.save();
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Screen shake
  if (screenShake > 0) {{
    ctx.translate((Math.random() - 0.5) * screenShake, (Math.random() - 0.5) * screenShake);
    screenShake *= 0.85;
    if (screenShake < 0.2) screenShake = 0;
  }}

  // Tick invulnerability timer & damage flash
  if (state.invulnerableTimer > 0) state.invulnerableTimer--;
  if (state.damageFlash > 0) {{
    state.damageFlash = Math.max(0, state.damageFlash - 0.04);
  }}

  // Real-time contact damage: if player stops on or touches an enemy
  if (!state.done && state.invulnerableTimer === 0 && state.enemies) {{
    for (let i = 0; i < state.enemies.length; i++) {{
      const e = state.enemies[i];
      const ep = e.path[e.idx];
      const ev = enemiesVisual[i];
      const isSameTile = (ep[0] === state.pos[0] && ep[1] === state.pos[1]);
      const dist = ev ? Math.hypot(playerVisual.x - ev.x, playerVisual.y - ev.y) : 99;
      if (isSameTile || dist < 0.65) {{
        takeDamage(1, "Shadow Fiend");
        break;
      }}
    }}
  }}

  // Interpolate Player visual coordinates for 60fps smooth movement
  playerVisual.lerp = Math.min(1.0, playerVisual.lerp + 0.25);
  playerVisual.x += (playerVisual.targetX - playerVisual.x) * 0.35;
  playerVisual.y += (playerVisual.targetY - playerVisual.y) * 0.35;

  // Interpolate Enemies
  enemiesVisual.forEach(ev => {{
    ev.lerp = Math.min(1.0, ev.lerp + 0.2);
    ev.x += (ev.targetX - ev.x) * 0.3;
    ev.y += (ev.targetY - ev.y) * 0.3;
  }});

  // 1. Draw Map Tiles
  drawTiles();

  // 2. Draw Bot Path Breadcrumb (if AI bot mode)
  if (currentMode === "bot" && botBreadcrumbPath.length > 1) {{
    ctx.strokeStyle = "rgba(56, 189, 248, 0.45)";
    ctx.lineWidth = 3;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    botBreadcrumbPath.forEach((pt, i) => {{
      const px = pt[0] * CELL + CELL / 2;
      const py = pt[1] * CELL + CELL / 2;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }});
    ctx.stroke();
    ctx.setLineDash([]);
  }}

  // 3. Draw Items (Coins, Key)
  drawItems();

  // 4. Draw Door & Goal Portal
  drawDoorAndGoal();

  // 5. Draw Enemies
  drawEnemies();

  // 6. Draw Player Knight
  drawPlayer();

  // 7. Dynamic Torchlight Vignette / Radial Glow
  drawLighting();

  // 8. Particle System
  drawParticles();

  // 9. Floating Text Notifications
  drawFloatingTexts();

  // 10. Damage Flash Vignette
  if (state.damageFlash > 0) {{
    ctx.save();
    ctx.fillStyle = `rgba(239, 68, 68, ${{state.damageFlash * 0.45}})`;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.restore();
  }}

  ctx.restore();
  requestAnimationFrame(renderLoop);
}}

function drawTiles() {{
  const raw = state.raw;
  for (let y = 0; y < state.height; y++) {{
    for (let x = 0; x < state.width; x++) {{
      const ch = raw[y][x];
      const bx = x * CELL;
      const by = y * CELL;

      if (theme === "gameboy") {{
        // GameBoy 4-color LCD palette
        if (ch === "#") {{
          ctx.fillStyle = "#0f380f";
          ctx.fillRect(bx, by, CELL, CELL);
        }} else {{
          ctx.fillStyle = "#8bac0f";
          ctx.fillRect(bx, by, CELL, CELL);
          ctx.strokeStyle = "#306230";
          ctx.strokeRect(bx + 1, by + 1, CELL - 2, CELL - 2);
        }}
        continue;
      }}

      if (ch === "#") {{
        // Wall (3D Dungeon Masonry)
        if (theme === "cyber") {{
          ctx.fillStyle = "#0b1329";
          ctx.fillRect(bx, by, CELL, CELL);
          ctx.strokeStyle = "#1d4ed8";
          ctx.lineWidth = 1;
          ctx.strokeRect(bx + 2, by + 2, CELL - 4, CELL - 4);
          ctx.fillStyle = "#38bdf8";
          ctx.fillRect(bx + CELL / 2 - 2, by + CELL / 2 - 2, 4, 4);
        }} else {{
          // Classic Dungeon Stone
          ctx.fillStyle = "#2c313e";
          ctx.fillRect(bx, by, CELL, CELL);
          // Highlight rim
          ctx.fillStyle = "#4a5266";
          ctx.fillRect(bx, by, CELL, 3);
          ctx.fillRect(bx, by, 3, CELL);
          // Shadow rim
          ctx.fillStyle = "#161922";
          ctx.fillRect(bx, by + CELL - 3, CELL, 3);
          ctx.fillRect(bx + CELL - 3, by, 3, CELL);
          // Mortar lines
          ctx.strokeStyle = "#1e222c";
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(bx, by + CELL / 2); ctx.lineTo(bx + CELL, by + CELL / 2);
          ctx.moveTo(bx + CELL / 2, by); ctx.lineTo(bx + CELL / 2, by + CELL / 2);
          ctx.stroke();
        }}
      }} else {{
        // Floor
        if (theme === "cyber") {{
          ctx.fillStyle = "#030712";
          ctx.fillRect(bx, by, CELL, CELL);
          ctx.strokeStyle = "#1e1b4b";
          ctx.strokeRect(bx, by, CELL, CELL);
        }} else {{
          ctx.fillStyle = "#1c202a";
          ctx.fillRect(bx, by, CELL, CELL);
          ctx.strokeStyle = "#252b38";
          ctx.strokeRect(bx + 1, by + 1, CELL - 2, CELL - 2);
          ctx.fillStyle = "#2a3140";
          ctx.fillRect(bx + CELL / 2 - 1, by + CELL / 2 - 1, 2, 2);
        }}

        if (ch === "~") {{
          // Hazard Pit
          ctx.fillStyle = "#090b14";
          ctx.fillRect(bx + 4, by + 4, CELL - 8, CELL - 8);
          ctx.strokeStyle = "#3b82f6";
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.arc(bx + CELL / 2, by + CELL / 2, CELL / 3, 0, Math.PI * 2);
          ctx.stroke();
        }}
      }}
    }}
  }}
}}

function drawItems() {{
  // Coins
  state.coins.forEach(c => {{
    if (c.taken) return;
    const cx = c.x * CELL + CELL / 2;
    const cy = c.y * CELL + CELL / 2;
    const bounce = Math.sin(animFrame * 0.08 + c.id) * 3;

    ctx.save();
    ctx.shadowColor = "#fbbf24";
    ctx.shadowBlur = 8;
    // Outer Coin
    ctx.fillStyle = "#fbbf24";
    ctx.beginPath();
    ctx.arc(cx, cy + bounce, 10, 0, Math.PI * 2);
    ctx.fill();
    // Inner Rim
    ctx.strokeStyle = "#d97706";
    ctx.lineWidth = 2;
    ctx.stroke();
    // Star glint
    ctx.fillStyle = "#fff";
    ctx.fillRect(cx - 3, cy + bounce - 3, 3, 3);
    ctx.restore();
  }});

  // Key
  if (state.keyPos) {{
    const kx = state.keyPos[0] * CELL + CELL / 2;
    const ky = state.keyPos[1] * CELL + CELL / 2;
    const bob = Math.sin(animFrame * 0.07) * 4;

    ctx.save();
    ctx.shadowColor = "#c084fc";
    ctx.shadowBlur = 10;
    ctx.strokeStyle = "#fbbf24";
    ctx.lineWidth = 3;
    // Bow ring
    ctx.beginPath();
    ctx.arc(kx, ky + bob - 6, 7, 0, Math.PI * 2);
    ctx.stroke();
    // Stem
    ctx.beginPath();
    ctx.moveTo(kx, ky + bob);
    ctx.lineTo(kx, ky + bob + 12);
    // Bit notches
    ctx.moveTo(kx, ky + bob + 8);
    ctx.lineTo(kx + 5, ky + bob + 8);
    ctx.moveTo(kx, ky + bob + 12);
    ctx.lineTo(kx + 4, ky + bob + 12);
    ctx.stroke();
    ctx.restore();
  }}
}}

function drawDoorAndGoal() {{
  // Door
  if (state.doorPos) {{
    const [dx, dy] = state.doorPos;
    const bx = dx * CELL;
    const by = dy * CELL;
    if (!state.doorOpen) {{
      ctx.fillStyle = "#5c3317";
      ctx.fillRect(bx + 4, by + 4, CELL - 8, CELL - 8);
      // Iron bands
      ctx.fillStyle = "#475569";
      ctx.fillRect(bx + 4, by + 10, CELL - 8, 4);
      ctx.fillRect(bx + 4, by + CELL - 14, CELL - 8, 4);
      // Brass Keyhole
      ctx.fillStyle = "#f59e0b";
      ctx.beginPath();
      ctx.arc(bx + CELL / 2, by + CELL / 2, 4, 0, Math.PI * 2);
      ctx.fill();
    }}
  }}

  // Goal (Portal)
  if (state.goalPos) {{
    const [gx, gy] = state.goalPos;
    const cx = gx * CELL + CELL / 2;
    const cy = gy * CELL + CELL / 2;
    const spin = animFrame * 0.05;

    ctx.save();
    ctx.shadowColor = "#34d399";
    ctx.shadowBlur = 14;
    // Outer magic ring
    ctx.strokeStyle = "#10b981";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.arc(cx, cy, 18, 0, Math.PI * 2);
    ctx.stroke();
    // Swirling vortex arcs
    ctx.strokeStyle = "#6ee7b7";
    ctx.beginPath();
    ctx.arc(cx, cy, 12, spin, spin + Math.PI * 1.3);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(cx, cy, 6, -spin, -spin + Math.PI * 1.3);
    ctx.stroke();
    ctx.restore();
  }}
}}

function drawEnemies() {{
  enemiesVisual.forEach(ev => {{
    const cx = ev.x * CELL + CELL / 2;
    const cy = ev.y * CELL + CELL / 2;
    const bob = Math.sin(animFrame * 0.1) * 2;

    ctx.save();
    ctx.shadowColor = "#ef4444";
    ctx.shadowBlur = 10;
    // Horned Crimson Fiend Body
    ctx.fillStyle = "#dc2626";
    ctx.beginPath();
    ctx.arc(cx, cy + bob, 12, 0, Math.PI * 2);
    ctx.fill();
    // Horns
    ctx.fillStyle = "#991b1b";
    ctx.beginPath();
    ctx.moveTo(cx - 8, cy + bob - 6); ctx.lineTo(cx - 12, cy + bob - 14); ctx.lineTo(cx - 4, cy + bob - 10);
    ctx.moveTo(cx + 8, cy + bob - 6); ctx.lineTo(cx + 12, cy + bob - 14); ctx.lineTo(cx + 4, cy + bob - 10);
    ctx.fill();
    // Glowing Evil Yellow Eyes
    ctx.fillStyle = "#fde047";
    ctx.fillRect(cx - 6, cy + bob - 2, 3, 3);
    ctx.fillRect(cx + 3, cy + bob - 2, 3, 3);
    ctx.restore();
  }});
}}

function drawPlayer() {{
  // Invulnerability flicker
  if (state.invulnerableTimer > 0 && Math.floor(animFrame / 4) % 2 === 0) {{
    return; // Classic i-frame blinking
  }}

  const px = playerVisual.x * CELL + CELL / 2;
  const py = playerVisual.y * CELL + CELL / 2;
  const idleBob = state.health <= 0 ? 4 : Math.sin(animFrame * 0.12) * 2;

  ctx.save();
  // Hero Shadow
  ctx.fillStyle = "rgba(0, 0, 0, 0.4)";
  ctx.beginPath();
  ctx.ellipse(px, py + 14, 12, 5, 0, 0, Math.PI * 2);
  ctx.fill();

  if (state.health <= 0) {{
    // Defeated Knight Tombstone
    ctx.fillStyle = "#475569";
    ctx.beginPath();
    ctx.arc(px, py + 2, 11, Math.PI, 0);
    ctx.lineTo(px + 11, py + 14);
    ctx.lineTo(px - 11, py + 14);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = "#ef4444";
    ctx.font = "bold 9px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("RIP", px, py + 10);
    ctx.restore();
    return;
  }}

  // Knight Blue Armor (or red hurt tint during i-frames)
  ctx.fillStyle = state.won ? "#fbbf24" : (state.invulnerableTimer > 0 ? "#f87171" : "#2563eb");
  ctx.beginPath();
  ctx.arc(px, py + idleBob, 12, 0, Math.PI * 2);
  ctx.fill();

  // Polished Steel Visor Helmet
  ctx.fillStyle = "#94a3b8";
  ctx.beginPath();
  ctx.arc(px, py + idleBob - 2, 10, Math.PI, 0);
  ctx.fill();

  // Cyan Visor Glow (or red when hurt)
  ctx.fillStyle = state.invulnerableTimer > 0 ? "#ef4444" : "#38bdf8";
  ctx.fillRect(px - 7, py + idleBob - 1, 14, 3);

  // Helmet Golden Crest
  ctx.fillStyle = "#fbbf24";
  ctx.beginPath();
  ctx.moveTo(px, py + idleBob - 16);
  ctx.lineTo(px - 4, py + idleBob - 9);
  ctx.lineTo(px + 4, py + idleBob - 9);
  ctx.fill();

  if (state.won) {{
    // Radiant Victory Star Halo
    ctx.strokeStyle = "#fef08a";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(px, py + idleBob, 18, 0, Math.PI * 2);
    ctx.stroke();
  }}
  ctx.restore();
}}

function drawLighting() {{
  if (theme === "gameboy") return;
  const px = playerVisual.x * CELL + CELL / 2;
  const py = playerVisual.y * CELL + CELL / 2;

  const grad = ctx.createRadialGradient(px, py, 30, px, py, 220);
  grad.addColorStop(0, "rgba(0, 0, 0, 0)");
  grad.addColorStop(0.7, "rgba(5, 7, 12, 0.4)");
  grad.addColorStop(1, "rgba(3, 4, 8, 0.85)");

  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
}}

function drawParticles() {{
  for (let i = particles.length - 1; i >= 0; i--) {{
    const p = particles[i];
    p.x += p.vx;
    p.y += p.vy;
    p.life -= p.decay;

    if (p.life <= 0) {{
      particles.splice(i, 1);
      continue;
    }}

    ctx.save();
    ctx.globalAlpha = p.life;
    ctx.fillStyle = p.color;
    ctx.fillRect(p.x, p.y, p.size, p.size);
    ctx.restore();
  }}
}}

function drawFloatingTexts() {{
  for (let i = floatingTexts.length - 1; i >= 0; i--) {{
    const ft = floatingTexts[i];
    ft.y -= 0.8;
    ft.life -= 0.02;

    if (ft.life <= 0) {{
      floatingTexts.splice(i, 1);
      continue;
    }}

    ctx.save();
    ctx.globalAlpha = ft.life;
    ctx.font = "bold 13px -apple-system, sans-serif";
    ctx.fillStyle = ft.color;
    ctx.shadowColor = "#000";
    ctx.shadowBlur = 4;
    ctx.textAlign = "center";
    ctx.fillText(ft.text, ft.x, ft.y);
    ctx.restore();
  }}
}}

// Kick off game and loop
initGame("level_01");
requestAnimationFrame(renderLoop);
</script>
</body>
</html>"""

    components.html(html_code, height=height, scrolling=False)
