from app.services.workbench import composer
from app.services.workbench.results import Evidence, MAX_EVIDENCE_ITEMS, MAX_EXCERPT_CHARS, ToolResult


def test_typed_result_separates_payload_evidence_and_lineage():
    result = ToolResult(
        source="db", card_type="chart", payload={"rows": [{"secret": "ui-only"}]},
        summary="Outstanding is 10.", evidence=[Evidence("Outstanding is 10.", untrusted=False)],
        sensitive=True, lineage={"sql": "SELECT hidden"},
    )
    rendered = composer.evidence_text([result])
    assert "Outstanding is 10" in rendered
    assert "secret" not in rendered
    assert "SELECT hidden" not in rendered
    assert result.source_group == "internal_data"


def test_evidence_is_bounded_and_serializable():
    result = ToolResult(
        source="macro", card_type="brief", payload={},
        evidence=[Evidence("x" * (MAX_EXCERPT_CHARS + 10)) for _ in range(MAX_EVIDENCE_ITEMS + 2)],
    )
    assert len(result.evidence) == MAX_EVIDENCE_ITEMS
    assert len(result.evidence[0].excerpt) == MAX_EXCERPT_CHARS
    assert result.as_dict()["kind"] == "brief"


def test_numeric_grounding_guard_accepts_format_variants_and_rejects_new_figures():
    evidence = "Portfolio was 1,200.50 and PAR was 4.2%."
    assert composer.numbers_are_grounded("PAR was 4.2% on a 1200.50 portfolio.", evidence)
    assert not composer.numbers_are_grounded("PAR was 4.3%.", evidence)


def test_extractive_fallback_uses_evidence_not_ui_payload():
    result = ToolResult(
        source="web", card_type="brief", payload={"raw": "do not expose"},
        evidence=[Evidence("Official result", document="RBI", url="https://rbi.org")],
    )
    text = composer.extractive_fallback([result])
    assert "Official result" in text
    assert "do not expose" not in text
