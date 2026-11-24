import json
from datetime import datetime, timezone

import pipeline.main
from pipeline.config import load_config
from pipeline.main import build_briefing, main
from pipeline.models import TOPIC_ORDER, Briefing, BriefingItem, NewsItem, Topic
from pipeline.publish import write_briefing
from pipeline.sources import SourceResult


def test_config_loads_with_topics_in_contract_order() -> None:
    config = load_config()
    assert tuple(t["id"] for t in config.topics) == TOPIC_ORDER
    assert config.max_items_per_topic == 4


def test_empty_briefing_matches_contract() -> None:
    now = datetime(2026, 11, 20, 23, 30, tzinfo=timezone.utc)
    data = build_briefing(now).to_dict()
    assert data["schema_version"] == 1
    assert data["date"] == "2026-11-21"  # 00:30 in Brussels
    assert data["generated_at"] == "2026-11-20T23:30:00Z"
    assert data["status"] == "ok"
    assert [t["id"] for t in data["topics"]] == list(TOPIC_ORDER)
    assert all(t["items"] == [] for t in data["topics"])


def test_topics_are_emitted_in_contract_order_and_items_serialize() -> None:
    item = BriefingItem(
        title_fr="Titre",
        summary_fr="Résumé.",
        outlet="Le Monde",
        published_at=datetime(2026, 11, 20, 18, 12, tzinfo=timezone.utc),
        source_url="https://www.lemonde.fr/x",
    )
    briefing = Briefing(
        date=datetime(2026, 11, 21).date(),
        generated_at=datetime(2026, 11, 21, 4, tzinfo=timezone.utc),
        timezone="Europe/Brussels",
        status="ok",
        audio_url="briefing-2026-11-21.mp3",
        topics=[Topic("numerique", "Numérique", [item]), Topic("geopolitique", "Géopolitique")],
    )
    data = briefing.to_dict()
    assert [t["id"] for t in data["topics"]] == ["geopolitique", "numerique"]
    assert data["topics"][1]["items"][0]["published_at"] == "2026-11-20T18:12:00Z"


def test_write_briefing_is_valid_utf8_json(tmp_path) -> None:
    briefing = build_briefing(datetime(2026, 11, 21, 4, tzinfo=timezone.utc))
    path = write_briefing(briefing, tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["topics"][1]["title"] == "Énergie"
    assert list(tmp_path.iterdir()) == [path]  # no temp files left behind


def test_dry_run_prints_items_and_writes_nothing(tmp_path, capsys, monkeypatch) -> None:
    item = NewsItem(
        title="Exemple de titre",
        summary="Résumé.",
        url="https://www.lemonde.fr/x",
        outlet="Le Monde",
        published_at=datetime(2026, 11, 24, 18, 0, tzinfo=timezone.utc),
        section="international",
    )
    fake = [SourceResult("The Guardian", error="GUARDIAN_API_KEY is not set"), SourceResult("Le Monde", [item])]
    monkeypatch.setattr(pipeline.main, "fetch_all", lambda *a, **k: fake)

    assert main(["--dry-run", "--docs-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "== The Guardian: FAILED (GUARDIAN_API_KEY is not set)" in out
    assert "== Le Monde: 1 items" in out
    assert "2026-11-24 18:00Z  international  Exemple de titre" in out
    assert list(tmp_path.iterdir()) == []


def test_dry_run_fails_when_every_source_fails(monkeypatch) -> None:
    fake = [SourceResult("The Guardian", error="x"), SourceResult("Le Monde", error="y")]
    monkeypatch.setattr(pipeline.main, "fetch_all", lambda *a, **k: fake)
    assert main(["--dry-run"]) == 1
