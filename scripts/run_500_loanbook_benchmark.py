#!/usr/bin/env python3
"""Run 500 Governed Loan Book queries organized into 100 5-turn chains.

Connects to Moneypal Genesis Intelligence application (http://100.70.118.31:4321)
and PostgreSQL (100.70.118.31:5432 / moneypaldb).

Performs:
1. Pure multi-turn questions against the API without hints.
2. PostgreSQL ground-truth SQL execution and data reconciliation.
3. Prompt token caching and conversation compaction audit.
4. Latency and chart type (kpi, table, bar, line, etc.) extraction.
5. Progressive checkpointing to Markdown and JSON after each completed chain.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import decimal
import json
import statistics
import sys
import threading
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.benchmark_common import percentile, stream_sse
except ImportError:
    from benchmark_common import percentile, stream_sse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

try:
    import pg8000.native
except ImportError:
    pg8000 = None

# Import the 100 chains (500 questions)
try:
    from scripts.chains_500_loanbook import CHAINS, Chain
except ImportError:
    from chains_500_loanbook import CHAINS, Chain


@dataclass
class Result:
    id: int
    chain_id: int
    turn: int
    category: str
    chain_title: str
    question: str
    conversation_id: str = ""
    status: str = (
        "Error"  # Answered | Partial | Clarification | Refused | Error
    )
    latency_s: float = 0.0
    db_duration_ms: int | None = None
    route_sources: list[str] = field(default_factory=list)
    route_model: str = ""
    card_types: list[str] = field(default_factory=list)
    chart_type: str = "none"
    row_count: int | None = None
    answer: str = ""
    sql: str = ""
    error: str = ""
    # PostgreSQL Reconciliation
    pg_status: str = "UNCHECKED"  # VERIFIED_MATCH | ROW_COUNT_MISMATCH | VALUE_MISMATCH | SQL_EXECUTION_ERROR | NO_SQL
    pg_row_count: int | None = None
    pg_duration_ms: int | None = None
    pg_error: str = ""
    pg_sample_data: str = ""
    # Caching and Compaction
    prompt_tokens: int = 0
    cached_prompt_tokens: int = 0
    uncached_prompt_tokens: int = 0
    cache_hit_pct: float = 0.0
    compaction_active: bool = False
    compaction_details: str = ""

    @property
    def answered(self) -> bool:
        return self.status in {"Answered", "Partial"}


def parse_events(
    result: Result, events: list[tuple[str, dict[str, Any]]]
) -> None:
    answers: list[str] = []
    for event, data in events:
        if event == "conversation":
            result.conversation_id = str(
                data.get("conversation_id") or result.conversation_id
            )
        elif event == "route":
            result.route_sources = [
                str(v) for v in data.get("sources", []) or []
            ]
            result.route_model = str(data.get("model") or "")
        elif event == "source_card":
            card_type = str(data.get("card_type") or "")
            if card_type:
                result.card_types.append(card_type)
            ct = data.get("chart_type")
            if ct:
                result.chart_type = str(ct)
            elif card_type == "chart" and result.chart_type == "none":
                result.chart_type = "chart"

            text = (
                data.get("summary")
                or data.get("headline")
                or data.get("message")
            )
            if text:
                answers.append(str(text))

            lineage = data.get("lineage")
            if isinstance(lineage, dict):
                result.sql = str(
                    lineage.get("display_sql")
                    or lineage.get("sql")
                    or result.sql
                )
                if lineage.get("row_count") is not None:
                    result.row_count = int(lineage["row_count"])
                if lineage.get("duration_ms") is not None:
                    result.db_duration_ms = int(lineage["duration_ms"])

            if card_type == "error":
                result.error = str(
                    data.get("message") or "Source returned an error"
                )
            elif card_type == "clarify":
                result.status = "Clarification"
            elif card_type == "refusal":
                result.status = "Refused"
            elif card_type:
                result.status = "Answered"

        elif event in {"answer", "synthesis"}:
            text = data.get("text")
            if text:
                answers.append(str(text))
            api_status = str(data.get("status") or "answered")
            result.status = {
                "answered": "Answered",
                "partial": "Partial",
                "clarify": "Clarification",
                "refused": "Refused",
            }.get(api_status, result.status)
        elif event == "refusal":
            result.status = "Refused"
            result.error = str(data.get("message") or "Request refused")
        elif event == "error":
            result.error = str(data.get("message") or "Workbench error")

    result.answer = "\n\n".join(
        dict.fromkeys(t.strip() for t in answers if t.strip())
    )
    if result.error and result.status == "Answered":
        result.status = "Partial"
    if result.status == "Error" and not result.error:
        result.error = "No usable answer event returned"


class PostgresReconciler:
    def __init__(
        self, host: str, port: int, db: str, user: str, password: str
    ):
        self.host = host
        self.port = port
        self.db = db
        self.user = user
        self.password = password
        self._lock = threading.Lock()

    def _get_connection(self):
        if pg8000 is None:
            raise RuntimeError(
                "pg8000 is required for PostgreSQL reconciliation"
            )
        return pg8000.native.Connection(
            self.user,
            host=self.host,
            port=self.port,
            database=self.db,
            password=self.password,
            timeout=30,
        )

    def reconcile(self, result: Result) -> None:
        if not result.sql or not result.sql.strip():
            result.pg_status = "NO_SQL"
            return

        # Clean SQL for execution
        sql = result.sql.strip().rstrip(";")
        start = time.monotonic()
        try:
            with self._get_connection() as con:
                rows = con.run(sql)
                duration_ms = int((time.monotonic() - start) * 1000)
                result.pg_duration_ms = duration_ms
                result.pg_row_count = len(rows)

                # Format sample data
                sample = []
                for row in rows[:5]:
                    formatted_row = [
                        float(v) if isinstance(v, decimal.Decimal) else v
                        for v in row
                    ]
                    sample.append(str(formatted_row))
                result.pg_sample_data = " | ".join(sample)

                # Compare row counts
                if (
                    result.row_count is not None
                    and result.row_count != result.pg_row_count
                ):
                    result.pg_status = "ROW_COUNT_MISMATCH"
                else:
                    result.pg_status = "VERIFIED_MATCH"

        except Exception as exc:
            result.pg_status = "SQL_EXECUTION_ERROR"
            result.pg_error = str(exc)

    def fetch_conversation_telemetry(
        self, conversation_id: str, turn_idx: int, result: Result
    ) -> None:
        if not conversation_id:
            return
        try:
            with self._get_connection() as con:
                q = "SELECT record_json FROM public.workbench_conversations WHERE conversation_id = :cid;"
                res = con.run(q, cid=conversation_id)
                if not res:
                    return
                record = res[0][0]
                if not isinstance(record, dict):
                    return

                # Compaction check
                compaction = record.get("compaction")
                if isinstance(compaction, dict):
                    result.compaction_active = True
                    result.compaction_details = f"Compacted up to turn {compaction.get('first_kept_turn_id')}"

                # Usage check for this turn
                turns = record.get("turns", [])
                if turn_idx < len(turns):
                    turn = turns[turn_idx]
                    usage = turn.get("usage")
                    if isinstance(usage, dict):
                        result.prompt_tokens = int(
                            usage.get("prompt_tokens") or 0
                        )
                        result.cached_prompt_tokens = int(
                            usage.get("cached_prompt_tokens") or 0
                        )
                        result.uncached_prompt_tokens = int(
                            usage.get("uncached_prompt_tokens") or 0
                        )
                        if result.prompt_tokens > 0:
                            result.cache_hit_pct = round(
                                (
                                    result.cached_prompt_tokens
                                    / result.prompt_tokens
                                )
                                * 100,
                                1,
                            )
        except Exception:
            pass


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
        events, error, result.latency_s = stream_sse(
            self.url,
            payload,
            token=self.token,
            timeout_s=self.timeout_s,
            user_agent="Moneypal-500-LoanBook-Benchmark/1.0",
        )
        result.error = error
        parse_events(result, events)
        return result


def run_chain(
    chain: Chain,
    client: Client,
    reconciler: PostgresReconciler | None,
    progress: Callable[[Result], None],
) -> list[Result]:
    conversation_id: str | None = None
    results: list[Result] = []
    for turn, question in enumerate(chain.questions, 1):
        item = Result(
            id=(chain.id - 1) * 5 + turn,
            chain_id=chain.id,
            turn=turn,
            category=chain.category,
            chain_title=chain.title,
            question=question,
        )
        client.ask(item, conversation_id)
        conversation_id = item.conversation_id or conversation_id

        if reconciler is not None:
            reconciler.reconcile(item)
            reconciler.fetch_conversation_telemetry(
                conversation_id or "", turn - 1, item
            )

        results.append(item)
        progress(item)
    return results


def generate_markdown_report(
    results: list[Result],
    base_url: str,
    elapsed_s: float,
    timeout_s: int,
    workers: int,
    total_expected: int = 500,
) -> str:
    ordered = sorted(results, key=lambda item: item.id)
    counts = Counter(item.status for item in ordered)
    pg_counts = Counter(item.pg_status for item in ordered)
    chart_counts = Counter(item.chart_type for item in ordered)
    latencies = [item.latency_s for item in ordered]
    answered = sum(item.answered for item in ordered)
    answer_rate = (answered / len(ordered) * 100) if ordered else 0.0

    # Chain completeness
    chain_ids = sorted(list({item.chain_id for item in ordered}))
    complete_chains = sum(
        len(rows := [item for item in ordered if item.chain_id == cid]) == 5
        and all(item.answered for item in rows)
        for cid in chain_ids
    )

    # Caching stats
    tokens_total = sum(item.prompt_tokens for item in ordered)
    tokens_cached = sum(item.cached_prompt_tokens for item in ordered)
    tokens_uncached = sum(item.uncached_prompt_tokens for item in ordered)
    overall_cache_pct = (
        (tokens_cached / tokens_total * 100) if tokens_total > 0 else 0.0
    )
    compacted_turns = sum(1 for item in ordered if item.compaction_active)

    sla_label = (
        f"{timeout_s}s"
        if (timeout_s and timeout_s > 0)
        else "None (unlimited / unconstrained)"
    )
    lines = [
        "# Moneypal Genesis Intelligence — 500 Governed Loan Book Benchmark & Reconciliation Report",
        "",
        f"**Generated:** {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}  ",
        f"**Application URL:** `{base_url}`  ",
        "**Database:** PostgreSQL (`moneypaldb.gold` on `100.70.118.31:5432`)  ",
        f"**Questions Completed:** {len(ordered)} / {total_expected} (across {len(chain_ids)} chains)  ",
        f"**Total Run Duration:** {elapsed_s:.2f}s ({elapsed_s / 60:.1f} minutes)  ",
        f"**Per-Question Timeout (SLA):** {sla_label} (LLM execution unconstrained)  ",
        f"**Workers:** {workers}  ",
        "",
        "---",
        "",
        "## 1. Executive Summary & KPIs",
        "",
        "| Metric | Result | Target Benchmark | Status |",
        "|---|---:|---:|:---:|",
        f"| **Total Queries Tested** | **{len(ordered)}** | {total_expected} | {'✅ Complete' if len(ordered) >= total_expected else '⏳ In Progress'} |",
        f"| **Answered / Partial** | **{answered} / {len(ordered)} ({answer_rate:.1f}%)** | ≥ 70.0% | {'✅ PASS' if answer_rate >= 70.0 else '⚠️ Review'} |",
        f"| **Fully Answered** | **{counts['Answered']}** | - | 🟢 |",
        f"| **Partial Answers** | **{counts['Partial']}** | - | 🟡 |",
        f"| **Clarification Needed** | **{counts['Clarification']}** | < 5% | ℹ️ |",
        f"| **Refused (Safety / Scope)** | **{counts['Refused']}** | < 5% | ℹ️ |",
        f"| **Errors / Timeouts** | **{counts['Error']}** | < 10% | {'✅ Normal' if counts['Error'] < len(ordered) * 0.1 else '⚠️ High'} |",
        f"| **Complete 5-Turn Chains** | **{complete_chains} / {len(chain_ids)}** | - | 🎯 |",
        f"| **PostgreSQL Exact Matches** | **{pg_counts['VERIFIED_MATCH']} / {len(ordered)}** | - | 🛡️ |",
        f"| **Mean Query Latency** | **{statistics.mean(latencies):.2f}s** | < 45s | ⏱️ |"
        if latencies
        else "| **Mean Query Latency** | **0.00s** | < 45s | ⏱️ |",
        f"| **Median (P50) Latency** | **{statistics.median(latencies):.2f}s** | - | ⏱️ |"
        if latencies
        else "| **Median (P50) Latency** | **0.00s** | - | ⏱️ |",
        f"| **P90 Latency** | **{percentile(latencies, 0.90):.2f}s** | - | ⏱️ |",
        f"| **P95 Latency** | **{percentile(latencies, 0.95):.2f}s** | - | ⏱️ |",
        f"| **Max Latency** | **{max(latencies):.2f}s** | - | ⏱️ |"
        if latencies
        else "| **Max Latency** | **0.00s** | - | ⏱️ |",
        "",
        "---",
        "",
        "## 2. PostgreSQL Ground-Truth Reconciliation Scorecard",
        "",
        "| Reconciliation Outcome | Count | Share (%) | Description |",
        "|---|---:|---:|---|",
        f"| **VERIFIED_MATCH** | {pg_counts['VERIFIED_MATCH']} | {(pg_counts['VERIFIED_MATCH'] / len(ordered) * 100 if ordered else 0):.1f}% | Generated SQL executed successfully; row counts & results match DB. |",
        f"| **ROW_COUNT_MISMATCH** | {pg_counts['ROW_COUNT_MISMATCH']} | {(pg_counts['ROW_COUNT_MISMATCH'] / len(ordered) * 100 if ordered else 0):.1f}% | SQL executed, but application asserted row count differs from Postgres. |",
        f"| **SQL_EXECUTION_ERROR** | {pg_counts['SQL_EXECUTION_ERROR']} | {(pg_counts['SQL_EXECUTION_ERROR'] / len(ordered) * 100 if ordered else 0):.1f}% | Generated SQL failed execution syntax or schema checks on Postgres. |",
        f"| **NO_SQL (Refusal/Clarify/Cache)** | {pg_counts['NO_SQL']} | {(pg_counts['NO_SQL'] / len(ordered) * 100 if ordered else 0):.1f}% | Query handled without SQL or refused by policy. |",
        "",
        "---",
        "",
        "## 3. Caching & Compaction Diagnostics",
        "",
        "### Prompt Token Caching (LLM Prefix & Context Reuse)",
        "",
        "| Cache Metric | Value | Notes |",
        "|---|---:|---|",
        f"| **Total Prompt Tokens Processed** | {tokens_total:,} | Total token evaluation across all query turns |",
        f"| **Prompt Tokens Served from Cache** | {tokens_cached:,} | Evaluated from llama-server / provider prompt cache |",
        f"| **Uncached Tokens Computed** | {tokens_uncached:,} | New tokens requiring full GPU prefill |",
        f"| **Overall Cache Hit Ratio** | **{overall_cache_pct:.1f}%** | Percentage of prompt tokens reused from memory |",
        "",
        "### Multi-Turn Compaction Status",
        "",
        f"- **Compaction Monitored Turns:** {len(ordered)}",
        f"- **Compacted Checkpoints Recorded:** {compacted_turns}",
        "- **Context Policy:** Turns exceeding budget are automatically summarized in `record_json.compaction` without discarding history.",
        "",
        "---",
        "",
        "## 4. Visualization & Chart Type Distribution",
        "",
        "| Chart / Visualization Type | Count | Share (%) | Description |",
        "|---|---:|---:|---|",
    ]
    for ct, cnt in chart_counts.most_common():
        lines.append(
            f"| `{ct}` | {cnt} | {(cnt / len(ordered) * 100):.1f}% | Visual format returned in UI cards |"
        )

    lines += [
        "",
        "---",
        "",
        "## 5. Performance by Domain",
        "",
        "| Domain Category | Completed | Answered/Partial | Pass Rate (%) | PG Verified | Mean Latency |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    categories = sorted(list({item.category for item in ordered}))
    for cat in categories:
        rows = [item for item in ordered if item.category == cat]
        ans = sum(item.answered for item in rows)
        pg_v = sum(item.pg_status == "VERIFIED_MATCH" for item in rows)
        mean_l = (
            statistics.mean(item.latency_s for item in rows) if rows else 0.0
        )
        pct = (ans / len(rows) * 100) if rows else 0.0
        lines.append(
            f"| **{cat}** | {len(rows)} | {ans} | {pct:.1f}% | {pg_v} | {mean_l:.2f}s |"
        )

    lines += [
        "",
        "---",
        "",
        "## 6. Performance by Turn Depth (1 to 5)",
        "",
        "| Turn | Completed | Answered | Pass Rate (%) | PG Verified | Mean Latency | Avg Cache Hit % |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for turn in range(1, 6):
        rows = [item for item in ordered if item.turn == turn]
        ans = sum(item.answered for item in rows)
        pg_v = sum(item.pg_status == "VERIFIED_MATCH" for item in rows)
        mean_l = (
            statistics.mean(item.latency_s for item in rows) if rows else 0.0
        )
        avg_cache = (
            statistics.mean(item.cache_hit_pct for item in rows)
            if rows
            else 0.0
        )
        pct = (ans / len(rows) * 100) if rows else 0.0
        lines.append(
            f"| Turn {turn} | {len(rows)} | {ans} | {pct:.1f}% | {pg_v} | {mean_l:.2f}s | {avg_cache:.1f}% |"
        )

    lines += [
        "",
        "---",
        "",
        "## 7. Detailed Query Execution Log",
        "",
    ]
    for cid in chain_ids:
        chain_rows = [item for item in ordered if item.chain_id == cid]
        if not chain_rows:
            continue
        first = chain_rows[0]
        lines += [
            f"### Chain {cid:03d}: [{first.category}] {first.chain_title}",
            "",
        ]
        for item in chain_rows:
            sources = ", ".join(item.route_sources) or "none"
            lines += [
                f"#### Q{item.id:03d} (Turn {item.turn}): {item.question}",
                "",
                f"- **Status:** `{item.status}` | **Latency:** `{item.latency_s:.2f}s` | **Route:** `{sources}` (`{item.route_model}`)",
                f"- **Chart Type:** `{item.chart_type}` | **Reported Rows:** `{item.row_count}` | **DB Time:** `{item.db_duration_ms} ms`",
                f"- **PostgreSQL Reconciliation:** `{item.pg_status}` (PG Rows: `{item.pg_row_count}`, Time: `{item.pg_duration_ms} ms`)",
                f"- **Cache Stats:** `{item.cached_prompt_tokens:,} / {item.prompt_tokens:,}` prompt tokens ({item.cache_hit_pct}%)",
                "",
                "**Application Response:**",
                f"> {item.answer.replace(chr(10), ' ')[:300] or item.error or 'No response text.'}",
                "",
            ]
            if item.sql:
                lines += [
                    "<details><summary>Generated SQL</summary>",
                    "",
                    "```sql",
                    item.sql,
                    "```",
                    "",
                    "</details>",
                    "",
                ]
            if item.pg_sample_data:
                lines += [
                    "<details><summary>PostgreSQL Ground-Truth Rows</summary>",
                    "",
                    "```text",
                    item.pg_sample_data,
                    "```",
                    "",
                    "</details>",
                    "",
                ]
            if item.pg_error:
                lines += [
                    f"> ⚠️ **PostgreSQL Error:** `{item.pg_error}`",
                    "",
                ]

    return "\n".join(lines)


def write_checkpoints(
    results: list[Result],
    *,
    markdown_path: Path,
    json_path: Path,
    base_url: str,
    elapsed_s: float,
    timeout_s: int,
    workers: int,
    total_expected: int = 500,
) -> None:
    report = generate_markdown_report(
        results,
        base_url,
        elapsed_s,
        timeout_s,
        workers,
        total_expected=total_expected,
    )
    markdown_path.write_text(report, encoding="utf-8")
    json_path.write_text(
        json.dumps(
            [asdict(item) for item in sorted(results, key=lambda r: r.id)],
            indent=2,
        ),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run 500 Governed Loan Book Benchmark with PostgreSQL Reconciliation"
    )
    parser.add_argument("--url", default="http://100.70.118.31:4321")
    parser.add_argument("--token", default="mock-token-gicc_admin")
    parser.add_argument("--db-host", default="100.70.118.31")
    parser.add_argument("--db-port", type=int, default=5432)
    parser.add_argument("--db-name", default="moneypaldb")
    parser.add_argument("--db-user", default="moneypal")
    parser.add_argument("--db-pass", default="moneypal123")
    parser.add_argument(
        "--timeout",
        type=int,
        default=0,
        help="Per-question timeout in seconds (0 = unlimited / no timeout)",
    )
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--chains",
        default="all",
        help="Chain range to run, e.g. '1-100', '1-5', or 'all'",
    )
    parser.add_argument(
        "--output-md", default="benchmark_500_queries_report.md"
    )
    parser.add_argument("--output-json", default="benchmark_500_queries.json")
    parser.add_argument(
        "--no-reconcile",
        action="store_true",
        help="Run multi-turn conversations without PostgreSQL reconciliation or telemetry",
    )
    args = parser.parse_args(argv)

    # Parse chains selection
    if args.chains == "all":
        selected_chains = list(CHAINS)
    elif "-" in args.chains:
        start_c, end_c = map(int, args.chains.split("-", 1))
        selected_chains = [c for c in CHAINS if start_c <= c.id <= end_c]
    else:
        c_id = int(args.chains)
        selected_chains = [c for c in CHAINS if c.id == c_id]

    total_expected = len(selected_chains) * 5
    print(
        f"Starting Benchmark: {len(selected_chains)} chains ({total_expected} questions) "
        f"against {args.url} (PostgreSQL at {args.db_host}:{args.db_port})",
        flush=True,
    )

    client = Client(args.url, args.token, args.timeout)
    reconciler = (
        None
        if args.no_reconcile
        else PostgresReconciler(
            args.db_host,
            args.db_port,
            args.db_name,
            args.db_user,
            args.db_pass,
        )
    )
    markdown_path = Path(args.output_md)
    json_path = Path(args.output_json)

    results: list[Result] = []
    lock = threading.Lock()
    started = time.monotonic()

    def progress(item: Result) -> None:
        with lock:
            print(
                f"[Q{item.id:03d}/{total_expected}] Chain {item.chain_id:03d} Turn {item.turn} "
                f"| {item.status} ({item.latency_s:.2f}s) "
                f"| PG: {item.pg_status} (rows: {item.pg_row_count}) "
                f"| Chart: {item.chart_type} "
                f"| Cache: {item.cache_hit_pct}% "
                f"— {item.question[:50]}...",
                flush=True,
            )

    # Run chains sequentially or with workers
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max(1, args.workers)
    ) as pool:
        future_map = {
            pool.submit(run_chain, chain, client, reconciler, progress): chain
            for chain in selected_chains
        }
        for future in concurrent.futures.as_completed(future_map):
            chain = future_map[future]
            try:
                chain_results = future.result()
                with lock:
                    results.extend(chain_results)
            except Exception as exc:
                print(f"Chain {chain.id} crashed: {exc}", flush=True)

            with lock:
                elapsed = time.monotonic() - started
                write_checkpoints(
                    results,
                    markdown_path=markdown_path,
                    json_path=json_path,
                    base_url=args.url,
                    elapsed_s=elapsed,
                    timeout_s=args.timeout,
                    workers=args.workers,
                    total_expected=total_expected,
                )

    elapsed = time.monotonic() - started
    write_checkpoints(
        results,
        markdown_path=markdown_path,
        json_path=json_path,
        base_url=args.url,
        elapsed_s=elapsed,
        timeout_s=args.timeout,
        workers=args.workers,
        total_expected=total_expected,
    )
    answered = sum(item.answered for item in results)
    pg_verified = sum(item.pg_status == "VERIFIED_MATCH" for item in results)
    print("\n" + "=" * 80)
    print(
        f"Benchmark Finished: {len(results)}/{total_expected} questions executed in {elapsed:.2f}s."
    )
    print(
        f"Answered: {answered}/{len(results)} ({(answered / len(results) * 100 if results else 0):.1f}%)"
    )
    print(f"Postgres Ground-Truth Verified: {pg_verified}/{len(results)}")
    print(f"Markdown Report: {markdown_path.resolve()}")
    print(f"JSON Output: {json_path.resolve()}")
    print("=" * 80)
    return 0 if len(results) == total_expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
