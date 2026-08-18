"""End-to-end wiring test: MeetingQA loader -> qa head -> metrics.qa scorer,
entirely on the tiny synthetic fixture and with ZERO model contact (a raw
reply string stands in for what a model would have said, exactly the
"failures as data" contract :func:`~meeting_minutes_agent.heads.qa.parse_qa_response`
gives every caller). This is the shape a future G1 Z-qa harness run wires
for real: :func:`~meeting_minutes_agent.corpora.meetingqa.loader.load_split`
supplies ``(question, reference answer_spans, audio_path)`` per example,
:func:`~meeting_minutes_agent.heads.qa.build_qa_request` turns the question
into a request, a (here: simulated) reply is parsed by
:func:`~meeting_minutes_agent.heads.qa.parse_qa_response` into prediction
spans, and :mod:`meeting_minutes_agent.metrics.qa` scores reference against
prediction."""

from __future__ import annotations

from meeting_minutes_agent.heads.qa import QUESTION_SECTION_HEADER, build_qa_request, parse_qa_response
from meeting_minutes_agent.metrics.qa import QAExample, score_example, score_qa_examples

from .fixtures import (
    DEV_FALLBACK_ID,
    DEV_MULTI_SPAN_ID,
    DEV_SINGLE_SPAN_ID,
    DEV_UNANSWERABLE_ID,
    build_tiny_ami_audio_tree,
    build_tiny_meetingqa_release,
)
from meeting_minutes_agent.corpora.meetingqa.loader import load_split


def _load_dev(tmp_path):
    meetingqa_root = tmp_path / "meetingqa"
    ami_root = tmp_path / "ami"
    build_tiny_meetingqa_release(meetingqa_root)
    build_tiny_ami_audio_tree(ami_root)
    return {ex.example_id: ex for ex in load_split(meetingqa_root=meetingqa_root, ami_root=ami_root, split="dev")}


def test_build_qa_request_carries_the_loaded_question(tmp_path):
    dev = _load_dev(tmp_path)
    ex = dev[DEV_SINGLE_SPAN_ID]

    req = build_qa_request(question=ex.question)

    assert req.supplied_text[-1] == f"{QUESTION_SECTION_HEADER}\n{ex.question}"


def test_exact_answer_reply_scores_perfect_f1_and_iou(tmp_path):
    dev = _load_dev(tmp_path)
    ex = dev[DEV_SINGLE_SPAN_ID]
    assert ex.audio_path.is_file()  # the request would be dispatched over real bytes

    build_qa_request(question=ex.question)  # exercises the request-building half of the wire
    simulated_reply = f"ANSWER: {ex.answer_spans[0]}"
    parsed = parse_qa_response(simulated_reply)
    assert parsed.parse_mode == "strict"

    score = score_example(QAExample(example_id=ex.example_id, reference_spans=ex.answer_spans, prediction_spans=parsed.answer_spans))
    assert score.f1 == 1.0
    assert score.iou == 1.0
    assert score.is_unanswerable is False
    assert score.is_abstention is False


def test_unanswerable_example_correctly_abstained_when_model_abstains(tmp_path):
    dev = _load_dev(tmp_path)
    ex = dev[DEV_UNANSWERABLE_ID]

    parsed = parse_qa_response("ABSTAIN")
    assert parsed.answer_spans == ()

    score = score_example(QAExample(example_id=ex.example_id, reference_spans=ex.answer_spans, prediction_spans=parsed.answer_spans))
    assert score.correctly_abstained is True
    assert score.falsely_abstained is False
    assert score.f1 == 1.0


def test_unanswerable_example_falsely_answered_is_scored_as_a_false_abstention_miss(tmp_path):
    dev = _load_dev(tmp_path)
    ex = dev[DEV_UNANSWERABLE_ID]

    # the model answers anyway, despite the question being unanswerable
    parsed = parse_qa_response("ANSWER: Paris")
    score = score_example(QAExample(example_id=ex.example_id, reference_spans=ex.answer_spans, prediction_spans=parsed.answer_spans))
    assert score.is_unanswerable is True
    assert score.is_abstention is False
    assert score.correctly_abstained is False
    assert score.f1 == 0.0


