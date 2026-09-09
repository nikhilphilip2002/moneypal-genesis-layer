from app.services.workbench import evaluation


def test_usage_summary_reports_p50_p95_by_purpose():
    report = evaluation.usage_summary([{
        "usage": {"calls": [
            {"purpose": "route", "uncached_prompt_tokens": 100},
            {"purpose": "route", "uncached_prompt_tokens": 200},
        ]},
        "timing": {"first_event_ms": 1, "first_card_ms": 10, "total_ms": 20},
    }])
    assert report["purposes"]["route"] == {
        "count": 2, "p50_uncached": 100.0, "p95_uncached": 200.0,
    }
