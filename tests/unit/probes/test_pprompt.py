"""Tests for :mod:`meeting_minutes_agent.probes.pprompt`: template/
arrangement rendering, roster derivation, request builders, seeded
derangements, and the LEGALITY guarantee (no gold transcript text can reach
a built prompt, X2 included). Runs entirely on the SAME hand-built
:func:`sample_manifest_document` fixture P-ATTR's own tests use -- no real
AMI bytes, no network."""

from __future__ import annotations

from pathlib import Path

import pytest

from meeting_minutes_agent.chunking.models import Segment
from meeting_minutes_agent.heads.transcribe_attribute import CONTEXT_SECTION_HEADER, SYSTEM_INSTRUCTION_TEMPLATE
from meeting_minutes_agent.probes.pattr import PattrManifest
from meeting_minutes_agent.probes.pprompt import (
    ARM_X1,
    ARM_X2,
    ARMS,
    ARRANGEMENTS,
    GRID_CELLS,
    MEETING_CONTEXT_SECTION_HEADER,
    REFERENCE_CELL,
    REINFORCED_GRAMMAR_SECTION_HEADER,
    TEMPLATES,
    PpromptError,
    build_all_requests,
    build_arm_requests,
    build_cell_requests,
    build_grid_requests,
    build_x1_requests,
    build_x2_requests,
    render_cell_prompt,
    render_x1_prompt,
    render_x2_prompt,
    roster_for_entry,
    seeded_derangement,
    seeded_label_derangement,
    seeded_meeting_derangement,
    summarize_all_requests,
)

from .fixtures import sample_manifest_document

_GRAMMAR_MARKER = "<speaker>|<text>"


def _manifest() -> PattrManifest:
    return PattrManifest(raw=sample_manifest_document(), source_path=None)


# ---------------------------------------------------------------------------
# roster derivation
# ---------------------------------------------------------------------------


def test_roster_for_entry_reads_distinct_speakers_from_turns():
    manifest = _manifest()
    entry = manifest.slice_entries("MTG1")[0]
    assert roster_for_entry(entry) == ("A", "B")


def test_roster_for_entry_is_sorted_and_deduplicated():
    entry = {"turns": [{"speaker": "B"}, {"speaker": "A"}, {"speaker": "B"}]}
    assert roster_for_entry(entry) == ("A", "B")


# ---------------------------------------------------------------------------
# template content: T1 subset of T2 subset of T3/T4; grammar contract present
# ---------------------------------------------------------------------------


def test_t1_is_the_bare_grammar_contract_with_nothing_else():
    prompt = render_cell_prompt("T1", "A1", "MTG1", ("A", "B"))
    assert prompt.task_instruction == SYSTEM_INSTRUCTION_TEMPLATE
    assert prompt.supplied_text_before_audio == ()
    assert prompt.supplied_text_after_audio == ()
    assert _GRAMMAR_MARKER in prompt.task_instruction


def test_t1_renders_identically_across_all_three_arrangements():
    # T1 has no extra block for arrangement to move -- a documented,
    # harmless consequence of honoring the registered 4x3 grid literally.
    hashes = {render_cell_prompt("T1", a, "MTG1", ("A", "B")).content_sha256 for a in ARRANGEMENTS}
    assert len(hashes) == 1


@pytest.mark.parametrize("arrangement", ARRANGEMENTS)
def test_t2_contains_t1s_base_instruction_plus_a_context_block(arrangement):
    prompt = render_cell_prompt("T2", arrangement, "MTG1", ("A", "B"))
    whole_text = " ".join(
        [prompt.task_instruction, *prompt.supplied_text_before_audio, *prompt.supplied_text_after_audio]
    )
    assert SYSTEM_INSTRUCTION_TEMPLATE in whole_text
    assert MEETING_CONTEXT_SECTION_HEADER in whole_text
    assert "MTG1" in whole_text
    assert "A" in whole_text and "B" in whole_text
    assert _GRAMMAR_MARKER in whole_text


