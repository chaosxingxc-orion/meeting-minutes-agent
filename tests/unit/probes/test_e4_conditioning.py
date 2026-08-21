from __future__ import annotations

from meeting_minutes_agent.probes.e4_conditioning import ARMS, E4Manifest, E4Target, build_head_request, build_requests


def _target() -> E4Target:
    return E4Target("D1", 2, "speaker_1", 20, 30, "Hydro Dent launched", ("Hydro Dent",), "Hydro dent launched", ("Hydro Dent",), ("Acme",), ("Other",), ("Hdyro Dnet",), "x.tar", "./D1.wav", "0" * 64)


def test_semantic_arms_have_equal_term_counts_and_same_instruction():
    target = _target(); heads = [build_head_request(target, arm) for arm in ARMS]
    assert len({head.task_instruction for head, _ in heads}) == 1
    assert heads[0][0].supplied_text == ()
    assert "speaker_1" in heads[1][0].supplied_text[0]
    assert {len(terms) for _, terms in heads[2:]} == {1}


def test_requests_are_complete_and_latin_rotated():
    target2 = E4Target(**{**_target().__dict__, "uniq_id": "D2"})
    requests = build_requests(E4Manifest({"content_hash": "x"}, (_target(), target2)))
    assert len(requests) == 12
    assert [x.arm for x in requests[:6]] == list(ARMS)
    assert [x.arm for x in requests[6:12]] == list(ARMS[1:] + ARMS[:1])
