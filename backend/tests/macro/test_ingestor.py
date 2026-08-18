"""Refresh semantics: idempotent IDs, per-document replace, and the stale purge."""

from __future__ import annotations


from scripts.macro_pipeline import ingestor


def _rows(document: str, count: int, pages: bool = True) -> list[tuple[dict, list[float]]]:
    return [
        (
            {
                "document": document,
                "page": (i + 1) if pages else None,
                "chunk_index": i,
                "text": f"{document} chunk {i}",
                "source_url": f"https://example.test/{document}",
                "topics": ["gdp_growth"],
                "figures": [],
            },
            [0.1, 0.2, 0.3],
        )
        for i in range(count)
    ]


def test_point_ids_are_stable_and_source_scoped():
    first = ingestor.point_id("indiabudget_gov_in", "echap01.pdf", 3, 7)
    assert first == ingestor.point_id("indiabudget_gov_in", "echap01.pdf", 3, 7)
    # Same filename from a different portal must not collide.
    assert first != ingestor.point_id("mospi_gov_in", "echap01.pdf", 3, 7)
    assert first != ingestor.point_id("indiabudget_gov_in", "echap01.pdf", 4, 7)


def test_payload_carries_citable_source_and_page(fake_qdrant, macro_collection):
    ingestor.ensure_collection()
    ingestor.upsert_rows(_rows("echap02.pdf", 2), "indiabudget_gov_in", "run-1")

    payload = fake_qdrant.payloads()[0]
    # rag.search reads `source` for the citation label — it must be the document,
    # not the source slug, or briefs cite "(indiabudget_gov_in)".
    assert payload["source"] == "echap02.pdf"
    assert payload["page"] in (1, 2)
    assert payload["module"] == "macro"
    assert payload["ingest_run"] == "run-1"


def test_reingesting_unchanged_document_does_not_duplicate(fake_qdrant, macro_collection):
    ingestor.ensure_collection()
    ingestor.upsert_rows(_rows("echap02.pdf", 5), "indiabudget_gov_in", "run-1")
    assert ingestor.count() == 5

    ingestor.upsert_rows(_rows("echap02.pdf", 5), "indiabudget_gov_in", "run-2")
    assert ingestor.count() == 5, "deterministic IDs should overwrite, not append"


def test_shorter_revision_leaves_no_orphaned_chunk_tail(fake_qdrant, macro_collection):
    ingestor.ensure_collection()
    ingestor.upsert_rows(_rows("echap02.pdf", 9), "indiabudget_gov_in", "run-1")
    assert ingestor.count() == 9

    # The document shrank. Without the delete-first step the 4 trailing chunks of the
    # old revision would linger forever with stale content.
    ingestor.delete_document("echap02.pdf", "indiabudget_gov_in")
    ingestor.upsert_rows(_rows("echap02.pdf", 5), "indiabudget_gov_in", "run-2")
    assert ingestor.count() == 5


def test_delete_document_is_scoped_to_one_source(fake_qdrant, macro_collection):
    ingestor.ensure_collection()
    ingestor.upsert_rows(_rows("shared.pdf", 3), "indiabudget_gov_in", "run-1")
    ingestor.upsert_rows(_rows("shared.pdf", 3), "mospi_gov_in", "run-1")
    assert ingestor.count() == 6

    ingestor.delete_document("shared.pdf", "mospi_gov_in")
    assert ingestor.count() == 3
    assert {p["source_slug"] for p in fake_qdrant.payloads()} == {"indiabudget_gov_in"}


def test_restamp_moves_unchanged_points_onto_the_new_run(fake_qdrant, macro_collection):
    ingestor.ensure_collection()
    ingestor.upsert_rows(_rows("echap02.pdf", 4), "indiabudget_gov_in", "run-1")

    moved = ingestor.restamp_document("echap02.pdf", "indiabudget_gov_in", "run-2")
    assert moved == 4
    assert all(p["ingest_run"] == "run-2" for p in fake_qdrant.payloads())