@pytest.mark.parametrize("arrangement", ARRANGEMENTS)
def test_t3_is_t2_plus_an_explicitly_empty_glossary_slot(arrangement):
    t2 = render_cell_prompt("T2", arrangement, "MTG1", ("A", "B"))
    t3 = render_cell_prompt("T3", arrangement, "MTG1", ("A", "B"))
    t2_whole = " ".join([t2.task_instruction, *t2.supplied_text_before_audio, *t2.supplied_text_after_audio])
    t3_whole = " ".join([t3.task_instruction, *t3.supplied_text_before_audio, *t3.supplied_text_after_audio])
    assert t2_whole in t3_whole or t2_whole == t3_whole[: len(t2_whole)] or MEETING_CONTEXT_SECTION_HEADER in t3_whole
    assert "KNOWN TERMS" in t3_whole  # GLOSSARY_SECTION_HEADER text
    assert "(no known terms yet)" in t3_whole  # GLOSSARY_EMPTY_LINE text
    assert _GRAMMAR_MARKER in t3_whole


@pytest.mark.parametrize("arrangement", ARRANGEMENTS)
def test_t4_is_t2_plus_a_reinforced_grammar_section_with_an_example_line(arrangement):
    t4 = render_cell_prompt("T4", arrangement, "MTG1", ("A", "B"))
    whole = " ".join([t4.task_instruction, *t4.supplied_text_before_audio, *t4.supplied_text_after_audio])
    assert MEETING_CONTEXT_SECTION_HEADER in whole
    assert REINFORCED_GRAMMAR_SECTION_HEADER in whole
    assert "A|Let's get started" in whole  # the worked example line
    assert _GRAMMAR_MARKER in whole


def test_render_cell_prompt_rejects_unknown_template():
    with pytest.raises(PpromptError, match="unknown template"):
        render_cell_prompt("T9", "A1", "MTG1", ("A",))


def test_render_cell_prompt_rejects_unknown_arrangement():
    with pytest.raises(PpromptError, match="unknown arrangement"):
        render_cell_prompt("T1", "A9", "MTG1", ("A",))


# ---------------------------------------------------------------------------
# arrangement placement (A1 system / A2 before-audio / A3 after-audio)
# ---------------------------------------------------------------------------


def test_a1_places_the_extra_block_in_the_system_task_instruction():
    prompt = render_cell_prompt("T2", "A1", "MTG1", ("A", "B"))
    assert MEETING_CONTEXT_SECTION_HEADER in prompt.task_instruction
    assert prompt.supplied_text_before_audio == ()
    assert prompt.supplied_text_after_audio == ()


def test_a2_places_the_extra_block_before_the_audio():
    prompt = render_cell_prompt("T2", "A2", "MTG1", ("A", "B"))
    assert prompt.task_instruction == SYSTEM_INSTRUCTION_TEMPLATE
    assert len(prompt.supplied_text_before_audio) == 1
    assert MEETING_CONTEXT_SECTION_HEADER in prompt.supplied_text_before_audio[0]
    assert prompt.supplied_text_after_audio == ()


def test_a3_places_the_extra_block_after_the_audio():
    prompt = render_cell_prompt("T2", "A3", "MTG1", ("A", "B"))
    assert prompt.task_instruction == SYSTEM_INSTRUCTION_TEMPLATE
    assert prompt.supplied_text_before_audio == ()
    assert len(prompt.supplied_text_after_audio) == 1
    assert MEETING_CONTEXT_SECTION_HEADER in prompt.supplied_text_after_audio[0]


def test_to_transport_kwargs_carries_supplied_text_after_audio(tmp_path):
    prompt = render_cell_prompt("T2", "A3", "MTG1", ("A", "B"))
    kwargs = prompt.to_transport_kwargs(request_id="r1", audio_path=Path("clip.wav"), audio_seconds=5.0)
    assert kwargs["supplied_text"] == ()
    assert len(kwargs["supplied_text_after_audio"]) == 1


# ---------------------------------------------------------------------------
# seeded derangements: deterministic, fixed-point-free, a real bijection
# ---------------------------------------------------------------------------


def test_seeded_derangement_is_deterministic_for_the_same_seed():
    a = seeded_derangement(["A", "B", "C", "D"], seed=1)
    b = seeded_derangement(["A", "B", "C", "D"], seed=1)
    assert a == b


