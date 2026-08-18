"""Mechanically extracted session state — the layer that must never lose a figure."""

from __future__ import annotations

import pytest

from app.services.workbench.compaction import state as session_state


def _chart_turn(turn_id: str, question: str, summary: str, *, sources=("db",)):
    return {
        "id": turn_id,
        "question": question,
        "status": "complete",
        "route": {"sources": list(sources), "intent": "data"},
        "cards": [
            {
                "source": sources[0],
                "card_type": "chart",
                "payload": {
                    "title": "Portfolio at risk",
                    "chart_type": "bar",
                    "columns": [{"name": "product"}, {"name": "par_30"}],
                    "rows": [],
                    "summary": summary,
                },
            }
        ],
        "synthesis": summary,
        "refusal": None,
        "error": None,
    }


def _text_of(turn):
    parts = [turn.get("synthesis") or ""]
    for card in turn.get("cards") or []:
        parts.append(str(card.get("payload", {}).get("summary") or ""))
    return "\n".join(p for p in parts if p)


class TestFigures:
    def test_captures_percentages_with_their_period(self):
        turn = _chart_turn("t1", "PAR-30 for FY25?", "PAR-30 stood at 4.2% in FY25.")

        state = session_state.extract_turn(turn, _text_of(turn))

        assert state.figures
        figure = state.figures[0]
        assert figure.value == "4.2%"
        assert figure.period == "FY25"
        assert figure.turn_id == "t1"

    def test_captures_rupee_amounts(self):
        turn = _chart_turn("t2", "MSME book?", "MSME credit outstanding is Rs 12,50,000 crore.")

        values = {f.value for f in session_state.extract_turn(turn, _text_of(turn)).figures}

        assert "Rs 12,50,000 crore" in values

    def test_captures_basis_points(self):
        turn = _chart_turn("t3", "Rate move?", "The repo rate was cut by 25 bps.")

        values = {f.value for f in session_state.extract_turn(turn, _text_of(turn)).figures}

        assert "25 bps" in values

    def test_period_falls_back_to_the_question(self):
        turn = _chart_turn("t4", "What was collection efficiency in FY24?", "It reached 92.5%.")

        figure = session_state.extract_turn(turn, _text_of(turn)).figures[0]

        assert figure.period == "FY24"

    def test_a_turn_cannot_flood_the_state(self):
        body = "\n".join(f"Metric {i} came in at {i}.5%." for i in range(50))
        turn = _chart_turn("t5", "Everything?", body)

        state = session_state.extract_turn(turn, _text_of(turn))

        assert len(state.figures) <= session_state.MAX_FIGURES_PER_TURN

    @pytest.mark.parametrize(
        "text",
        [
            "Over the years 2024 saw steady growth.",
            "Across quarters 2025 remained stable.",
            "Numbers 2026 were not disclosed.",
        ],
    )
    def test_currency_marker_needs_a_word_boundary(self, text):
        """"yea|rs 2024" must not be read as a rupee amount.

        A false figure is worse than a missing one: it enters the state block as fact.
        """
        turn = _chart_turn("t8", "Trend?", text)

        assert session_state.extract_turn(turn, _text_of(turn)).figures == []

    def test_real_currency_forms_are_still_caught(self):
        turn = _chart_turn("t8", "Book?", "Sanctioned ₹1,200 crore and Rs.75 lakh this year.")

        value = session_state.extract_turn(turn, _text_of(turn)).figures[0].value

        assert "Rs 1,200 crore" in value
        assert "Rs 75 lakh" in value

    def test_one_row_per_sentence_not_per_number(self):
        turn = _chart_turn(
            "t7", "Split?", "Term loans 5.1%, working capital 3.4%, gold loans 1.2% in 2026-07."
        )

        figures = session_state.extract_turn(turn, _text_of(turn)).figures

        # The sentence is the context for all three numbers; repeating it per number
        # triples a block that ships on every request.
        assert len(figures) == 1
        assert figures[0].value == "5.1%, 3.4%, 1.2%"
        assert figures[0].period == "2026-07"

    def test_values_survive_verbatim_not_rounded(self):
        turn = _chart_turn("t6", "Growth?", "Real GDP grew 6.5 per cent in FY25.")

        figure = session_state.extract_turn(turn, _text_of(turn)).figures[0]

        # The whole point of extracting mechanically: no model gets to round this.
        assert figure.value == "6.5%"


