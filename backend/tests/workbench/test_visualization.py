from __future__ import annotations

import pytest

from app.services.workbench.agent_contracts import (
    VisualizeQueryResultArguments,
)
from app.services.workbench.visualization import (
    VisualizationError,
    build_inferred_visual,
    build_visual,
)


def _source(*, rows=None, complete=True):
    rows = rows or [
        {"week_number": 31, "scheme_code": "MSME", "total_collected": 11.0},
        {"week_number": 31, "scheme_code": "Personal", "total_collected": 8.0},
        {"week_number": 32, "scheme_code": "MSME", "total_collected": 15.0},
    ]
    return {
        "query_id": "older:q1",
        "status": "success",
        "has_data": True,
        "result_complete": complete,
        "result_payload": {
            "title": "Weekly collections",
            "columns": [
                {
                    "name": "week_number",
                    "label": "Week Number",
                    "unit": "count",
                },
                {"name": "scheme_code", "label": "Scheme", "unit": "text"},
                {
                    "name": "total_collected",
                    "label": "Collected",
                    "unit": "inr",
                },
            ],
            "rows": rows,
            "lineage": {
                "path": "postgres_mcp",
                "sql": "SELECT ...",
                "display_sql": "",
                "row_count": len(rows),
                "warnings": [],
                "unverified": True,
            },
        },
    }


def _args(**overrides):
    values = {
        "query_id": "older:q1",
        "chart_type": "stacked_area",
        "x": "week_number",
        "y": ["total_collected"],
        "series": "scheme_code",
        "aggregation": "none",
    }
    values.update(overrides)
    return VisualizeQueryResultArguments.model_validate(values)


def test_preserves_already_aggregated_rows_for_stacked_area():
    result = build_visual(_source(), _args())

    assert result.payload["chart_type"] == "stacked_area"
    assert result.payload["x"]["field"] == "week_number"
    assert result.payload["series_by"]["field"] == "scheme_code"
    assert result.payload["series"][0]["field"] == "total_collected"
    assert result.payload["rows"][0]["total_collected"] == 11.0


def test_sum_combines_rows_at_the_requested_grain():
    source = _source(
        rows=[
            {"week_number": 31, "scheme_code": "MSME", "total_collected": 4.0},
            {"week_number": 31, "scheme_code": "MSME", "total_collected": 7.0},
        ]
    )

    result = build_visual(source, _args(aggregation="sum"))

    assert result.payload["rows"] == [
        {
            "week_number": 31,
            "scheme_code": "MSME",
            "total_collected": 11.0,
        }
    ]


@pytest.mark.parametrize(
    ("aggregation", "expected"),
    [
        ("avg", 5.5),
        ("min", 4.0),
        ("max", 7.0),
        ("count", 2),
        ("count_distinct", 2),
    ],
)
def test_supported_aggregations(aggregation, expected):
    source = _source(
        rows=[
            {"week_number": 31, "scheme_code": "MSME", "total_collected": 4.0},
            {"week_number": 31, "scheme_code": "MSME", "total_collected": 7.0},
        ]
    )

    result = build_visual(source, _args(aggregation=aggregation))

    assert result.payload["rows"][0]["total_collected"] == expected


def test_none_rejects_duplicate_x_series_grain():
    source = _source(
        rows=[
            {"week_number": 31, "scheme_code": "MSME", "total_collected": 4.0},
            {"week_number": 31, "scheme_code": "MSME", "total_collected": 7.0},
        ]
    )

    with pytest.raises(VisualizationError, match="one row per x/series pair"):
        build_visual(source, _args())


def test_rejects_aggregation_of_a_truncated_result():
    with pytest.raises(VisualizationError, match="truncated"):
        build_visual(_source(complete=False), _args(aggregation="sum"))


def test_infers_donut_fields_from_query_result_order_and_types():
    source = _source(
        rows=[
            {"gender": "Male", "loan_count": 229},
            {"gender": "Female", "loan_count": 159},
        ]
    )
    source["result_payload"]["columns"] = [
        {"name": "gender", "label": "Gender", "unit": "text"},
        {"name": "loan_count", "label": "Loans", "unit": "count"},
    ]

    result = build_inferred_visual(source, query_id="turn:q1", view="donut")

    assert result.payload["x"]["field"] == "gender"
    assert result.payload["series"][0]["field"] == "loan_count"


def test_inferred_view_rejects_an_incompatible_result_shape():
    source = _source(rows=[{"gender": "Male", "scheme": "MSME"}])
    source["result_payload"]["columns"] = [
        {"name": "gender", "unit": "text"},
        {"name": "scheme", "unit": "text"},
    ]

    with pytest.raises(VisualizationError, match="numeric value"):
        build_inferred_visual(source, query_id="turn:q1", view="donut")
