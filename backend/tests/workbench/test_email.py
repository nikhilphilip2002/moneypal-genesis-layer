"""The mailbox (email) source: retrieval shape, degradation, and the access boundary.

Qdrant and the embedder are stubbed so the suite never depends on a live mailbox index or a
downloaded model, and so a shape change in the retrieval contract fails here loudly. The
async style follows the neighbouring node tests: ``anyio`` plus an inline ``to_thread``.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.services import email_intel
from app.services.workbench import access, agent_contracts, agent_tools, nodes, tools


# --- small talk -------------------------------------------------------------------------
#
# "hi" was being answered from the mailbox, which produced a confident "no excerpt
# matches" paragraph under a wall of unrelated citations. Greetings are answered directly,
# and the response keeps the same shape so the console renders no citation cards.


@pytest.mark.parametrize(
    "question",
    ["hi", "Hi", "hi!", "  hi  ", "hey there", "Hello.", "good morning", "how are you?",
     "thanks", "bye", "what's up"],
)
def test_greetings_are_treated_as_small_talk(question):
    from app.api.routes.email import _is_small_talk

    assert _is_small_talk(question) is True


@pytest.mark.parametrize(
    "question",
    [
        "which documents were requested for the vehicle loan?",
        "hi, what documents are needed for the vehicle loan?",
        "list the leave requests",
        "this",
        "history",
        "hire",
    ],
)
def test_real_questions_are_not_treated_as_small_talk(question):
    from app.api.routes.email import _is_small_talk

    assert _is_small_talk(question) is False


@pytest.fixture(autouse=True)
def _connector_settings(monkeypatch):
    monkeypatch.setattr(access.settings, "workbench_external_connectors_enabled", True)
    monkeypatch.setattr(access.settings, "exa_mcp_enabled", True)


@pytest.fixture
def inline_retrieval(monkeypatch):
    """Run the node's thread offload inline so tests never touch Qdrant or a model."""
    async def run_inline(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(nodes.asyncio, "to_thread", run_inline)


def _hit(text: str, *, subject: str = "Request for Vehicle Loan", score: float = 0.81,
         email_id: str = "AAMk1", sender: str = "anjali.ks@aroha.co.in") -> dict:
    return {
        "text": text,
        "subject": subject,
        "sender": sender,
        "received_at": "2026-09-28T06:01:11+00:00",
        "email_id": email_id,
        "filename": "email body",
        "chunk_source": "body",
        "source": subject,
        "document": subject,
        "score": score,
    }


def test_email_is_a_registered_source_and_a_curated_domain():
    assert "email" in access.SOURCE_GROUPS
    assert agent_tools.CURATED_DOMAIN_SOURCES["email"] == "email"
    allowed = agent_contracts.SearchCuratedKnowledgeArguments.model_fields["domain"].annotation.__args__
    assert "email" in allowed


def test_mailbox_tool_is_registered_and_blocked_without_external_consent():
    assert tools.TOOLS["mailbox_recent"].source_id == "email"
    policy = access.build_policy(role="admin", external_sources_enabled=False)
    assert not policy.allows("email")
    assert policy.allows("db")


def test_email_collection_uses_its_own_vector_space():
    """The mailbox model is not Genesis's document model; one space cannot be searched as the other."""
    assert settings.email_embedding_model != settings.embedding_model
    assert settings.email_vector_size != settings.vector_size
    assert settings.email_collection == "email_chunks"


class TestEmailNode:
    @pytest.mark.anyio
    async def test_returns_mail_metadata_in_citations(self, monkeypatch, inline_retrieval):
        monkeypatch.setattr(
            email_intel, "search_multi",
            lambda queries: [_hit("Please share the RC book and insurance.")],
        )
        result = await nodes.run_email(
            "what documents were requested for the vehicle loan",
            policy=access.build_policy(role="admin", external_sources_enabled=True),
        )
        assert result.source == "email"
        assert result.card_type == "brief"
        assert result.sensitive is True
        assert result.sources[0]["subject"] == "Request for Vehicle Loan"
        assert result.sources[0]["sender"] == "anjali.ks@aroha.co.in"
        assert result.sources[0]["date"] == "2026-09-28"
        assert result.evidence[0].excerpt.startswith("Please share")

    @pytest.mark.anyio
    async def test_deduplicates_citations_per_message(self, monkeypatch, inline_retrieval):
        """Two chunks of one message are one citation, not two identical lines."""
        monkeypatch.setattr(email_intel, "search_multi", lambda queries: [
            _hit("chunk one of the same message", email_id="AAMk1"),
            _hit("chunk two of the same message", email_id="AAMk1"),
            _hit("a different message", email_id="AAMk2", subject="Leave Request"),
        ])
        result = await nodes.run_email("recent mail", policy=None)
        assert len(result.sources) == 2
        assert {ref["subject"] for ref in result.sources} == {"Request for Vehicle Loan", "Leave Request"}

    @pytest.mark.anyio
    async def test_no_match_is_reported_without_failing_the_turn(self, monkeypatch, inline_retrieval):
        monkeypatch.setattr(email_intel, "search_multi", lambda queries: [])
        result = await nodes.run_email("anything", policy=None)
        assert result.card_type == "brief"
        assert result.complete is False
        assert "No mailbox messages" in result.limitation

    @pytest.mark.anyio
    async def test_store_failure_degrades_to_a_retryable_error_card(self, monkeypatch, inline_retrieval):
        def _boom(queries):
            raise RuntimeError("qdrant unreachable")

        monkeypatch.setattr(email_intel, "search_multi", _boom)
        result = await nodes.run_email("anything", policy=None)
        assert result.card_type == "error"
        assert result.payload["retryable"] is True

    @pytest.mark.anyio
    async def test_refuses_when_external_consent_is_off(self, inline_retrieval):
        policy = access.build_policy(role="admin", external_sources_enabled=False)
        with pytest.raises(access.SourceAccessDenied):
            await nodes.run_email("what did the borrower ask for", policy=policy)

    @pytest.mark.anyio
    async def test_adds_a_data_seeking_query_beside_the_question(self, monkeypatch, inline_retrieval):
        seen: list[list[str]] = []
        monkeypatch.setattr(email_intel, "search_multi", lambda queries: seen.append(queries) or [])
        await nodes.run_email("what did the customer ask for", policy=None)
        assert seen[0][0] == "what did the customer ask for"
        assert "customer" in seen[0][1] and "what" not in seen[0][1]


def test_search_multi_drops_weak_hits_dedupes_and_caps(monkeypatch):
    monkeypatch.setattr(settings, "email_min_score", 0.5)
    monkeypatch.setattr(settings, "email_max_chunks", 2)
    seen: list[str] = []

    def _fake_search(query: str, top_k=None):
        seen.append(query)
        return [
            _hit("strong", score=0.9),
            _hit("weak", score=0.2, email_id="AAMk2"),
            _hit("strong", score=0.9),  # same text, same dedupe key
            _hit("second", score=0.7, email_id="AAMk3"),
        ]

    monkeypatch.setattr(email_intel, "search", _fake_search)
    merged = email_intel.search_multi(["vehicle loan documents"])
    assert [hit["text"] for hit in merged] == ["strong", "second"]
    assert seen == ["vehicle loan documents"]


# --- answer-model failover -------------------------------------------------------------
#
# Two providers are configured and both are unreliable, so the pool must hand over in both
# directions without reconfiguration: a refusal from one benches it and the other answers,
# and a success puts that provider back in front. Network calls are stubbed, so these assert
# the routing decisions rather than any provider's availability.


@pytest.fixture
def _pool(monkeypatch):
    """A two-provider pool with a clean health table and a stubbed transport."""
    from app.services import email_answer

    monkeypatch.setattr(email_answer.settings, "email_llm_api_key", "k-nvidia")
    monkeypatch.setattr(email_answer.settings, "email_llm_base_url", "https://nvidia.test/v1")
    monkeypatch.setattr(email_answer.settings, "groq_api_key", "k-groq")
    monkeypatch.setattr(email_answer.settings, "groq_base_url", "https://groq.test/openai/v1")
    monkeypatch.setattr(email_answer.settings, "email_llm_model", "nvidia-model")
    monkeypatch.setattr(email_answer.settings, "groq_model", "groq-model")
    monkeypatch.setattr(email_answer.settings, "email_llm_max_tokens", 64)
    monkeypatch.setattr(email_answer, "_HEALTH", {})

    state = {"nvidia": "ok", "groq": "ok"}
    calls: list[str] = []

    def _fake_call(provider, base_url, api_key, model, messages):
        calls.append(provider)
        mode = state[provider]
        if mode == "ok":
            return f"answer from {provider}", None, False
        if mode == "403":
            return None, f"{provider} returned HTTP 403 (credential refused).", True
        return None, f"{provider} returned HTTP 503.", False

    monkeypatch.setattr(email_answer, "_call", _fake_call)
    return email_answer, state, calls


_PASSAGES = [
    {
        "text": "Please share income proof, address proof and bank statements.",
        "subject": "Request for Vehicle Loan Details",
        "sender": "anjali.ks@aroha.co.in",
        "date": "2026-09-20",
        "filename": "msg-1.txt",
        "score": 0.86,
    }
]


def test_403_fails_over_to_the_other_provider(_pool):
    email_answer, state, calls = _pool
    state["nvidia"] = "403"

    text, error = email_answer.answer("which documents?", _PASSAGES)

    assert text == "answer from groq"
    assert error is None
    assert calls[0] == "nvidia", "the refused provider is tried first, then handed over"
    assert email_answer.served_by() == "groq"
    assert email_answer._HEALTH["nvidia"].benched(__import__("time").monotonic())


def test_a_403_benches_longer_than_a_503(_pool):
    """A bad key does not become a good key in 30 seconds; a 503 might."""
    import time

    email_answer, state, _ = _pool
    now = time.monotonic()

    state["nvidia"] = "403"
    email_answer.answer("q", _PASSAGES)
    refused = email_answer._HEALTH["nvidia"]

    email_answer._HEALTH.clear()
    state["nvidia"] = "503"
    email_answer.answer("q", _PASSAGES)
    overloaded = email_answer._HEALTH["nvidia"]

    assert refused.benched_until - now > overloaded.benched_until - now


def test_the_working_provider_is_preferred_on_the_next_question(_pool):
    email_answer, state, calls = _pool
    state["nvidia"] = "403"

    email_answer.answer("q", _PASSAGES)
    calls.clear()

    text, _ = email_answer.answer("q again", _PASSAGES)

    assert text == "answer from groq"
    assert calls == ["groq"], "a benched provider is not retried while the other is healthy"
    assert email_answer.preferred() == "groq"
    assert email_answer.model_name() == "groq-model"


def test_failure_hands_back_the_other_way(_pool):
    """Groq 403 must return the console to NVIDIA."""
    import time

    email_answer, state, calls = _pool
    # Sideline NVIDIA so the request reaches Groq in the first place.
    email_answer._HEALTH["nvidia"] = email_answer._Health()
    email_answer._HEALTH["nvidia"].record_failure(
        time.monotonic(), "nvidia returned HTTP 403.", hard=True
    )
    state["groq"] = "403"

    text, error = email_answer.answer("q", _PASSAGES)

    assert text == "answer from nvidia"
    assert error is None
    assert calls[0] == "groq"
    assert email_answer.served_by() == "nvidia"


def test_a_healthy_provider_is_not_displaced_by_a_recovered_one(_pool):
    """The pool is sticky: a provider that is already working keeps the front of the order.

    Alternating on every question would double the latency for no benefit, so recovery
    means the benched provider becomes eligible again, not that it outranks a healthy one.
    """
    import time

    email_answer, state, calls = _pool
    state["nvidia"] = "403"
    email_answer.answer("q", _PASSAGES)
    assert email_answer.preferred() == "groq"

    email_answer._HEALTH["nvidia"].benched_until = 0.0
    state["nvidia"] = "ok"
    calls.clear()
    email_answer.answer("q", _PASSAGES)

    assert calls == ["groq"], "the working provider is tried, and the other is not needlessly called"
    # NVIDIA was not called, so its slate is untouched. Clearing it is the job of an
    # actual success, not of the passage of time.
    assert email_answer._HEALTH["nvidia"].consecutive_failures == 1
    assert email_answer.preferred() == "groq"


def test_a_recovered_provider_clears_its_slate_when_retried(_pool):
    """Once the recovered provider is actually reached and works, its record is clean."""
    email_answer, state, calls = _pool
    state["nvidia"] = "403"
    email_answer.answer("q", _PASSAGES)

    # Its cooldown expires and the other provider is now the broken one, so the
    # recovered provider is reached — and its stale failure record must not persist.
    email_answer._HEALTH["nvidia"].benched_until = 0.0
    email_answer._HEALTH["groq"].benched_until = 0.0
    state["nvidia"], state["groq"] = "ok", "403"
    calls.clear()
    email_answer.answer("q", _PASSAGES)

    assert "nvidia" in calls
    assert email_answer._HEALTH["nvidia"].consecutive_failures == 0
    assert email_answer._HEALTH["nvidia"].last_error == ""


def test_the_pool_recovers_after_a_cooldown(_pool):
    """A recovered provider becomes eligible again once its bench expires."""
    import time

    email_answer, state, calls = _pool
    email_answer._HEALTH["nvidia"] = email_answer._Health()
    email_answer._HEALTH["nvidia"].record_failure(
        time.monotonic(), "nvidia returned HTTP 403.", hard=True
    )
    state["groq"] = "403"
    email_answer.answer("q", _PASSAGES)
    assert email_answer._HEALTH["groq"].consecutive_failures == 1

    # Groq's bench expires while NVIDIA goes down again, so the recovered provider is
    # the only one that can serve the request and its stale record must be cleared.
    email_answer._HEALTH["groq"].benched_until = 0.0
    email_answer._HEALTH["nvidia"].benched_until = time.monotonic() + 300
    state["groq"], state["nvidia"] = "ok", "403"
    calls.clear()
    text, _ = email_answer.answer("q", _PASSAGES)
    assert calls[0] == "groq", "the recovered provider is retried once its bench expires"
    assert email_answer._HEALTH["groq"].consecutive_failures == 0
    assert email_answer._HEALTH["groq"].last_error == ""
    assert text == "answer from groq"


def test_both_providers_down_degrades_to_cited_passages(_pool):
    email_answer, state, _ = _pool
    state["nvidia"], state["groq"] = "403", "503"

    text, error = email_answer.answer("q", _PASSAGES)

    assert text is None
    assert "403" in error and "503" in error
    assert error.count("403") == 1, "a retried provider reports its cause once"
    assert email_answer.served_by() is None


def test_no_passages_never_calls_a_provider(_pool):
    email_answer, _, calls = _pool

    text, error = email_answer.answer("q", [])

    assert text is None
    assert calls == []
    assert "No matching mailbox message" in error


def test_snapshot_reports_every_configured_provider(_pool):
    import time

    email_answer, state, _ = _pool
    email_answer._HEALTH["nvidia"] = email_answer._Health()
    email_answer._HEALTH["nvidia"].record_failure(
        time.monotonic(), "nvidia returned HTTP 403.", hard=True
    )
    state["groq"] = "403"
    email_answer.answer("q", _PASSAGES)

    rows = {row["provider"]: row for row in email_answer.snapshot()}

    assert set(rows) == {"nvidia", "groq"}
    assert rows["groq"]["benched"] is True
    assert "403" in rows["groq"]["last_error"]
    assert rows["nvidia"]["model"] == "nvidia-model"



# --- attachment previews ---------------------------------------------------------------
#
# The console opens a cited message in a viewer and previews the original PDF / image.
# Those bytes live on the ingestion host behind a localhost-only /files mount, so Genesis
# streams them itself. The path in the request comes from a Qdrant payload and is therefore
# untrusted: these tests pin the confinement, because a mistake here exposes the host.


@pytest.fixture
def file_root(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    (root / "abc123").mkdir(parents=True)
    (root / "abc123" / "report.pdf").write_bytes(b"%PDF-1.4 stub")
    (root / "abc123" / "shot.png").write_bytes(b"\x89PNG stub")
    (root / "abc123" / "notes.docx").write_bytes(b"PK stub")
    (tmp_path / "secret.env").write_text("TOKEN=do-not-leak", encoding="utf-8")
    monkeypatch.setattr(settings, "email_files_dir", str(root))
    return root


@pytest.mark.parametrize("filename", ["report.pdf", "shot.png"])
def test_resolve_allows_files_under_the_root(file_root, filename):
    from app.services import email_files

    resolved = email_files.resolve(f"abc123/{filename}")

    assert resolved is not None
    assert resolved.parent == file_root / "abc123"
    assert resolved.read_bytes().endswith(b"stub")


@pytest.mark.parametrize(
    "candidate",
    [
        "",
        "   ",
        "..",
        "../secret.env",
        "abc123/../../secret.env",
        "..\\..\\secret.env",
        "C:\\Windows\\win.ini",
        "D:/email-rag/data/projects/anything",
        "/etc/passwd",
        "//server/share/file",
        "abc123/missing.pdf",
    ],
)
def test_resolve_rejects_anything_outside_the_root(file_root, candidate):
    from app.services import email_files

    assert email_files.resolve(candidate) is None


def test_resolve_rejects_a_symlink_that_escapes(file_root, tmp_path):
    from app.services import email_files

    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"secret")
    link = file_root / "abc123" / "link.pdf"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this filesystem")

    assert email_files.resolve("abc123/link.pdf") is None


def test_describe_marks_preview_kind_and_url(file_root):
    from app.services import email_files

    pdf = email_files.describe("abc123/report.pdf")
    image = email_files.describe("abc123/shot.png")
    docx = email_files.describe("abc123/notes.docx")

    assert pdf["kind"] == "pdf" and pdf["content_type"] == "application/pdf"
    assert pdf["inline"] is True and pdf["size"] > 0
    assert image["kind"] == "image" and image["content_type"] == "image/png"
    # A Word file is offered as a download: browsers cannot render it and there is no
    # extracted text attached to this shape to show instead.
    assert docx["kind"] == "binary" and docx["inline"] is False
    assert email_files.describe("abc123/missing.pdf") is None
    assert email_files.describe("") is None


def test_describe_url_encodes_paths_with_spaces(file_root):
    from app.services import email_files

    (file_root / "abc123" / "my report (final).pdf").write_bytes(b"%PDF-1.4 stub")

    described = email_files.describe("abc123/my report (final).pdf")

    assert "%20" in described["url"] and "%28" in described["url"]
    assert "my report" in described["filename"]


def test_email_body_joins_body_chunks_in_order(monkeypatch):
    """A viewer needs the message text, not an attachment chunk's extracted contents."""
    from types import SimpleNamespace

    payload = lambda idx, text: {"chunk_index": idx, "text": text, "source": "body"}
    points = [
        SimpleNamespace(payload=payload(2, "third")),
        SimpleNamespace(payload=payload(0, "first")),
        SimpleNamespace(payload=payload(1, "second")),
    ]

    class _Client:
        def scroll(self, **_kwargs):
            return points, None

    monkeypatch.setattr(email_intel, "get_client", lambda: _Client())
    monkeypatch.setattr(email_intel, "collection", lambda: "email_chunks")

    assert email_intel.email_body("m1") == "first\n\nsecond\n\nthird"
    assert email_intel.email_body("") == ""
