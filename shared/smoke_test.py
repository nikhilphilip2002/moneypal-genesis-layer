"""End-to-end smoke test for the Direct RAG pipeline.

Proves load -> chunk -> embed -> store -> search -> generate all work before the
teams depend on it. Uses the buildathon brief PDF as the test document and a
throwaway collection that is deleted at the end.

Prerequisites:
  - On Aroha_T1 / Aroha_G1 WiFi (to reach Qdrant at 192.168.1.183)
  - .env has a real GROQ_API_KEY
  - bge-m3 downloaded (python shared/download_model.py)

Run:
  python shared/smoke_test.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import rag_helpers as rag  # noqa: E402
from schema import make_response  # noqa: E402

COLLECTION = "smoke_test_tmp"
PDF = os.path.join(HERE, "..", "docs", "Moneypal Genesis Layer Buildathon.pdf")


def main() -> None:
    print("1) Ingest test PDF ->", COLLECTION)
    n = rag.ingest_files(COLLECTION, [PDF])
    assert n > 0, "ingestion produced 0 chunks"

    print("\n2) Semantic search")
    hits = rag.search(COLLECTION, "What are the three buildathon modules?", top_k=4)
    for h in hits:
        print(f"   score={h['score']:.3f}  {h['source']} p{h['page']}")
    assert hits, "search returned no hits"

    print("\n3) Generate grounded answer")
    answer, _sources = rag.ask(
        COLLECTION,
        "In 3 sentences, what is the Moneypal Genesis Layer and what are its three "
        "intelligence modules?",
    )
    print("   --- answer ---")
    print("  ", answer.replace("\n", "\n   "))

    print("\n4) Assemble schema response")
    resp = make_response(
        title="Genesis Layer Overview",
        summary=answer,
        key_points=[
            "Macro-economic Intelligence",
            "Competitive Intelligence",
            "Regulatory Intelligence",
        ],
        document=os.path.basename(PDF),
        url="internal://docs/buildathon-brief.pdf",
        ai_note="Generated from the buildathon brief via the shared Direct RAG pipeline.",
        confidence="high",
    )
    print(resp.model_dump_json(indent=2))

    print("\n5) Cleanup throwaway collection")
    rag.get_qdrant().delete_collection(COLLECTION)

    print("\nSMOKE TEST PASSED ✔  The Direct RAG pipeline works end to end.")


if __name__ == "__main__":
    main()
