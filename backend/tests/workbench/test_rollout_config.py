from app.core.config import Settings


def test_simplification_flags_can_be_disabled_independently(monkeypatch):
    for name in (
        "WORKBENCH_ORCHESTRATOR_V2",
        "WORKBENCH_DETERMINISTIC_ROUTING",
        "WORKBENCH_COMMON_COMPOSER",
        "WORKBENCH_PERSONALIZE_SUGGESTIONS",
    ):
        monkeypatch.setenv(name, "false")
    config = Settings()
    assert config.workbench_orchestrator_v2 is False
    assert config.workbench_deterministic_routing is False
    assert config.workbench_common_composer is False
    assert config.workbench_personalize_suggestions is False


def test_external_connector_kill_switch_is_independent(monkeypatch):
    monkeypatch.setenv("WORKBENCH_EXTERNAL_CONNECTORS_ENABLED", "false")
    monkeypatch.setenv("WORKBENCH_COMMON_COMPOSER", "true")
    config = Settings()
    assert config.workbench_external_connectors_enabled is False
    assert config.workbench_common_composer is True