class TestPurge:
    def test_deletes_only_points_from_older_runs(self, fake_qdrant, macro_collection):
        ingestor.ensure_collection()
        ingestor.upsert_rows(_rows("retired.pdf", 3), "indiabudget_gov_in", "run-1")
        ingestor.upsert_rows(_rows("current.pdf", 7), "indiabudget_gov_in", "run-2")

        report = ingestor.purge_stale("run-2", stamped=7, before=10, safe=True)

        assert report["ran"] is True
        assert report["deleted"] == 3
        assert fake_qdrant.documents() == {"current.pdf"}

    def test_leaves_legacy_unstamped_points_alone_by_default(self, fake_qdrant, macro_collection):
        from .helpers import put_legacy_point

        ingestor.ensure_collection()
        ingestor.upsert_rows(_rows("retired.pdf", 3), "indiabudget_gov_in", "run-1")
        ingestor.upsert_rows(_rows("current.pdf", 4), "indiabudget_gov_in", "run-2")
        put_legacy_point(fake_qdrant, "mospi_release.pdf")

        report = ingestor.purge_stale("run-2", stamped=4, before=7, safe=True)

        # The superseded run-1 points go; the pre-pipeline point stays, because the
        # crawler cannot re-fetch what it covers.
        assert report["deleted"] == 3
        assert "mospi_release.pdf" in fake_qdrant.documents()

    def test_purges_legacy_points_when_explicitly_opted_in(
        self, fake_qdrant, macro_collection, monkeypatch
    ):
        from app.core.config import settings

        from .helpers import put_legacy_point

        monkeypatch.setattr(settings, "macro_purge_legacy", True)
        ingestor.ensure_collection()
        ingestor.upsert_rows(_rows("current.pdf", 4), "indiabudget_gov_in", "run-2")
        put_legacy_point(fake_qdrant, "mospi_release.pdf")

        report = ingestor.purge_stale("run-2", stamped=4, before=5, safe=True)

        assert report["deleted"] == 1
        assert fake_qdrant.documents() == {"current.pdf"}

    def test_skipped_when_a_source_failed(self, fake_qdrant, macro_collection):
        ingestor.ensure_collection()
        ingestor.upsert_rows(_rows("old.pdf", 10), "indiabudget_gov_in", "run-1")

        report = ingestor.purge_stale("run-2", stamped=0, before=10, safe=False)

        assert report["ran"] is False
        assert "failed" in report["reason"]
        assert ingestor.count() == 10, "a blocked crawl must not empty the collection"

    def test_skipped_when_run_yield_falls_below_the_ratio_rail(self, fake_qdrant, macro_collection):
        ingestor.ensure_collection()
        ingestor.upsert_rows(_rows("old.pdf", 100), "indiabudget_gov_in", "run-1")

        # Only 10 of 100 points re-confirmed — the crawl clearly came back partial.
        report = ingestor.purge_stale("run-2", stamped=10, before=100, safe=True)

        assert report["ran"] is False
        assert "MACRO_PURGE_MIN_RATIO" in report["reason"]
        assert ingestor.count() == 100

    def test_runs_on_first_ever_ingest(self, fake_qdrant, macro_collection):
        ingestor.ensure_collection()
        ingestor.upsert_rows(_rows("new.pdf", 5), "indiabudget_gov_in", "run-1")

        # before=0 -> ratio guard must not divide by zero or block the first run.
        report = ingestor.purge_stale("run-1", stamped=5, before=0, safe=True)

        assert report["ran"] is True
        assert report["deleted"] == 0

    def test_respects_the_disable_switch(self, fake_qdrant, macro_collection, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "macro_purge_stale", False)
        ingestor.ensure_collection()
        ingestor.upsert_rows(_rows("old.pdf", 3), "indiabudget_gov_in", "run-1")

        report = ingestor.purge_stale("run-2", stamped=3, before=3, safe=True)

        assert report["ran"] is False
        assert ingestor.count() == 3


def test_migration_targets_only_legacy_unstamped_points(fake_qdrant, macro_collection):
    from .helpers import put_legacy_point

    ingestor.ensure_collection()
    ingestor.upsert_rows(_rows("current.pdf", 4), "indiabudget_gov_in", "run-1")
    put_legacy_point(fake_qdrant, "legacy.pdf")
    put_legacy_point(fake_qdrant, "legacy2.pdf")

    assert ingestor.count_unstamped() == 2
    assert ingestor.delete_unstamped() == 2
    assert ingestor.count_unstamped() == 0
    assert ingestor.count() == 4