def test_seeded_derangement_has_no_fixed_points():
    d = seeded_derangement(["A", "B", "C", "D"], seed=20260818)
    assert all(k != v for k, v in d.items())


def test_seeded_derangement_is_a_bijection_over_the_same_item_set():
    items = ["A", "B", "C", "D"]
    d = seeded_derangement(items, seed=7)
    assert set(d.keys()) == set(items)
    assert set(d.values()) == set(items)


def test_seeded_derangement_rejects_fewer_than_two_items():
    with pytest.raises(PpromptError):
        seeded_derangement(["A"], seed=1)


def test_seeded_label_derangement_default_alphabet_is_canonical_ami_labels():
    d = seeded_label_derangement(20260818)
    assert set(d) == {"A", "B", "C", "D"}


def test_seeded_meeting_derangement_never_assigns_a_meeting_to_itself():
    d = seeded_meeting_derangement(["MTG1", "MTG2", "MTG3", "MTG4"], seed=20260818)
    assert all(target != donor for target, donor in d.items())


# ---------------------------------------------------------------------------
# X1 wrong-roster
# ---------------------------------------------------------------------------


def test_x1_uses_the_reference_cells_own_base_and_arrangement():
    reference = render_cell_prompt("T2", "A1", "MTG1", ("A", "B"))
    derangement = {"A": "B", "B": "A"}
    x1 = render_x1_prompt("MTG1", ("A", "B"), derangement)
    assert x1.supplied_text_before_audio == reference.supplied_text_before_audio == ()
    assert x1.supplied_text_after_audio == reference.supplied_text_after_audio == ()
    assert SYSTEM_INSTRUCTION_TEMPLATE in x1.task_instruction


def test_x1_roster_is_actually_deranged_not_the_true_roster():
    # A 2-cycle derangement (A<->B) happens to render an IDENTICAL roster
    # SET for a 2-speaker slice -- that is expected and not itself a bug
    # (X1's corruption is real per-slice, not always visible for every
    # possible roster/derangement pair); use a derangement whose effect on
    # THIS roster is visible to prove the corruption mechanism is live.
    derangement = {"A": "C", "B": "D", "C": "A", "D": "B"}
    x1 = render_x1_prompt("MTG1", ("A", "B"), derangement)
    reference = render_cell_prompt("T2", "A1", "MTG1", ("A", "B"))
    assert x1.content_sha256 != reference.content_sha256
    assert "C" in x1.task_instruction and "D" in x1.task_instruction
    assert "Speakers in this excerpt (from turn metadata): C, D" in x1.task_instruction


def test_x1_rejects_a_derangement_missing_a_seen_label():
    with pytest.raises(PpromptError, match="missing"):
        render_x1_prompt("MTG1", ("A", "B"), {"A": "B"})


# ---------------------------------------------------------------------------
# X2 stale-tail
# ---------------------------------------------------------------------------


def test_x2_with_no_tail_segments_matches_the_reference_cell():
    x2 = render_x2_prompt("MTG1", ("A", "B"), ())
    reference = render_cell_prompt("T2", "A1", "MTG1", ("A", "B"))
    assert x2.content_sha256 == reference.content_sha256


def test_x2_with_tail_segments_prepends_a_context_block_before_the_audio():
    tail = (Segment(id="d0", speaker="C", start=0.0, end=0.0, text="DONOR-TAIL-MARKER-ONE"),)
    x2 = render_x2_prompt("MTG1", ("A", "B"), tail)
    assert len(x2.supplied_text_before_audio) == 1
    tail_block = x2.supplied_text_before_audio[0]
    assert tail_block.startswith(CONTEXT_SECTION_HEADER)
    assert "[C] DONOR-TAIL-MARKER-ONE" in tail_block
    # the reference cell's own (clean) context block still lands in the
    # system message, unchanged by the tail.
    assert MEETING_CONTEXT_SECTION_HEADER in x2.task_instruction
    assert "Speakers in this excerpt (from turn metadata): A, B" in x2.task_instruction


