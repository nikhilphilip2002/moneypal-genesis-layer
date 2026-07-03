"""End-to-end smoke test for the Direct RAG engine (genesis_core.rag).

Proves load -> chunk -> embed -> store -> search -> generate all work before the
teams depend on it. Uses the buildathon brief PDF and a throwaway collection.

Prerequisites:
  - On Aroha_T1 / Aroha_G1 WiFi (to reach Qdrant)
  - .env has a real GROQ_API_KEY
  - bge-m3 downloaded (python scripts/download_model.py)
  - genesis-core installed (pip install -e packages/genesis_core)

Run:
  python scripts/smoke_test.py
"""
from pathlib import Path

from genesis_core import make_response, rag

COLLECTION = "smoke_test_tmp"
PDF = Path(__file__).resolve().parents[1] / "docs" / "Moneypal Genesis Layer Buildathon.pdf"


def main() -> None:
    print("1) Ingest test PDF ->", COLLECTION)
    n = rag.ingest_files(COLLECTION, [str(PDF)])
    assert n > 0, "ingestion produced 0 chunks"

    print("\n2) Semantic search")
    hits = rag.search(COLLECTION, "What are the three buildathon modules?", top_k=4)
    for h in hits:
        print(f"   score={h['score']:.3f}  {h['source']} p{h['page']}")
    assert hits, "search returned no hits"

    print("\n3) Generate grounded answer")
    answer, _ = rag.ask(
        COLLECTION,
        "In 3 sentences, what is the Moneypal Genesis Layer and what are its three "
        "intelligence modules?",
    )
    print("  ", answer.replace("\n", "\n   "))

    print("\n4) Assemble schema response")
    resp = make_response(
        title="Genesis Layer Overview",
        summary=answer,
        key_points=["Macro-economic", "Competitive", "Regulatory"],
        document=PDF.name,
        url="internal://docs/buildathon-brief.pdf",
        ai_note="Generated from the brief via the shared Direct RAG engine.",
        confidence="high",
    )
    print(resp.model_dump_json(indent=2))

    print("\n5) Cleanup throwaway collection")
    rag.get_qdrant().delete_collection(COLLECTION)

    print("\nSMOKE TEST PASSED  The Direct RAG engine works end to end.")


if __name__ == "__main__":
    main()