def test_multi_span_reply_matching_both_spans_scores_perfect(tmp_path):
    dev = _load_dev(tmp_path)
    ex = dev[DEV_MULTI_SPAN_ID]
    assert len(ex.answer_spans) == 2

    simulated_reply = "\n".join(f"ANSWER: {span}" for span in ex.answer_spans)
    parsed = parse_qa_response(simulated_reply)
    assert parsed.parse_mode == "strict"
    assert len(parsed.answer_spans) == 2

    score = score_example(QAExample(example_id=ex.example_id, reference_spans=ex.answer_spans, prediction_spans=parsed.answer_spans))
    assert score.is_multi_span is True
    assert score.f1 == 1.0
    assert score.iou == 1.0


def test_multi_span_reply_missing_one_span_scores_partial_credit(tmp_path):
    dev = _load_dev(tmp_path)
    ex = dev[DEV_MULTI_SPAN_ID]

    simulated_reply = f"ANSWER: {ex.answer_spans[0]}"  # model only found the first span
    parsed = parse_qa_response(simulated_reply)

    score = score_example(QAExample(example_id=ex.example_id, reference_spans=ex.answer_spans, prediction_spans=parsed.answer_spans))
    assert 0.0 < score.f1 < 1.0
    assert 0.0 < score.iou < 1.0


def test_malformed_reply_never_raises_and_scores_as_an_abstention_shape(tmp_path):
    dev = _load_dev(tmp_path)
    ex = dev[DEV_SINGLE_SPAN_ID]

    parsed = parse_qa_response("the model rambled without using the required grammar")
    assert parsed.parse_mode == "failed"
    assert parsed.answer_spans == ()

    # a caller CAN still feed a failed parse into the scorer (it is
    # structurally identical to an abstention) -- this documents that the
    # caller, not the head or the scorer, must decide whether "failed"
    # should be excluded from a report rather than counted as a miss.
    score = score_example(QAExample(example_id=ex.example_id, reference_spans=ex.answer_spans, prediction_spans=parsed.answer_spans))
    assert score.is_abstention is True
    assert score.falsely_abstained is True


def test_full_split_wires_end_to_end_through_the_pooled_report(tmp_path):
    dev = _load_dev(tmp_path)

    # one simulated reply per example: exact answers for answerable
    # examples, a genuine ABSTAIN for the unanswerable one.
    simulated_replies = {
        DEV_SINGLE_SPAN_ID: "\n".join(f"ANSWER: {s}" for s in dev[DEV_SINGLE_SPAN_ID].answer_spans),
        DEV_MULTI_SPAN_ID: "\n".join(f"ANSWER: {s}" for s in dev[DEV_MULTI_SPAN_ID].answer_spans),
        DEV_UNANSWERABLE_ID: "ABSTAIN",
        DEV_FALLBACK_ID: "\n".join(f"ANSWER: {s}" for s in dev[DEV_FALLBACK_ID].answer_spans),
    }

    examples = []
    for example_id, ex in dev.items():
        build_qa_request(question=ex.question)  # request-building half, exercised for every example
        parsed = parse_qa_response(simulated_replies[example_id])
        examples.append(QAExample(example_id=example_id, reference_spans=ex.answer_spans, prediction_spans=parsed.answer_spans))

    report = score_qa_examples(examples)
    assert report.n_examples == 4
    assert report.macro_f1 == 1.0
    assert report.macro_iou == 1.0
    assert report.n_unanswerable == 1
    assert report.abstention_accuracy == 1.0
    assert report.n_answerable == 3
    assert report.false_abstention_rate == 0.0
    assert report.n_multi_span == 1
    assert report.multi_span_macro_f1 == 1.0
