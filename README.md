# wokemeup

Personal French morning briefing: a Python pipeline on GitHub Actions fetches news
(The Guardian, Le Monde), summarizes it in French with the Claude API, generates audio
with Piper TTS, and publishes to GitHub Pages for an iPhone Shortcut.

Development context and decisions: [CLAUDE.md](CLAUDE.md).

## Local setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in keys; .env is gitignored
python -m pytest -q
python -m pipeline.main --dry-run
```

## Configuration

| File | What to change |
|---|---|
| `config/sources.yaml` | items per topic, time window, Le Monde feeds, LLM model, TTS voice |
| `config/topics.yaml` | topic titles, Guardian / Le Monde sections and keywords |
| `config/wake.json` | wake time per date (edit the night before) |

Content is a summary of the linked sources, for personal, non-commercial use.
