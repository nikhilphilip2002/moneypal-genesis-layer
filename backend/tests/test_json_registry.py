import json

import pytest

from app.services import json_registry


def test_registry_round_trip_is_sorted(tmp_path):
    json_registry.save(tmp_path, {"id": "zeta", "value": 2})
    json_registry.save(tmp_path, {"id": "alpha", "value": 1})

    assert json_registry.load_one(tmp_path, "alpha") == {
        "id": "alpha",
        "value": 1,
    }
    assert [item["id"] for item in json_registry.load_all(tmp_path)] == [
        "alpha",
        "zeta",
    ]
    assert json.loads((tmp_path / "alpha.json").read_text()) == {
        "id": "alpha",
        "value": 1,
    }


@pytest.mark.parametrize(
    "item_id", ["", "../outside", "nested/file", ".hidden"]
)
def test_registry_rejects_unsafe_ids(tmp_path, item_id):
    assert json_registry.load_one(tmp_path, item_id) is None

    with pytest.raises(ValueError, match="registry id"):
        json_registry.save(tmp_path, {"id": item_id})
