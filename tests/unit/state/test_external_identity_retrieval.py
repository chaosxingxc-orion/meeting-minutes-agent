from meeting_minutes_agent.state.external_identity_retrieval import contains_identity, trigger_identity


def test_contains_identity_normalizes_case_and_diacritics() -> None:
    assert contains_identity("Results from JERÓNIMO MARTINS improved.", ("Jeronimo Martins",))


def test_exact_identity_does_not_trigger_correction() -> None:
    assert trigger_identity("Welcome to the TeamViewer call.", "TeamViewer", ("TeamViewer",)) is None


def test_fuzzy_identity_requests_canonical_surface() -> None:
    trigger = trigger_identity("Welcome to the TeamVewer call.", "TeamViewer", ("TeamViewer",), 0.75)
    assert trigger is not None
    assert trigger.canonical == "TeamViewer"
    assert trigger.observed_surface == "teamvewer"


def test_unrelated_text_does_not_trigger() -> None:
    assert trigger_identity("Revenue grew strongly.", "Galp", ("Galp",), 0.75) is None


def test_multiword_window_width_is_preserved() -> None:
    trigger = trigger_identity("Welcome to SK telekom earnings.", "SK Telecom", ("SK Telecom",), 0.75)
    assert trigger is not None
    assert trigger.observed_surface == "sk telekom"
