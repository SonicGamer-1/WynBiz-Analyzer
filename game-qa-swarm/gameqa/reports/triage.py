"""LLM triage: ask Claude for a title, severity and suspected cause.

Two things matter for the stage:
  * Results are cached on disk, so a network failure during the demo is
    invisible -- pre-warm the cache beforehand with `cli.py triage --all`.
  * There is always a deterministic heuristic fallback, so the dashboard is
    never empty even with no API key at all.

The prompt deliberately does NOT include the `# BUG:` comments from the game
source. Triage has to reason from the repro, the map data and the detector
output -- the same information a human QA engineer would have.
"""
from __future__ import annotations

import json
import os

from ..game.maps import MAP_RAW
from .signature import safe_filename


def _load_env():
    repo_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_path = os.path.join(repo_dir, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k:
                        os.environ[k] = v
        except OSError:
            pass


_load_env()

def get_cline_config():
    _load_env()
    key = os.environ.get("CLINE_API_KEY", "").strip()
    base_url = os.environ.get("CLINE_BASE_URL", "https://api.cline.bot/api/v1").rstrip("/")
    model = os.environ.get("CLINE_MODEL", "xiaomi/mimo-v2.6-flash").strip()
    return key, base_url, model

CLINE_API_KEY, CLINE_BASE_URL, CLINE_MODEL = get_cline_config()

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
MAX_TOKENS = 8192

SYSTEM = (
    "You are a senior game QA engineer triaging a bug found by automated "
    "playtesting agents in a small grid game. Reply with ONLY a JSON object, "
    "no prose, no markdown fences. Keys: title (<= 70 chars, specific), "
    "severity (one of critical/high/medium/low), suspected_cause (2-3 "
    "sentences naming the likely mechanism), suggested_fix_area (the function "
    "or module to change), confidence (0.0-1.0)."
)

_HEURISTICS = {
    "crash": (
        "Unhandled exception in action handling",
        "critical",
        "An exception escaped the game's step handler, so the run aborted. "
        "The failing action is the last one in the repro and the fault site "
        "in the detail points at the exact line.",
        "gameqa/game/grid_game.py :: GridGame.step / action handlers",
    ),
    "softlock": (
        "Progression softlock: level can no longer be completed",
        "critical",
        "Reachability analysis proves the goal is unreachable from this state. "
        "The usual cause is a required progression item leaving the world "
        "permanently instead of the action being refused.",
        "gameqa/game/grid_game.py :: drop / item handling",
    ),
    "map_hole": (
        "Collision hole: player occupies a wall tile",
        "high",
        "The player's final position is a wall in the declared level data, so "
        "the runtime walkable set disagrees with the map. Usually an "
        "off-by-one while building collision data.",
        "gameqa/game/grid_game.py :: walkable set construction",
    ),
    "exploit": (
        "Economy exploit: score exceeds the legal maximum",
        "high",
        "A cumulative counter exceeded what the level can legally produce, "
        "which means a collectible is credited more than once. Look for "
        "identity tracked by position instead of by a stable id.",
        "gameqa/game/grid_game.py :: pickup / scoring",
    ),
}


def heuristic_triage(report):
    title, severity, cause, area = _HEURISTICS.get(
        report.kind,
        ("Unexpected behaviour detected", "medium",
         "A detector rule fired; see the report detail.", "gameqa/game/"),
    )
    return {
        "title": title,
        "severity": severity,
        "suspected_cause": cause,
        "suggested_fix_area": area,
        "confidence": 0.4,
        "source": "heuristic",
        "model": None,
    }


def _user_prompt(report):
    tail_actions = report.actions[-20:] if len(report.actions) > 20 else report.actions
    start_idx = max(0, len(report.actions) - len(tail_actions))
    action_str = "\n".join("%3d %s" % (start_idx + i, a) for i, a in enumerate(tail_actions))
    map_name = getattr(report, "map_id", "level_01")
    return (
        "BUG REPORT\n"
        "============\n"
        "signature: %s\n"
        "kind: %s\n"
        "occurrences: %d (merged duplicates)\n"
        "detector summary: %s\n"
        "map: %s   seed: %d   bot: %s   failed at step: %d (total actions: %d)\n\n"
        "DETECTOR FINDINGS DETAIL\n%s\n\n"
        "REPRO ACTION SEQUENCE (failing tail sequence)\n%s\n"
        % (
            report.signature,
            report.kind,
            report.occurrences,
            report.summary,
            map_name,
            report.seed,
            report.bot,
            report.step_index,
            len(report.actions),
            json.dumps(report.detail, indent=2, sort_keys=True),
            action_str,
        )
    )


def _extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object in response")
    return json.loads(text[start:end + 1])


class Triager:
    def __init__(self, store, model=None, offline=False):
        self.store = store
        key, base_url, cline_model = get_cline_config()
        default_model = cline_model if key else MODEL
        self.model = model or default_model
        has_key = bool(key or os.environ.get("ANTHROPIC_API_KEY"))
        self.offline = offline if (offline and not has_key) else (offline and not bool(key))

    # --------------------------------------------------------------- cache

    def cache_path(self, signature):
        return os.path.join(self.store.cache_dir,
                            safe_filename(signature) + ".json")

    def read_cache(self, signature):
        path = self.cache_path(signature)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (ValueError, OSError):
            return None

    def write_cache(self, signature, payload):
        try:
            with open(self.cache_path(signature), "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
        except OSError:
            pass

    # ---------------------------------------------------------------- call

    def _call_cline_api(self, report):
        import urllib.request

        api_key, base_url, default_model = get_cline_config()
        model = self.model or default_model

        url = f"{base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": _user_prompt(report)},
            ],
            "max_tokens": MAX_TOKENS,
            "temperature": 0.0,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        choices = data.get("choices") or (data.get("data", {}).get("choices") if isinstance(data.get("data"), dict) else [])
        if not choices:
            raise ValueError(f"No choices returned from Cline API: {data}")
        content = choices[0].get("message", {}).get("content", "")
        result = _extract_json(content)
        result["source"] = "live"
        result["model"] = f"cline:{model}"
        return result

    def _call_api(self, report):
        key, _, _ = get_cline_config()
        if key:
            return self._call_cline_api(report)

        import anthropic  # lazy: the package stays optional

        client = anthropic.Anthropic()
        message = client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            temperature=0.0,
            system=SYSTEM,
            messages=[{"role": "user", "content": _user_prompt(report)}],
        )
        parts = []
        for block in getattr(message, "content", []) or []:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        payload = _extract_json("".join(parts))
        payload["source"] = "live"
        payload["model"] = self.model
        return payload

    def triage(self, report, force=False):
        """Return a triage dict. Never raises -- the demo cannot stall here."""
        if not force:
            cached = self.read_cache(report.signature)
            # Use cached result if offline, or if the cache is an actual AI response (not a heuristic fallback)
            if cached and (self.offline or (cached.get("model") and cached.get("source") != "heuristic")):
                cached.setdefault("source", "cached")
                return cached
        if self.offline:
            payload = heuristic_triage(report)
            self.write_cache(report.signature, payload)
            return payload
        try:
            payload = self._call_api(report)
        except Exception as exc:                      # noqa: BLE001
            cached = self.read_cache(report.signature)
            if cached and cached.get("model"):
                cached["source"] = "cached"
                cached["api_error"] = "%s: %s" % (type(exc).__name__, exc)
                return cached
            payload = heuristic_triage(report)
            payload["api_error"] = "%s: %s" % (type(exc).__name__, exc)
        self.write_cache(report.signature, payload)
        return payload

    def apply(self, report, force=False):
        payload = self.triage(report, force=force)
        report.triage = payload
        if payload.get("title"):
            report.title = payload["title"]
        if payload.get("severity"):
            report.severity = payload["severity"]
        self.store.save(report)
        return report
