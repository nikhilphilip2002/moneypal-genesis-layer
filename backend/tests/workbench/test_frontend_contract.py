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
