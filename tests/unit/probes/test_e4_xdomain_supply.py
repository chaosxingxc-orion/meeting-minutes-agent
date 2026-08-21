from pathlib import Path

from meeting_minutes_agent.probes.e4_xdomain_supply import (
    CorpusInput,
    MeetingCounts,
    Segment,
    analyse_meeting,
    build_input_manifest,
    choose_decision,
    extract_candidates,
    summarise_domain,
)


def test_candidate_extraction_is_conservative_and_segment_deduplicated():
    candidates = extract_candidates("Morgan met Morgan about XML and H2O. London replied. Later Ada agreed.")
    assert candidates == {
        "morgan": "name_like",
        "xml": "strict_technical",
        "h2o": "strict_technical",
        "ada": "name_like",
    }


def test_carry_separates_speaker_exclusive_shared_and_global_only():
    result = analyse_meeting(
        "m1",
        (
            Segment("A", "We asked Morgan about XML."),
            Segment("A", "Then Morgan revised XML."),
            Segment("B", "I mentioned Morgan and H2O."),
            Segment("B", "Later XML and H2O returned."),
            Segment("A", "Again Morgan reviewed XML."),
        ),
    )
    assert result.exclusive_by_surface == {"morgan": 1, "xml": 1, "h2o": 1}
    assert result.shared_carry == 2
    assert result.global_only_carry == 2
    assert result.strict_exclusive_carry == 2
    assert result.eligible


def _meeting(index: int, exclusive: int, strict: int = 1) -> MeetingCounts:
    return MeetingCounts(
        meeting_id=f"m{index}", segments=2, candidate_units=exclusive + 1,
        strict_candidate_units=strict, same_speaker_carry=exclusive, shared_carry=0,
        global_only_carry=0, exclusive_by_surface={f"term{index}-{j}": 1 for j in range(exclusive)},
        strict_exclusive_carry=strict,
    )


def test_domain_gates_and_ordered_decision():
    passing = summarise_domain("Product", [_meeting(index, 5) for index in range(20)])
    failing = summarise_domain("Academic", [_meeting(index, 1, 0) for index in range(20)])
    assert passing["passes"] is True
    assert failing["passes"] is False
    assert choose_decision({"Product": passing, "Academic": passing}) == "XDOMAIN-SUPPLY-FEASIBLE"
    assert choose_decision({"Product": passing, "Academic": failing}) == "DOMAIN-LIMITED-SUPPLY"
    assert choose_decision({"Product": failing, "Academic": failing}) == "INSUFFICIENT-XDOMAIN-SUPPLY"


def test_manifest_contains_hashes_not_transcript_text(tmp_path: Path):
    qmsum = tmp_path / "qmsum"
    transcript = qmsum / "data" / "Product" / "train" / "M1.json"
    transcript.parent.mkdir(parents=True)
    transcript.write_text('{"meeting_transcripts": []}', encoding="utf-8")
    audio = tmp_path / "M1.wav"
    audio.write_bytes(b"RIFF")
    manifest = build_input_manifest((CorpusInput("Product", "M1", transcript, audio),), qmsum)
    assert manifest["inputs"][0]["transcript"] == "data/Product/train/M1.json"
    assert "meeting_transcripts" not in str(manifest)
    assert len(manifest["inputs"][0]["transcript_sha256"]) == 64
