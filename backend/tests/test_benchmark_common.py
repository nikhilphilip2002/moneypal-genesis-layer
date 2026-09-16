import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "benchmark_common.py"
SPEC = importlib.util.spec_from_file_location("benchmark_common", MODULE_PATH)
assert SPEC and SPEC.loader
benchmark_common = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark_common)

decode_sse_data = benchmark_common.decode_sse_data
load_env_file = benchmark_common.load_env_file
percentile = benchmark_common.percentile


def test_load_env_file_ignores_comments_and_unquotes_values(tmp_path):
    path = tmp_path / "benchmark.env"
    path.write_text("# comment\nTOKEN='secret'\nEMPTY=\n", encoding="utf-8")

    assert load_env_file(path) == {"TOKEN": "secret", "EMPTY": ""}


def test_decode_sse_data_handles_objects_scalars_and_invalid_json():
    assert decode_sse_data(['{"status": "ok"}']) == {"status": "ok"}
    assert decode_sse_data(["42"]) == {"value": 42}
    assert decode_sse_data(["not-json"]) == {"raw": "not-json"}


def test_percentile_uses_nearest_rank():
    assert percentile([], 0.95) == 0.0
    assert percentile([4.0, 1.0, 3.0, 2.0], 0.5) == 2.0
    assert percentile([4.0, 1.0, 3.0, 2.0], 0.95) == 4.0
