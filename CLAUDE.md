# CLAUDE.md — Morning Briefing (project context)

This file is the working context for Claude when developing this repository. Read it fully before making changes. Keep it updated when decisions change.

## 1. What this project is

A personal morning briefing system:

- A **Python pipeline** runs on **GitHub Actions** (free). It fetches news, selects stories, writes **French summaries** with the **Claude API**, generates a **French audio briefing** with a **free TTS engine**, and publishes the results to **GitHub Pages**.
- An **iPhone Shortcut** (Apple Shortcuts, no paid Apple developer account, no app to sign) downloads the latest briefing, plays the audio at wake-up, shows a list of stories, and opens each story's source link in Safari.

The repository is **public**. It must never contain secrets or personal data beyond the wake-time schedule file.

Owner: Noé (Liège, Belgium). Timezone: `Europe/Brussels`. Briefings are in **French**.

## 2. Scope of version 1

**In scope**

- Sources: **The Guardian** (Content API) and **Le Monde** (RSS). Le Soir is out of scope until a usable feed is confirmed.
- Four topics, no preset configuration UI in v1:
  1. **Géopolitique** (geopolitics)
  2. **Énergie** (energy sector)
  3. **Numérique** (digital: tech, AI, digital policy, telecoms)
  4. **Bonne nouvelle du jour** (good news of the day)
- Summaries in French, with the source link and outlet name for every story.
- French audio briefing, free TTS.
- Wake time that can differ every day and is set the night before.
- Public GitHub Pages output consumed by the iPhone Shortcut.

**Out of scope for v1** (do not build yet)

