"""Topic classification and figure mining — the enrichment attached to every chunk."""

from __future__ import annotations

from scripts.macro_pipeline import macro_topics, structured


class TestFigures:
    def test_decimals_do_not_truncate_the_context_sentence(self):
        text = "India’s 10-year bond yield is 6.7%, while Indonesia’s is 6.3%, even though both economies grew."

        figures = structured.extract_figures(text)

        values = {f["value"] for f in figures}
        assert {6.7, 6.3} <= values
        # A naive "split on every period" splitter cuts this into "…yield is 6." and
        # leaves the number with no classifiable context.
        for figure in figures:
            assert "Indonesia" in figure["sentence"]

    def test_sentence_gives_the_figure_a_topic(self):
        text = "Retail inflation measured by the consumer price index eased to 4.6% in FY25."

        figures = structured.extract_figures(text)

        assert figures
        assert figures[0]["value"] == 4.6
        assert figures[0]["about"] == "inflation_cpi"

    def test_mines_rupee_amounts_bps_and_percentage_points(self):
        text = (
            "Bank credit stood at Rs 12,50,000 crore. The repo rate was cut by 25 bps. "
            "The deficit narrowed by 1.4 percentage points."
        )

        figures = structured.extract_figures(text)
        kinds = {(f["kind"], f["value"], f["unit"]) for f in figures}

        # The magnitude word is part of the figure: 1,250,000 crore and 1,250,000 lakh
        # differ by 100x, so "crore" is carried rather than flattened to "amount".
        assert ("currency", 1250000.0, "crore") in kinds
        # bps and percentage points each get their own kind — 25 bps is not 25%.
        assert ("bps", 25.0, "bps") in kinds
        assert ("pp", 1.4, "pp") in kinds

    def test_output_is_capped_and_deduplicated(self):
        text = " ".join(["Growth was 6.5 per cent."] * 60)

        figures = structured.extract_figures(text)

        assert len(figures) <= 25
        assert len(figures) == 1, "identical value+sentence pairs collapse to one row"

    def test_long_table_rows_fall_back_to_a_tight_window(self):
        text = "Item " + " ".join(f"{i} 12.5%" for i in range(200))

        for figure in structured.extract_figures(text):
            assert len(figure["sentence"]) <= 280


class TestTopics:
    def test_phrase_keywords_outrank_single_words(self):
        text = "MSME credit growth accelerated as bank credit to small business expanded."

        topics = macro_topics.classify_topics(text)

        assert topics[0] in ("credit_growth", "msme_trends")

    def test_generic_sector_topic_is_demoted(self):
        text = "The industry and services sector saw activity while MSME credit growth surged."

        topics = macro_topics.classify_topics(text)

        assert topics.index("sectors") > 0

    def test_unrelated_text_classifies_to_nothing(self):
        assert macro_topics.classify_topics("The committee met and adjourned.") == []


def test_snapshot_attaches_topics_and_figures_to_every_row():
    rows = [{"text": "Real GDP grew 6.5 per cent in FY25.", "document": "x.pdf", "chunk_index": 0}]

    enriched = list(structured.extract_snapshot(rows))

    assert enriched[0]["topics"]
    assert enriched[0]["figures"][0]["value"] == 6.5
