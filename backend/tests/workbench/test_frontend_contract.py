from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_external_toggle_has_programmatic_label_and_description():
    source = (ROOT / "frontend/components/workbench/Composer.tsx").read_text()
    assert 'htmlFor="workbench-external-sources"' in source
    assert 'id="workbench-external-sources"' in source
    assert 'aria-describedby="workbench-external-sources-description"' in source
    assert 'id="workbench-external-sources-description"' in source
    assert "onCheckedChange={onExternalSourcesEnabled}" in source


def test_external_workspace_actions_are_consent_gated():
    source = (ROOT / "frontend/app/workbench/page.tsx").read_text()
    for workspace in (
        "macro-intelligence", "competitive-intelligence", "regulatory-intelligence",
        "intelligence-review", "policy-workspace",
    ):
        assert f"'{workspace}'" in source
    assert "EXTERNAL_WORKSPACES.has(view) && !externalSourcesEnabled" in source
    assert "disabled={EXTERNAL_WORKSPACES.has(module.id) && !externalSourcesEnabled}" in source


def test_workbench_stream_preserves_native_contract_fields():
    api = (ROOT / "frontend/lib/api.ts").read_text()
    assert "facts?: WorkbenchVerifiedFact[]" in api
    assert "suggestions?: string[]" in api
    assert "tools?: string[]" in api
    assert "code?: string" in api
    assert "message: payload.text ?? payload.message ?? ''" in api
    assert "policy_version: payload.policy_version, tools: payload.tools || []" in api
    assert "retryable: !!payload.retryable, reason: payload.reason" in api


def test_workbench_turn_renders_preserved_answer_and_route_metadata():
    source = (ROOT / "frontend/components/workbench/WorkbenchTurn.tsx").read_text()
    assert "'schema', 'catalog'" in source
    assert 'aria-label="Verified facts"' in source
    assert 'aria-label="Suggested follow-up questions"' in source
    assert "turn.error.code" in source
    assert 'aria-label="Capabilities used"' in source
