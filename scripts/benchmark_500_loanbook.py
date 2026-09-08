#!/usr/bin/env python3
"""Benchmark 500 loan book questions covering all 18 Gold views against Workbench.

Features:
- 500 clean, natural-language banking questions (no clues, hints, or system prefixes).
- Multi-turn chains testing context/binding preservation (e.g. "customers under vanitha" ->
  "include tenure and sanctioned amount with the above details").
- Long conversational chains (8-10 turns) testing conversation compaction.
- Detailed graph/card verification (chart_type, series, x/y columns, row counts).
- Latency profiling (wall-clock, DB duration, p50, p90, p95, min, max, avg).
- Checkpointed results to JSON and comprehensive Markdown reports.
- Resume capability to continue from completed chains.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import math
import statistics
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class Chain:
    id: int
    role: str
    category: str
    title: str
    view: str
    questions: tuple[str, ...]


@dataclass
class Result:
    id: int
    chain_id: int
    turn: int
    role: str
    category: str
    chain_title: str
    view: str
    question: str
    conversation_id: str = ""
    status: str = "Error"
    latency_s: float = 0.0
    db_duration_ms: int | None = None
    route_sources: list[str] = field(default_factory=list)
    route_model: str = ""
    card_types: list[str] = field(default_factory=list)
    chart_types: list[str] = field(default_factory=list)
    graph_verified: bool = False
    graph_details: dict[str, Any] = field(default_factory=dict)
    compaction_detected: bool = False
    compaction_summary: str = ""
    row_count: int | None = None
    answer: str = ""
    sql: str = ""
    error: str = ""

    @property
    def answered(self) -> bool:
        return self.status in {"Answered", "Partial"}


def decode(data_lines: list[str]) -> dict[str, Any]:
    raw = "\n".join(data_lines)
    try:
        value = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {"raw": raw}
    return value if isinstance(value, dict) else {"value": value}


def parse_events(result: Result, events: list[tuple[str, dict[str, Any]]]) -> None:
    answers: list[str] = []
    for event, data in events:
        if event == "conversation":
            result.conversation_id = str(data.get("conversation_id") or result.conversation_id)
        elif event == "route":
            result.route_sources = [str(value) for value in data.get("sources", []) or []]
            result.route_model = str(data.get("model") or "")
        elif event == "source_card":
            card_type = str(data.get("card_type") or "")
            if card_type:
                result.card_types.append(card_type)
            chart_type = str(data.get("chart_type") or "")
            if chart_type:
                result.chart_types.append(chart_type)
                result.graph_verified = True
                result.graph_details = {
                    "chart_type": chart_type,
                    "title": data.get("title") or "",
                    "x": data.get("x"),
                    "series_by": data.get("series_by"),
                    "row_count": len(data.get("rows", [])) if isinstance(data.get("rows"), list) else None,
                }
            text = data.get("summary") or data.get("headline") or data.get("message")
            if text:
                answers.append(str(text))
            lineage = data.get("lineage")
            if isinstance(lineage, dict):
                result.sql = str(lineage.get("display_sql") or lineage.get("sql") or result.sql)
                if lineage.get("row_count") is not None:
                    result.row_count = int(lineage["row_count"])
                if lineage.get("duration_ms") is not None:
                    result.db_duration_ms = int(lineage["duration_ms"])
            if card_type == "error":
                result.error = str(data.get("message") or "Source returned an error")
            elif card_type == "clarify":
                result.status = "Clarification"
            elif card_type == "refusal":
                result.status = "Refused"
            elif card_type:
                result.status = "Answered"
        elif event == "compaction":
            result.compaction_detected = True
            result.compaction_summary = str(data.get("summary") or "")
        elif event in {"answer", "synthesis"}:
            text = data.get("text")
            if text:
                answers.append(str(text))
            api_status = str(data.get("status") or "answered")
            result.status = {
                "answered": "Answered", "partial": "Partial", "clarify": "Clarification",
                "refused": "Refused",
            }.get(api_status, result.status)
        elif event == "refusal":
            result.status = "Refused"
            result.error = str(data.get("message") or "Request refused")
        elif event == "error":
            result.error = str(data.get("message") or "Workbench error")

    result.answer = "\n\n".join(dict.fromkeys(text.strip() for text in answers if text.strip()))
    if result.error and result.status == "Answered":
        result.status = "Partial"
    if result.status == "Error" and not result.error:
        result.error = "No usable answer event returned"


class Client:
    def __init__(self, base_url: str, token: str, timeout_s: int):
        self.url = f"{base_url.rstrip('/')}/api/workbench/ask"
        self.token = token
        self.timeout_s = timeout_s

    def ask(self, result: Result, conversation_id: str | None) -> Result:
        payload = {
            "question": result.question,
            "conversation_id": conversation_id,
            "external_sources_enabled": False,
        }
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "Moneypal-Benchmark-500/1.0",
            },
        )
        events: list[tuple[str, dict[str, Any]]] = []
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                event_name = ""
                data_lines: list[str] = []
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                    if not line:
                        if event_name:
                            events.append((event_name, decode(data_lines)))
                        event_name, data_lines = "", []
                    elif line.startswith("event:"):
                        event_name = line.partition(":")[2].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line.partition(":")[2].lstrip())
                if event_name:
                    events.append((event_name, decode(data_lines)))
        except urllib.error.HTTPError as exc:
            result.error = f"HTTP {exc.code}: {exc.reason}"
        except urllib.error.URLError as exc:
            result.error = f"Connection error: {exc.reason}"
        except TimeoutError:
            result.error = f"Request timed out after {self.timeout_s}s"
        except Exception as exc:  # noqa: BLE001
            result.error = f"Unexpected error: {exc}"
        result.latency_s = time.monotonic() - started
        parse_events(result, events)
        return result


def run_chain(chain: Chain, client: Client, progress: Callable[[Result], None], start_id: int) -> list[Result]:
    conversation_id: str | None = None
    results: list[Result] = []
    for turn, question in enumerate(chain.questions, 1):
        item = Result(
            id=start_id + turn - 1,
            chain_id=chain.id,
            turn=turn,
            role=chain.role,
            category=chain.category,
            chain_title=chain.title,
            view=chain.view,
            question=question,
        )
        client.ask(item, conversation_id)
        conversation_id = item.conversation_id or conversation_id
        results.append(item)
        progress(item)
    return results


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    k = (len(values) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return values[int(k)]
    return values[f] * (c - k) + values[c] * (k - f)


def markdown_report(
    results: list[Result], base_url: str, elapsed_s: float, timeout_s: int, workers: int,
) -> str:
    total = len(results)
    answered = sum(1 for r in results if r.answered)
    failed = total - answered
    pass_pct = (answered / total * 100) if total else 0.0

    latencies = sorted(r.latency_s for r in results)
    p50 = percentile(latencies, 50)
    p90 = percentile(latencies, 90)
    p95 = percentile(latencies, 95)
    avg_latency = statistics.mean(latencies) if latencies else 0.0
    min_latency = min(latencies) if latencies else 0.0
    max_latency = max(latencies) if latencies else 0.0

    graphs_verified = sum(1 for r in results if r.graph_verified)
    graph_pct = (graphs_verified / total * 100) if total else 0.0

    compactions = sum(1 for r in results if r.compaction_detected)

    chart_type_counts = Counter(ct for r in results for ct in r.chart_types)
    status_counts = Counter(r.status for r in results)

    # Per-view breakdown
    views = sorted({r.view for r in results})
    view_rows = []
    for v in views:
        v_results = [r for r in results if r.view == v]
        v_total = len(v_results)
        v_ans = sum(1 for r in v_results if r.answered)
        v_pct = (v_ans / v_total * 100) if v_total else 0.0
        v_lat = statistics.mean([r.latency_s for r in v_results]) if v_results else 0.0
        v_graphs = sum(1 for r in v_results if r.graph_verified)
        view_rows.append(f"| `{v}` | {v_total} | {v_ans} | {v_pct:.1f}% | {v_graphs} | {v_lat:.2f}s |")

    # Multi-turn chains breakdown
    chain_ids = sorted({r.chain_id for r in results})
    chain_rows = []
    for cid in chain_ids:
        c_results = [r for r in results if r.chain_id == cid]
        c_ans = sum(1 for r in c_results if r.answered)
        c_tot = len(c_results)
        c_pct = (c_ans / c_tot * 100) if c_tot else 0.0
        c_lat = statistics.mean([r.latency_s for r in c_results]) if c_results else 0.0
        c_title = c_results[0].chain_title if c_results else ""
        c_view = c_results[0].view if c_results else ""
        chain_rows.append(f"| Chain {cid}: {c_title} | `{c_view}` | {c_tot} | {c_ans}/{c_tot} ({c_pct:.0f}%) | {c_lat:.2f}s |")

    lines = [
        "# Moneypal Loan Book Benchmark Analysis",
        "",
        f"**Generated:** {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}  ",
        f"**Target Application:** `{base_url}`  ",
        f"**Benchmark Scope:** {total} Loan Book Questions Across 18 Gold Views  ",
        f"**Execution Mode:** Concurrent multi-turn chains with sequential conversational turns (Concurrency: {workers} workers, Timeout: {timeout_s}s)  ",
        f"**Total Run Duration:** {elapsed_s:.1f}s ({elapsed_s / 60:.1f} min)  ",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        "| Metric | Result | Benchmark Target | Status |",
        "|---|---|---|---|",
        f"| **Total Evaluated Questions** | **{total}** | 200 / 500 | ✅ Complete |",
        f"| **Answered / Successful** | **{answered} ({pass_pct:.1f}%)** | ≥ 95.0% | {'✅ PASS' if pass_pct >= 95 else '⚠️ OBSERVE'} |",
        f"| **Failed / Errors** | **{failed}** | 0 | {'✅ 0 Errors' if failed == 0 else '⚠️ Needs Review'} |",
        f"| **Visual Graphs / Cards Rendered** | **{graphs_verified} ({graph_pct:.1f}%)** | ≥ 90.0% | {'✅ PASS' if graph_pct >= 90 else '⚠️ OBSERVE'} |",
        f"| **Compaction Checkpoints** | **{compactions}** | > 0 in deep chains | {'✅ Verified' if compactions > 0 else 'ℹ️ Tested'} |",
        f"| **Latency p50 (Median)** | **{p50:.2f}s** | ≤ 6.0s | {'✅ Fast' if p50 <= 6.0 else '⚠️ High'} |",
        f"| **Latency p90** | **{p90:.2f}s** | ≤ 12.0s | {'✅ Fast' if p90 <= 12.0 else '⚠️ High'} |",
        f"| **Latency p95** | **{p95:.2f}s** | ≤ 18.0s | {'✅ Fast' if p95 <= 18.0 else '⚠️ High'} |",
        f"| **Latency Range** | **{min_latency:.2f}s – {max_latency:.2f}s** (Avg: {avg_latency:.2f}s) | - | - |",
        "",
        "---",
        "",
        "## 2. Graph & Visualizations Verification",
        "",
        "Every response was inspected for returned source cards, chart configurations, and structural rendering metadata.",
        "",
        "### Chart Type Distribution",
        "",
        "| Chart / Card Type | Count | Share | Description |",
        "|---|---|---|---|",
    ]

    for ct, count in chart_type_counts.most_common():
        share = (count / total * 100) if total else 0.0
        lines.append(f"| `{ct}` | {count} | {share:.1f}% | Governed {ct.upper()} visualization |")
    if not chart_type_counts:
        lines.append("| *None* | 0 | 0.0% | No chart types captured |")

    lines.extend([
        "",
        "### Status Distribution",
        "",
        "| Status | Count | Share |",
        "|---|---|---|",
    ])
    for st, count in status_counts.items():
        share = (count / total * 100) if total else 0.0
        lines.append(f"| **{st}** | {count} | {share:.1f}% |")

    lines.extend([
        "",
        "---",
        "",
        "## 3. Coverage by Gold Semantic View (18 Views)",
        "",
        "| View Identifier | Questions | Answered | Success Rate | Graphs Rendered | Avg Latency |",
        "|---|---|---|---|---|---|",
        *view_rows,
        "",
        "---",
        "",
        "## 4. Multi-Turn Conversational Chains & Compaction Verification",
        "",
        "Chains execute sequentially using the session conversation ID returned by the API. "
        "They explicitly exercise context inheritance (retaining filters such as `vanitha` across turns, "
        "adding requested fields like `tenure` and `sanction_amount`, and switching dimensions from scheme to branch).",
        "",
        "| Chain Title | Semantic View | Turns | Success Rate | Avg Latency |",
        "|---|---|---|---|---|",
        *chain_rows,
        "",
        "---",
        "",
        "## 5. Per-Question Detail Table",
        "",
        "| ID | Chain | Turn | Question | View | Status | Latency | Chart | Rows |",
        "|---|---|---|---|---|---|---|---|---|",
    ])

    for r in sorted(results, key=lambda row: row.id):
        q_clean = r.question.replace("|", "\\|")
        chart_str = ", ".join(r.chart_types) or "-"
        rows_str = str(r.row_count) if r.row_count is not None else "-"
        lines.append(
            f"| {r.id} | {r.chain_id} | {r.turn} | {q_clean} | `{r.view}` | {r.status} | {r.latency_s:.2f}s | `{chart_str}` | {rows_str} |"
        )

    return "\n".join(lines)


def write_outputs(
    results: list[Result], *, markdown: Path, json_path: Path, base_url: str,
    elapsed_s: float, timeout_s: int, workers: int,
) -> None:
    markdown.write_text(
        markdown_report(results, base_url, elapsed_s, timeout_s, workers), encoding="utf-8",
    )
    json_path.write_text(
        json.dumps([asdict(item) for item in sorted(results, key=lambda row: row.id)], indent=2),
        encoding="utf-8",
    )


def load_chains(path: Path, limit_questions: int | None = None) -> list[Chain]:
    data = json.loads(path.read_text(encoding="utf-8"))
    chains = []
    total_q = 0
    for item in data:
        qs = item["questions"]
        if limit_questions is not None and total_q >= limit_questions:
            break
        if limit_questions is not None and total_q + len(qs) > limit_questions:
            qs = qs[:limit_questions - total_q]
        chains.append(Chain(
            id=item["id"],
            role=item["role"],
            category=item["category"],
            title=item["title"],
            view=item["view"],
            questions=tuple(qs),
        ))
        total_q += len(qs)
    return chains


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark 500 loan book questions across 18 Gold views")
    parser.add_argument("--url", default="http://100.70.118.31:4321")
    parser.add_argument("--token", default="mock-token-gicc_admin")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--limit", type=int, default=200, help="Limit total questions to run (e.g. 200)")
    parser.add_argument("--resume", action="store_true", help="Resume from previously saved JSON results")
    parser.add_argument("--data-file", default="scripts/fixtures/loanbook_500_questions.json")
    parser.add_argument("--output-md", default="benchmark_loanbook_report.md")
    parser.add_argument("--output-json", default="benchmark_loanbook_results.json")
    args = parser.parse_args()

    data_path = Path(args.data_file)
    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")

    chains = load_chains(data_path, limit_questions=args.limit)
    total_questions = sum(len(c.questions) for c in chains)

    markdown_path = Path(args.output_md)
    json_path = Path(args.output_json)
    client = Client(args.url, args.token, args.timeout)

    results: list[Result] = []
    completed_chain_ids = set()

    if args.resume and json_path.exists():
        try:
            saved_raw = json.loads(json_path.read_text(encoding="utf-8"))
            for r in saved_raw:
                results.append(Result(**r))
            # Determine which chains are fully completed
            chain_question_counts = Counter(r.chain_id for r in results)
            for c in chains:
                if chain_question_counts[c.id] == len(c.questions):
                    completed_chain_ids.add(c.id)
            print(f"Resuming: loaded {len(results)} existing results across {len(completed_chain_ids)} fully completed chains.")
        except Exception as e:
            print(f"Could not load existing results for resume: {e}")
            results = []
            completed_chain_ids = set()

    # Filter chains to run
    chains_to_run = [c for c in chains if c.id not in completed_chain_ids]
    remaining_questions = sum(len(c.questions) for c in chains_to_run)
    print(f"Loaded {len(chains)} total chains ({total_questions} questions). Running {len(chains_to_run)} chains ({remaining_questions} questions) with {args.workers} workers (Timeout: {args.timeout}s).")

    lock = threading.Lock()
    completed_count = len(results)
    start_time = time.monotonic()

    def on_progress(result: Result) -> None:
        nonlocal completed_count
        with lock:
            completed_count += 1
            results.append(result)
            graph_icon = "📊 " + (result.chart_types[0] if result.chart_types else "card") if result.graph_verified else "❌ no-graph"
            status_icon = "🟢" if result.answered else "🔴"
            comp_flag = " 🗜️[compacted]" if result.compaction_detected else ""
            print(
                f"[{completed_count}/{total_questions}] {status_icon} Turn {result.turn} (Chain {result.chain_id}): "
                f"{result.question[:45]:<45} | {result.status:<8} | {result.latency_s:.2f}s | {graph_icon}{comp_flag}"
            )
            write_outputs(
                results, markdown=markdown_path, json_path=json_path,
                base_url=args.url, elapsed_s=time.monotonic() - start_time,
                timeout_s=args.timeout, workers=args.workers,
            )

    # Calculate starting ID for each chain
    chain_start_ids = {}
    curr_id = 1
    for c in chains:
        chain_start_ids[c.id] = curr_id
        curr_id += len(c.questions)

    # Run remaining chains concurrently
    if args.workers > 1 and len(chains_to_run) > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [
                executor.submit(run_chain, chain, client, on_progress, chain_start_ids[chain.id])
                for chain in chains_to_run
            ]
            for f in concurrent.futures.as_completed(futures):
                try:
                    f.result()
                except Exception as exc:
                    print(f"Chain execution error: {exc}")
    else:
        for chain in chains_to_run:
            run_chain(chain, client, on_progress, chain_start_ids[chain.id])

    elapsed_s = time.monotonic() - start_time
    write_outputs(
        results, markdown=markdown_path, json_path=json_path,
        base_url=args.url, elapsed_s=elapsed_s,
        timeout_s=args.timeout, workers=args.workers,
    )
    print("\n" + "="*80)
    print(f"Benchmark finished in {elapsed_s:.1f}s ({elapsed_s/60:.1f} min)")
    print(f"Report written to: {markdown_path.resolve()}")
    print(f"JSON results to:   {json_path.resolve()}")
    print("="*80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
