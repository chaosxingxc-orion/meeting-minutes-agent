from pathlib import Path

import pytest

from meeting_minutes_agent.probes.e4_xdomain_supply_v2 import (
    DISCOVERY_SIZE,
    RESERVE_SIZE,
    Earnings22AuditError,
    EntityMention,
    analyse_mentions,
    deterministic_split,
    load_entity_mentions,
)


HEADER = "token|speaker|ts|endTs|punctuation|prepunctuation|case|tags|oldTs|oldEndTs|ali_comment\n"
HEADER_WITH_WER_TAGS = "token|speaker|ts|endTs|punctuation|prepunctuation|case|tags|wer_tags|oldTs|oldEndTs|ali_comment\n"


def test_deterministic_split_has_frozen_sizes_and_is_order_independent():
    ids = [f"file-{index:03d}" for index in range(DISCOVERY_SIZE + RESERVE_SIZE)]
    first = deterministic_split(ids)
    second = deterministic_split(reversed(ids))
    assert first == second
    assert list(first.values()).count("discovery") == DISCOVERY_SIZE
    assert list(first.values()).count("reserve") == RESERVE_SIZE


def test_parser_reconstructs_multitoken_entity_and_rejects_schema_drift(tmp_path: Path):
    path = tmp_path / "m.aligned.nlp"
    path.write_text(
        HEADER
        + "New|1|91.0|91.2||||['7:ORG']|||\n"
        + "York|1|91.2|91.5||||['7:ORG']|||\n"
        + "today|1||||||['8:DATE']|||del\n",
        encoding="utf-8",
    )
    mentions = load_entity_mentions(path)
    assert mentions == (
        EntityMention("1", 91.0, "new york", "ORG"),
        EntityMention("1", None, "today", "DATE"),
    )
    path.write_text("bad|header\n", encoding="utf-8")
    with pytest.raises(Earnings22AuditError, match="header drift"):
        load_entity_mentions(path)


def test_parser_refuses_reused_noncontiguous_entity_id(tmp_path: Path):
    path = tmp_path / "m.aligned.nlp"
    path.write_text(
        HEADER
        + "Acme|1|1.0|||||['7:ORG']|||\n"
        + "paused|1|2.0|||||[]|||\n"
        + "Acme|1|3.0|||||['7:ORG']|||\n",
        encoding="utf-8",
    )
    with pytest.raises(Earnings22AuditError, match="non-contiguous entity id"):
        load_entity_mentions(path)


def test_parser_accepts_documented_wer_tags_header_variant(tmp_path: Path):
    path = tmp_path / "m.aligned.nlp"
    path.write_text(
        HEADER_WITH_WER_TAGS + "Acme|1|1.0|||||['7:ORG']|['7']|||\n",
        encoding="utf-8",
    )
    assert load_entity_mentions(path) == (EntityMention("1", 1.0, "acme", "ORG"),)


def test_carry_uses_prior_slices_and_separates_other_speakers():
    mentions = (
        EntityMention("A", 1.0, "acme", "ORG"),
        EntityMention("A", 2.0, "acme", "ORG"),  # same unit: deduplicated
        EntityMention("A", 91.0, "acme", "ORG"),  # exclusive carry
        EntityMention("B", 181.0, "acme", "ORG"),  # global only
        EntityMention("A", 271.0, "acme", "ORG"),  # shared carry
        EntityMention("A", None, "widget", "PRODUCT"),
        EntityMention("A", 1.0, "2026", "YEAR"),
    )
    result = analyse_mentions(mentions)
    assert result.candidate_units == 4
    assert result.exclusive_by_surface == {"acme": 1}
    assert result.same_speaker_carry == 2
    assert result.shared_carry == 1
    assert result.global_only_carry == 1
    assert result.excluded_unaligned_mentions == 1


def test_split_refuses_wrong_roster_size():
    with pytest.raises(Earnings22AuditError, match="125 unique"):
        deterministic_split(["only-one"])
