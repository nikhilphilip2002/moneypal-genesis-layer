from app.core.config import Settings


def test_optional_personalization_can_be_disabled(monkeypatch):
    monkeypatch.setenv("WORKBENCH_PERSONALIZE_SUGGESTIONS", "false")
    config = Settings()
    assert config.workbench_personalize_suggestions is False


def test_external_connector_kill_switch_is_independent(monkeypatch):
    monkeypatch.setenv("WORKBENCH_EXTERNAL_CONNECTORS_ENABLED", "false")
    config = Settings()
    assert config.workbench_external_connectors_enabled is False


def test_native_agent_budget_bounds_values(monkeypatch):
    monkeypatch.setenv("WORKBENCH_AGENT_MAX_ROUNDS", "99")
    monkeypatch.setenv("WORKBENCH_AGENT_MAX_TOOL_CALLS", "0")
    config = Settings()
    assert config.workbench_agent_max_rounds == 8  # every LLM request is one round since Phase B
    assert config.workbench_agent_max_tool_calls == 1
