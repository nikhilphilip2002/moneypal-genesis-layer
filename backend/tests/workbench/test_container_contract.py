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


def test_fastmcp_dependencies_and_compatibility_mode_are_deployed():
    requirements = (ROOT / "requirements.txt").read_text()
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    services = compose["services"]

    assert "fastmcp>=4.0.5,<5" in requirements
    assert "mcp>=2.0.0,<3" in requirements
    assert "mcp==1.29.0" not in requirements
    assert services["backend"]["environment"]["FASTMCP_MCP_CAMELCASE_COMPAT"] == "false"
    assert services["postgres-mcp"]["environment"]["FASTMCP_MCP_CAMELCASE_COMPAT"] == "false"


def test_postgres_mcp_route_health_and_startup_dependency_are_explicit():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    services = compose["services"]
    postgres = services["postgres-mcp"]

    assert services["backend"]["environment"]["POSTGRES_MCP_URL"].endswith(":8001/mcp")
    assert services["backend"]["depends_on"]["postgres-mcp"]["condition"] == "service_healthy"
    assert postgres["command"] == ["python", "-m", "app.mcp.postgres_server"]
    assert "healthcheck" in postgres
    assert postgres["stop_grace_period"] == "15s"
