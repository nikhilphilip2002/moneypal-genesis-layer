from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]


def test_python_services_reuse_one_built_image():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    services = compose["services"]
    image = services["backend"]["image"]

    assert services["backend"]["build"]["dockerfile"] == "backend/Dockerfile"
    assert services["postgres-mcp"]["image"] == image
    assert services["macro-pipeline"]["image"] == image
    assert "build" not in services["postgres-mcp"]
    assert "build" not in services["macro-pipeline"]


def test_backend_installs_cpu_torch_before_requirements():
    dockerfile = (ROOT / "backend/Dockerfile").read_text()
    cpu_install = 'pip install --no-cache-dir --index-url "${PYTORCH_CPU_INDEX_URL}" torch'
    dependency_install = "pip install --no-cache-dir -r /srv/requirements.txt"

    assert "https://download.pytorch.org/whl/cpu" in dockerfile
    assert dockerfile.index(cpu_install) < dockerfile.index(dependency_install)


def test_backend_context_excludes_local_virtual_environment():
    ignored = (ROOT / ".dockerignore").read_text().splitlines()

    assert ".venv/" in ignored
    assert ".pytest_cache/" in ignored
    assert ".ruff_cache/" in ignored
