from app.services import regulatory_rag


def test_generate_uses_shared_rag_engine(monkeypatch):
    seen: dict = {}

    def generate(prompt, hits, *, system):
        seen.update(prompt=prompt, hits=hits, system=system)
        return "configured response"

    monkeypatch.setattr(regulatory_rag.rag, "generate", generate)
    hits = [{"text": "RBI requirement", "source": "circular.pdf", "page": 2}]

    assert regulatory_rag.generate_brief("summarize", hits) == "configured response"
    assert seen["prompt"] == "summarize"
    assert seen["hits"] == hits
    assert "regulatory intelligence analyst" in seen["system"]


def test_generate_returns_none_when_shared_engine_is_unavailable(monkeypatch):
    def fail(*_args, **_kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(regulatory_rag.rag, "generate", fail)
    assert regulatory_rag.generate_brief("summarize", []) is None
