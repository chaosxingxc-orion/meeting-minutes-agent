from meeting_minutes_agent.state.material_retrieval import (
    MaterialBm25Index,
    retrieval_features,
    select_balanced_keys,
    summarize_signal,
    word_tokens,
)


def _meetings() -> list[dict[str, object]]:
    return [
        {
            "file_id": file_id,
            "candidates": [
                {
                    "canonical": f"{name}{index}",
                    "aliases": [f"{name}{index}"],
                    "category": "product",
                    "page": index,
                    "source_span": f"{name}{index} cloud platform",
                }
                for index in range(3)
            ],
        }
        for file_id, name in (("a", "Alpha"), ("b", "Beta"))
    ]


def test_features_exclude_short_acronym_fuzzing_and_generic_words() -> None:
    assert word_tokens("The OCF quarterly CloudFront update") == ("ocf", "cloudfront", "update")
    features = retrieval_features("OCF CloudFront")
    assert "w:ocf" in features
    assert not any(feature.startswith("c:") and "ocf" in feature for feature in features)
    assert "w:cloudfront" in features
    assert "c:clo" in features


def test_balanced_selection_and_bm25_recover_matching_material() -> None:
    keys = select_balanced_keys(_meetings(), width=2, salt="fixed")
    assert {key.file_id for key in keys} == {"a", "b"}
    assert sum(key.file_id == "a" for key in keys) == 2
    index = MaterialBm25Index(keys)
    alpha_key, alpha_score = index.best(retrieval_features("Alpha platform"), "a")
    _, beta_score = index.best(retrieval_features("Alpha platform"), "b")
    assert alpha_key.file_id == "a"
    assert alpha_score > beta_score


def test_signal_summary_treats_ties_as_non_wins() -> None:
    summary = summarize_signal(
        [
            {"correct_score": 2.0, "deranged_score": 1.0, "best_score": 2.0, "normalized_margin": 1 / 3},
            {"correct_score": 1.0, "deranged_score": 1.0, "best_score": 1.0, "normalized_margin": 0.0},
            {"correct_score": 0.0, "deranged_score": 0.0, "best_score": 0.0, "normalized_margin": 0.0},
        ]
    )
    assert summary["eligible_turns"] == 3
    assert summary["dispatched_turns"] == 2
    assert summary["correct_wins"] == 1
    assert summary["attribution_precision"] == 0.5
