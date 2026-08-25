"""Tests for deterministic official-material organization."""

from meeting_minutes_agent.state.meeting_materials import (
    classify_material_document,
    extract_candidate_surfaces,
    extract_visible_html_text,
    normalize_material_surface,
)


def test_normalize_material_surface_only_changes_formatting() -> None:
    assert normalize_material_surface("  Frontline   AR, ") == "Frontline AR"


def test_extracts_proper_names_acronyms_and_alphanumeric_terms() -> None:
    rows = extract_candidate_surfaces("Frontline AR works with Google Cloud and 5G services.")
    surfaces = {row["surface"] for row in rows}
    assert {"Frontline AR", "Google Cloud", "5G"} <= surfaces


def test_excludes_generic_financial_heading() -> None:
    rows = extract_candidate_surfaces("Financial Results and Adjusted EBITDA")
    surfaces = {row["surface"] for row in rows}
    assert "Financial Results" not in surfaces
    assert "Adjusted EBITDA" not in surfaces


def test_extract_visible_html_text_ignores_executable_and_style_content() -> None:
    html = """<html><style>Hidden Style</style><body><h1>Global Atlantic</h1>
    <script>Hidden Script</script><p>Fee Related Earnings</p></body></html>"""
    text = extract_visible_html_text(html)
    assert text == "Global Atlantic\nFee Related Earnings"


def test_classifies_pdf_regular_html_and_sec_exhibit() -> None:
    assert classify_material_document(b"%PDF-1.7", ".pdf") == "pdf"
    assert classify_material_document(b"<!DOCTYPE html><html>", ".html") == "html"
    assert classify_material_document(b"<DOCUMENT>\n<TYPE>EX-99.1", ".htm") == "html"
    assert classify_material_document(b"access denied", ".pdf") == "unsupported"
