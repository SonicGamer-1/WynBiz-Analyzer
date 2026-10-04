# WynBiz-Analyzer

An AI agent swarm that plays a small grid game, finds real bugs, writes
reproducible bug reports, triages them with Cline, and then proves a fix
worked — without a human writing a single test case.

## What's in here

| Path | What it is |
|---|---|
| [`game-qa-swarm/`](game-qa-swarm/) | The **AI Game QA Swarm** — a headless, deterministic grid game with four planted bugs, three agent types, four rule-based detectors, a Streamlit dashboard (playable arcade, chatbot, file analyzer), and a fix-and-verify flow. See its [README](game-qa-swarm/README.md) for the full story. |

## Quick start

```bash
cd game-qa-swarm
pip install -r requirements.txt

python scripts/seed_bugs.py              # prove the 4 planted bugs reproduce
python -m gameqa.cli run --episodes 20   # let the swarm loose
streamlit run dashboard/app.py           # dashboard + playable arcade
```

## License

[MIT](LICENSE)