class TestRouteAndRefusals:
    def test_sources_are_collected(self):
        turn = _chart_turn("t1", "Compare", "Nothing numeric here.", sources=("db", "macro"))

        state = session_state.extract_turn(turn, _text_of(turn))

        assert state.sources_consulted == {"db", "macro"}

    def test_refusals_are_retained(self):
        turn = _chart_turn("t1", "Show borrower names", "")
        turn["refusal"] = {"message": "Borrower PII is not available for your role."}

        state = session_state.extract_turn(turn, _text_of(turn))

        assert state.refusals
        assert "PII" in state.refusals[0]
        assert "t1" in state.refusals[0]

    def test_pinned_document_is_carried(self):
        turn = _chart_turn("t1", "What does it say?", "It says growth held up.")
        turn["pinned"] = "RBI Master Direction 2024.pdf"

        state = session_state.extract_turn(turn, _text_of(turn))

        assert state.pinned == "RBI Master Direction 2024.pdf"
        assert "<pinned-document>" in session_state.render(state)

    def test_currency_scale_is_preserved(self):
        """crore and lakh crore differ by 10,000x — the magnitude word is the figure."""
        turn = _chart_turn("t1", "Book size?", "The book stands at Rs 1,200 crore.")

        value = session_state.extract_turn(turn, _text_of(turn)).figures[0].value

        assert value == "Rs 1,200 crore"

    def test_chart_columns_become_metrics(self):
        turn = _chart_turn("t1", "PAR?", "PAR-30 stood at 4.2%.")

        state = session_state.extract_turn(turn, _text_of(turn))

        assert {"product", "par_30"} <= state.metrics_seen


class TestMergeAndRender:
    def test_merge_deduplicates_repeated_figures(self):
        turn = _chart_turn("t1", "PAR?", "PAR-30 stood at 4.2% in FY25.")
        first = session_state.extract_turn(turn, _text_of(turn))
        second = session_state.extract_turn(turn, _text_of(turn))

        merged = session_state.merge(first, second)

        assert len(merged.figures) == len(first.figures)

    def test_merge_caps_total_figures_keeping_newest(self):
        base = session_state.SessionState(
            figures=[
                session_state.Figure(f"old {i}", f"{i}%", "FY20", "db", "t0")
                for i in range(session_state.MAX_FIGURES)
            ]
        )
        turn = _chart_turn("t9", "Latest?", "Latest reading is 9.9% in FY26.")
        merged = session_state.merge(base, session_state.extract_turn(turn, _text_of(turn)))

        assert len(merged.figures) == session_state.MAX_FIGURES
        assert merged.figures[-1].value == "9.9%"

    def test_render_is_empty_when_nothing_was_learned(self):
        assert session_state.render(session_state.SessionState()) == ""

    def test_render_emits_tagged_blocks(self):
        turn = _chart_turn("t1", "PAR for FY25?", "PAR-30 stood at 4.2% in FY25.")
        rendered = session_state.render(
            session_state.from_turns([turn], _text_of)
        )

        assert "<established-figures>" in rendered
        assert "4.2%" in rendered
        assert "<sources-consulted>" in rendered

    def test_running_turns_are_ignored(self):
        turn = _chart_turn("t1", "PAR?", "PAR-30 stood at 4.2%.")
        turn["status"] = "running"

        state = session_state.from_turns([turn], _text_of)

        assert state.is_empty()

    def test_payload_round_trip(self):
        turn = _chart_turn("t1", "PAR for FY25?", "PAR-30 stood at 4.2% in FY25.")
        original = session_state.from_turns([turn], _text_of)

        restored = session_state.from_payload(session_state.to_payload(original))

        assert session_state.render(restored) == session_state.render(original)