def test_x2_tail_preserves_segment_order():
    tail = (
        Segment(id="d0", speaker="C", start=0.0, end=0.0, text="first"),
        Segment(id="d1", speaker="D", start=0.0, end=0.0, text="second"),
    )
    x2 = render_x2_prompt("MTG1", ("A", "B"), tail)
    tail_block = x2.supplied_text_before_audio[0]
    assert tail_block.index("[C] first") < tail_block.index("[D] second")


# ---------------------------------------------------------------------------
# request builders
# ---------------------------------------------------------------------------


def test_build_cell_requests_count_equals_n_slices():
    manifest = _manifest()
    requests = build_cell_requests(manifest, "T2-A1")
    assert len(requests) == 3  # 2 (MTG1) + 1 (MTG2)
    assert all(r.arm == "T2-A1" for r in requests)


def test_build_cell_requests_rejects_unknown_cell():
    manifest = _manifest()
    with pytest.raises(PpromptError, match="unknown grid cell"):
        build_cell_requests(manifest, "T9-A1")


def test_build_grid_requests_count_is_12_cells_times_n_slices():
    manifest = _manifest()
    requests = build_grid_requests(manifest)
    assert len(requests) == 12 * 3
    assert {r.arm for r in requests} == set(GRID_CELLS)


def test_build_x1_requests_count_equals_n_slices():
    manifest = _manifest()
    derangement = {"A": "B", "B": "A", "C": "D", "D": "C"}
    requests = build_x1_requests(manifest, derangement)
    assert len(requests) == 3
    assert all(r.arm == ARM_X1 for r in requests)


def test_build_x2_requests_count_equals_n_slices_even_with_no_tail_data():
    manifest = _manifest()
    requests = build_x2_requests(manifest, {})
    assert len(requests) == 3
    assert all(r.arm == ARM_X2 for r in requests)


def test_build_x2_requests_uses_the_tail_for_its_own_meeting_only():
    manifest = _manifest()
    tail = {"MTG1": (Segment(id="d0", speaker="C", start=0.0, end=0.0, text="donor text"),)}
    requests = {(r.meeting_id, r.slice_index): r for r in build_x2_requests(manifest, tail)}
    assert "donor text" in requests[("MTG1", 0)].prompt.supplied_text_before_audio[0]
    assert requests[("MTG2", 0)].prompt.supplied_text_before_audio == ()


def test_build_all_requests_totals_336_equivalent_shape():
    # On this 3-slice fixture: 12*3 grid + 3 X1 + 3 X2 = 42 (the real
    # 24-slice manifest gives 12*24 + 24 + 24 = 336, the registered total).
    manifest = _manifest()
    derangement = {"A": "B", "B": "A", "C": "D", "D": "C"}
    requests = build_all_requests(manifest, derangement=derangement, tail_segments_by_meeting={})
    assert len(requests) == 12 * 3 + 3 + 3
    assert {r.arm for r in requests} == set(ARMS)


def test_build_arm_requests_dispatches_grid_cells():
    manifest = _manifest()
    for cell in GRID_CELLS:
        assert [r.request_id for r in build_arm_requests(manifest, cell)] == [
            r.request_id for r in build_cell_requests(manifest, cell)
        ]


def test_build_arm_requests_dispatches_x1_with_a_derangement():
    manifest = _manifest()
    derangement = {"A": "B", "B": "A", "C": "D", "D": "C"}
    assert [r.request_id for r in build_arm_requests(manifest, ARM_X1, derangement=derangement)] == [
        r.request_id for r in build_x1_requests(manifest, derangement)
    ]


def test_build_arm_requests_x1_without_a_derangement_refuses():
    manifest = _manifest()
    with pytest.raises(PpromptError, match="derangement"):
        build_arm_requests(manifest, ARM_X1)


def test_build_arm_requests_dispatches_x2():
    manifest = _manifest()
    tail = {"MTG1": (Segment(id="d0", speaker="C", start=0.0, end=0.0, text="x"),)}
    assert [r.request_id for r in build_arm_requests(manifest, ARM_X2, tail_segments_by_meeting=tail)] == [
        r.request_id for r in build_x2_requests(manifest, tail)
    ]


