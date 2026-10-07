from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_external_toggle_has_programmatic_label_and_description():
    source = (ROOT / "frontend/components/workbench/Composer.tsx").read_text()
    assert 'htmlFor="workbench-external-sources"' in source
    assert 'id="workbench-external-sources"' in source
    assert 'aria-describedby="workbench-external-sources-description"' in source
    assert 'id="workbench-external-sources-description"' in source
    assert "onCheckedChange={onExternalSourcesEnabled}" in source


def test_external_workspace_actions_are_consent_gated():
    source = _read("frontend/app/workbench/page.tsx")
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
    assert "message: stringValue(payload.text) || stringValue(payload.message)" in api
    assert "policy_version: optionalString(payload.policy_version)" in api
    assert "tools: stringArray(payload.tools)" in api
    assert "retryable: payload.retryable === true" in api
    assert "reason: optionalString(payload.reason)" in api


def test_workbench_turn_renders_preserved_answer_and_route_metadata():
    source = _read("frontend/components/workbench/WorkbenchTurn.tsx")
    assert "card.card_type === 'schema'" in source
    assert "card.card_type === 'catalog'" in source
    assert 'aria-label="Verified facts"' in source
    assert 'aria-label="Suggested follow-up questions"' in source
    assert "turn.error.code" in source
    assert "turn.route.sources" in source
    assert ">Sources</span>" in source


def test_email_switch_is_labelled_and_toggles_independent_consent():
    source = _read("frontend/components/workbench/Composer.tsx")
    assert 'htmlFor="workbench-email-sources"' in source
    assert 'id="workbench-email-sources"' in source
    assert "onCheckedChange={onEmailEnabled}" in source
    # The mailbox must follow the policy: its own switch OR the legacy broad switch.
    assert "return emailEnabled || externalSourcesEnabled;" in source


def test_email_switch_drives_the_enabled_banner():
    page = _read("frontend/app/workbench/page.tsx")
    assert "emailEnabled" in page
    assert "Email extraction is enabled" in page
    # The flag must reach the request body, not just local UI state.
    assert "emailEnabled," in page or "emailEnabled}" in page


def test_email_citations_stay_visible_when_the_agent_also_answered():
    source = _read("frontend/components/workbench/WorkbenchTurn.tsx")
    assert "EmailSourceViewer" in source
    # Email brief cards used to be hidden whenever a narrative answer existed, which is why
    # email evidence never showed in the console. They must survive that filter.
    assert "|| card.source === 'email'" in source
    assert "card.source === 'email' && card.card_type === 'brief'" in source


def test_email_attachment_previews_are_authenticated():
    api = _read("frontend/lib/api.ts")
    # <img>/<object> loads cannot send a bearer token, so bytes must be fetched and blob-ed.
    assert "fetchBlob" in api
    assert "createObjectURL" in _read("frontend/components/email/EmailSourceViewer.tsx")


def test_standalone_email_module_is_retired():
    assert "Email Transactions" not in _read("frontend/lib/useUserRole.ts")
    assert "email-transactions" not in _read("frontend/components/workbench/WorkbenchWorkspace.tsx")
    assert not (ROOT / "frontend/app/email").exists()