- Preset editor, user accounts, multi-user support.
- Le Soir and other outlets.
- Native Swift app, push notifications, paid Apple developer features.
- Full article text. Only headlines, short summaries, and links are stored or published.
- Any "certified accuracy" claim. The app shows outlet, timestamp, and link so the user can verify.
- Personal section from email and calendar, summarized by a local LLM (e.g. Ollama on the owner's Mac). Future step after v1. Its content must stay on-device and never be published, because this repo and GitHub Pages are public.

## 3. Architecture

```
GitHub Actions (hourly, see §8)
  1. fetch   -> Guardian Content API, Le Monde RSS
  2. select  -> assign each item to a topic, dedupe, rank, keep N per topic
  3. summarize -> Claude API (French, grounded on source text only)
  4. speak   -> Piper TTS -> MP3
  5. publish -> docs/ (GitHub Pages): briefing.json, briefing-YYYY-MM-DD.mp3

iPhone (Shortcuts)
  -> at wake time: fetch briefing.json, play MP3, show story menu
  -> story tap: open source_url in Safari
```

## 4. Repository layout (target)

```
.
├── CLAUDE.md                    # this file
├── README.md                    # human-facing setup notes
├── config/
│   ├── topics.yaml              # topic definitions and keywords per source
│   ├── sources.yaml             # feed URLs, Guardian filters, limits
│   └── wake.json                # per-day wake times (edited the night before)
├── pipeline/
│   ├── __init__.py
│   ├── main.py                  # orchestrates all steps; CLI entry point
│   ├── config.py                # loads config/*.yaml and wake.json
│   ├── sources/
│   │   ├── guardian.py
│   │   └── lemonde_rss.py
│   ├── select.py                # topic assignment, dedupe, ranking
│   ├── summarize.py             # Claude API calls
│   ├── tts.py                   # Piper wrapper -> MP3
│   ├── publish.py               # writes docs/
│   └── models.py                # dataclasses for items and briefing
├── docs/                        # GitHub Pages root (generated, committed)
│   ├── briefing.json
│   └── briefing-YYYY-MM-DD.mp3
├── tests/
│   ├── fixtures/                # saved sample responses (no live calls in tests)
│   └── test_*.py
├── shortcut/
│   └── SHORTCUT.md              # step-by-step recipe to rebuild the iPhone Shortcut
├── requirements.txt
└── .github/workflows/
    ├── briefing.yml             # scheduled + manual run
    └── test.yml                 # runs pytest on pull requests
```

## 5. Output contract: `docs/briefing.json`

This file is the **only** interface between the pipeline and the iPhone Shortcut. Do not change its shape without bumping `schema_version` and updating `shortcut/SHORTCUT.md`.

```json
{
  "schema_version": 1,
  "date": "2026-11-21",
  "generated_at": "2026-11-21T04:00:00Z",
  "timezone": "Europe/Brussels",
  "status": "ok",
  "audio_url": "briefing-2026-11-21.mp3",
  "topics": [
    {
      "id": "geopolitique",
      "title": "Géopolitique",
      "items": [
        {
          "title_fr": "Titre en français",
          "summary_fr": "Résumé court, en français, fondé uniquement sur le texte source.",
          "outlet": "Le Monde",
          "published_at": "2026-11-20T18:12:00Z",
          "source_url": "https://www.lemonde.fr/..."
        }
      ]
    }
  ]
}
```

Rules:

- `status` is `"ok"` for a fresh briefing, `"fallback"` when the pipeline failed and the previous day's briefing is republished (the audio then starts with a spoken notice that the news is from the previous day; see §9).
- `audio_url` is relative to `docs/`, or `null` when no audio was generated (M0 to M3).
- Topics always appear in this order: geopolitique, energie, numerique, bonne-nouvelle.
- Each topic has at most `max_items_per_topic` items (default 4). An empty topic is kept with `items: []`, and the audio says so in one sentence.

## 6. Sources and topic selection

### 6.1 Guardian (Content API)

- Endpoint: `https://content.guardianapis.com/search`
- Auth: `api-key` query parameter, read from the environment variable `GUARDIAN_API_KEY`. Never hard-code it.
- The developer key is for **non-commercial use**. This project is personal and non-commercial. If the project ever becomes commercial or distributed as a product, stop and ask the owner about a commercial key.
- Request only the fields needed: `show-fields=headline,trailText,byline` (and `bodyText` only transiently for summarization input, never published).
- Respect rate limits: cache responses in the run's working directory, and back off on HTTP 429.
- Map topics to Guardian filters in `config/topics.yaml`. Initial mapping (verify and tune):
  - géopolitique → section `world`, plus keywords (war, sanctions, diplomacy, NATO, election).
  - énergie → keywords (energy, electricity, gas, nuclear, renewables, grid, oil) within `business` / `environment`.
  - numérique → section `technology`, plus keywords (AI, digital, cyber, regulation, telecoms).
  - bonne-nouvelle → keyword search for good-news framing (e.g. "good news", breakthrough, recovery, record-low) and `tag` filters if they prove useful. This topic is best-effort in v1.

### 6.2 Le Monde (RSS)

- Use the official RSS feeds on `lemonde.fr`. Known example: `https://www.lemonde.fr/rss/une.xml`. Section feeds exist (e.g. international, économie). **Verify each feed URL works before relying on it** and record the verified URLs in `config/sources.yaml`.
- RSS provides title, summary, link, and date. Use those only. Do not fetch and republish article bodies.
- Map topics the same way: international → géopolitique; économie with energy keywords → énergie; a tech/numérique section or keywords → numérique.

### 6.3 Selection rules (`select.py`)

1. Normalize items: strip HTML, trim whitespace, parse dates to UTC.
2. Keep only items published in the last 24 hours (or since the previous successful run, whichever is shorter).
3. Assign each item to one topic (first match in the order above; keyword match takes precedence over section where they disagree).
4. **Dedupe**: merge items with the same canonical URL, or with highly similar titles (normalized token overlap above a threshold, tune in tests). Keep all outlets in the merged item.
5. **Rank** within each topic: prefer stories covered by more than one outlet, then recency.
6. Keep `max_items_per_topic` per topic.

Ranking should be deterministic and tested with fixtures. Do not use the LLM for ranking in v1.

## 7. Summarization (`summarize.py`)

- Provider: **Anthropic Claude API**. Model default: `claude-haiku-5-5` (configurable in `config/sources.yaml` as `llm.model`). Read the key from `ANTHROPIC_API_KEY`.
- Input per item: title, trail text / RSS summary, outlet, date, and URL. Nothing else.
- Output per item: one French title (`title_fr`) and one French summary of 1 to 2 sentences (`summary_fr`).
- **Grounding rules (mandatory in the prompt):**
  - Use only facts present in the input. Do not add context, numbers, names, or dates from memory.
  - If the input is insufficient, say so in the summary rather than guessing.
  - Keep names, figures, and dates exactly as in the source.
  - Write in neutral, factual French. No opinion, no adjectives that editorialize.
  - Output strict JSON so the pipeline can validate it. Reject and retry once on invalid JSON; then skip the item and log it.
- Cost control: batch items per topic into one request where possible; log token usage per run.
- Never send the Guardian API key or any secret to the model.

## 8. Audio and scheduling

### 8.1 TTS (`tts.py`)

- Engine: **Piper** (open source, runs offline on the GitHub Actions runner, no API cost). Install with pip in the workflow.
- Choose a French voice (candidates: `fr_FR` voices in the Piper voice list). Verify quality by listening to a sample before fixing the choice, and record the chosen voice in `config/sources.yaml` as `tts.voice`.
- Output: MP3 (encode with ffmpeg, available on the runner).
- Script structure (generated by `main.py`, not by the LLM):
  1. Intro: "Bonjour. Voici votre briefing du [date]."
  2. One section per topic: a short French topic title, then each story's `summary_fr` as its own sentence(s).
  3. Outro: "Les sources sont disponibles dans l'application."
- Target length: about 3 to 6 minutes.
- If a topic is empty: "Pas d'actualité retenue pour ce thème aujourd'hui."

### 8.2 Schedule

- The workflow runs **hourly** (`cron: "0 * * * *"`, UTC), plus `workflow_dispatch` for manual runs.
- Each run regenerates the briefing only if the current local date has no successful briefing yet, or if the previous run failed. Otherwise it exits early. (Public repos get free Actions minutes, so hourly runs are acceptable. Keep runs short.)
- This design means the latest briefing is ready before any wake time between about 04:00 and 10:00 Brussels, without needing to know the wake time in advance.
- The UTC cron does not adjust for daylight saving time. This is acceptable because the hourly schedule covers all local hours.
- GitHub may delay scheduled runs under load. The fallback in §9 covers that.

### 8.3 Wake-time configuration

- File: `config/wake.json`. Format: a map from date to wake time in local time.

```json
{
  "timezone": "Europe/Brussels",
  "wake_times": {
    "2026-11-21": "06:45",
    "2026-11-22": "07:30"
  }
}
```

- The owner edits this file the night before (via the GitHub web or mobile app, or by asking Claude to commit a change). Keep only future dates; old entries may be pruned by a commit.
- The pipeline does **not** depend on `wake.json` to build the briefing. It reads it only to write `wake_time` into `briefing.json` and to report if tomorrow's wake time is missing.
- The iPhone side uses `wake.json` to set the Clock alarm for the next day (see `shortcut/SHORTCUT.md`). The exact mechanism (a nightly Shortcut that sets a Clock alarm, and how the briefing Shortcut is triggered at that time) is **an open prototype item** and must be verified on a real phone before being documented as working.

## 9. Failure handling

- If a run fails at any step, do not publish a partial briefing. Keep the previous `briefing.json` and audio.
- If no fresh briefing exists for the current day when the workflow runs and the pipeline fails, republish yesterday's content with `status: "fallback"` and generate a short audio notice: "Le briefing d'aujourd'hui n'a pas pu être généré. Voici celui d'hier."
- Log every run to `docs/run-log.json`: timestamp, status, counts per source, token usage, errors. Keep the last 30 entries.
- Fail the workflow visibly (non-zero exit) so GitHub's failure notification reaches the owner.

## 10. Secrets and configuration

- GitHub repository secrets (never committed):
  - `GUARDIAN_API_KEY`
  - `ANTHROPIC_API_KEY`
- Non-secret configuration lives in `config/*.yaml` and `config/wake.json`.
- Local development: use a `.env` file, which is gitignored. Provide `.env.example` with variable names only.
- Never print secrets in logs. Mask them in the workflow.

## 11. Legal and content rules

- Publish only: French title, short French summary, outlet name, publication time, and the link to the original article.
- Never publish or store full article text. Use the body text only in memory for summarization, and drop it after the request.
- Every summary must link to its source. The app must not present content without attribution.
- Do not claim the content is "certified" or "verified". Describe it as a summary of the linked sources.
- Guardian content is licensed for non-commercial use. Keep this repo personal and non-commercial.

## 12. Coding conventions

- Python 3.12. Type hints everywhere. Dataclasses for models.
- Standard library first; add dependencies only when needed. Pin them in `requirements.txt`.
- No network calls in tests. Use saved fixtures under `tests/fixtures/`.
- Each source module exposes one function returning a list of normalized items, so sources can be tested in isolation.
- Logging via `logging`, not `print`.
- Keep `pipeline/main.py` thin; put logic in the modules.
- Commit messages: short imperative English, e.g. `Add Le Monde RSS source`.

## 13. Milestones

| # | Milestone | Done when |
|---|---|---|
| M0 | Repo skeleton, `CLAUDE.md`, GitHub Pages enabled, secrets set | `docs/briefing.json` with `status: "ok"` and no items is reachable from a phone browser |
| M1 | Guardian + Le Monde fetch, normalized items, saved fixtures and tests | `python -m pipeline.main --dry-run` prints items for both sources |
| M2 | Topic assignment, dedupe, ranking | Each topic has up to 4 items in fixtures and in a live dry run |
| M3 | French summaries via Claude API, grounded and validated | Summaries are French, linked, and rejected when invalid JSON |
| M4 | Piper TTS, MP3 generation, `briefing.json` published | A 3 to 6 minute French MP3 plays from the Pages URL |
| M5 | Scheduling, `wake.json`, fallback and run log | Hourly runs publish once per day; a forced failure republishes yesterday's briefing |
| M6 | iPhone Shortcut: fetch, play, story menu, open links | Works on a locked phone for five consecutive mornings |
| M7 | Nightly wake-time workflow on the phone | Tomorrow's wake time set the night before drives the Clock alarm |

M6 and M7 need a real iPhone to test. Do not mark them done based on simulation.

## 14. Open items to verify (do not assume)

1. Exact Le Monde feed URLs for international, économie, and any tech section. Verify each returns valid RSS.
2. Whether Le Soir offers a usable feed (out of scope until verified).
3. Chosen Piper French voice, after a listening test.
4. Guardian keyword/tag combinations that work for the good-news topic.
5. Whether the iPhone Shortcuts app can set a Clock alarm from a file fetched over HTTPS, and how a Shortcut plays audio on a locked screen.
6. Claude API pricing and token use per briefing, measured in M3.

## 15. How Claude should work in this repo

- Start by reading this file and `config/*`. Check the open items in §14 before implementing dependent code.
- Implement one milestone at a time. Keep changes small and tested.
- Do not add features beyond the milestone in progress.
- When unsure about a source's terms, a feed URL, or a voice's quality, say so and ask the owner rather than guessing.
- When a decision changes, update this file in the same commit.