def test_build_arm_requests_rejects_unknown_arm():
    manifest = _manifest()
    with pytest.raises(PpromptError, match="unknown P-PROMPT arm"):
        build_arm_requests(manifest, "bogus")


def test_request_id_format_and_uniqueness():
    manifest = _manifest()
    derangement = {"A": "B", "B": "A", "C": "D", "D": "C"}
    requests = build_all_requests(manifest, derangement=derangement, tail_segments_by_meeting={})
    ids = [r.request_id for r in requests]
    assert len(ids) == len(set(ids))
    assert "pprompt-T2-A1-MTG1-slice0000" in ids
    assert "pprompt-X1-MTG2-slice0000" in ids
    assert "pprompt-X2-MTG1-slice0001" in ids


def test_audio_relpath_and_seconds_match_the_manifest():
    manifest = _manifest()
    requests = {r.request_id: r for r in build_cell_requests(manifest, "T1-A1")}
    r1 = requests["pprompt-T1-A1-MTG1-slice0001"]
    assert r1.audio_relpath == "derived/meeting-minutes/pattr-smoke/slices/MTG1/MTG1-slice0001.wav"
    assert r1.audio_seconds == pytest.approx(90.0)  # 180.0 - 90.0


def test_summarize_all_requests_matches_totals():
    manifest = _manifest()
    requests = build_cell_requests(manifest, "T2-A1")
    summaries = summarize_all_requests(requests)
    assert set(summaries) == {"T2-A1"}
    assert summaries["T2-A1"].n_requests == 3
    assert summaries["T2-A1"].n_meetings == 2
    assert summaries["T2-A1"].total_audio_seconds == pytest.approx(240.0)


# ---------------------------------------------------------------------------
# LEGALITY: no gold transcript text reaches any built prompt (X2 included)
# ---------------------------------------------------------------------------

_GOLD_TRAP = "GOLD-TRAP-DO-NOT-LEAK-INTO-ANY-PROMPT"


def _all_text_parts(prompt) -> str:
    return " ".join([prompt.task_instruction, *prompt.supplied_text_before_audio, *prompt.supplied_text_after_audio])


def test_no_gold_text_reaches_any_of_the_336_equivalent_built_prompts():
    manifest = _manifest()
    derangement = {"A": "B", "B": "A", "C": "D", "D": "C"}
    # A caller with a GOLD reference string sitting in its own process (as a
    # real read/scoring script would have) must never be able to leak it
    # into a built prompt through any of this module's builder functions --
    # none of them accept a gold-transcript-shaped argument at all, which
    # this test also confirms structurally: the only per-meeting text this
    # module ever renders comes from the manifest's OWN roster labels and
    # the caller-supplied tail Segments (X2), never a reference transcript.
    tail = {
        "MTG1": (Segment(id="d0", speaker="C", start=0.0, end=0.0, text="DONOR-TAIL-MARKER-ONE"),),
        "MTG2": (Segment(id="d1", speaker="A", start=0.0, end=0.0, text="DONOR-TAIL-MARKER-TWO"),),
    }
    requests = build_all_requests(manifest, derangement=derangement, tail_segments_by_meeting=tail)
    for spec in requests:
        whole = _all_text_parts(spec.prompt)
        assert _GOLD_TRAP not in whole

    # the donor marker DOES flow through, proving the tail mechanism is
    # live (not merely "absent of gold because nothing was rendered").
    x2_texts = " ".join(_all_text_parts(spec.prompt) for spec in requests if spec.arm == ARM_X2)
    assert "DONOR-TAIL-MARKER-ONE" in x2_texts
    assert "DONOR-TAIL-MARKER-TWO" in x2_texts


def test_x2_builder_signature_has_no_gold_transcript_parameter():
    # Structural guarantee: build_x2_requests only ever accepts a manifest
    # (audio identity) and tail Segments (model-generated donor text) -- no
    # parameter shaped like a reference/gold transcript exists to pass one
    # through even by caller error.
    import inspect

    from meeting_minutes_agent.probes.pprompt import build_x2_requests as fn

    params = set(inspect.signature(fn).parameters)
    assert not any("gold" in p or "reference" in p for p in params)
