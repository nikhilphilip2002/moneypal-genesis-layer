#!/usr/bin/env python3
"""Benchmark 100 CFO/CEO/CGO questions against the live Workbench loan book.

The corpus is organised as 20 five-turn conversations. Turns within a conversation run
sequentially with the conversation ID returned by the API; independent conversations may
run concurrently. The runner records transport latency, database duration, routing,
answer status, row counts, SQL, and response text, and checkpoints Markdown and JSON after
each completed conversation.
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
    questions: tuple[str, str, str, str, str]


CHAINS: tuple[Chain, ...] = (
    Chain(1, "CEO", "Enterprise pulse", "Scale and account mix", (
        "How many sanctioned loan accounts are in the loan book?",
        "Break that down by account status.",
        "Now show it by scheme.",
        "Which application branches have the most accounts?",
        "Show the top 10 borrowers by principal outstanding.",
    )),
    Chain(2, "CEO", "Growth", "Disbursement trajectory", (
        "What is our total disbursed amount this financial year?",
        "Show the monthly trend.",
        "Compare it with the previous financial year.",
        "Break the current financial year down by application branch.",
        "Which five schemes disbursed the most?",
    )),
    Chain(3, "CEO", "Customer franchise", "Borrower reach and mix", (
        "How many distinct borrowers have sanctioned loan accounts?",
        "Break the borrower count down by scheme.",
        "Now split it by gender.",
        "Show borrower count by application branch.",
        "Which ten agents have the highest customer count?",
    )),
    Chain(4, "CEO", "Balance sheet", "Outstanding portfolio concentration", (
        "What is the current principal outstanding across the loan book?",
        "Break it down by scheme.",
        "Now show it by application branch.",
        "Split it by account status.",
        "Which ten borrowers have the largest principal outstanding?",
    )),
    Chain(5, "CEO", "Risk", "NPA profile", (
        "What is our current NPA ratio?",
        "Break it down by scheme.",
        "Now show it by application branch.",
        "Which borrowers have the highest NPA principal outstanding?",
        "How many accounts are currently classified as NPA?",
    )),
    Chain(6, "CEO", "Risk", "Portfolio at risk", (
        "What is our current PAR 30 ratio?",
        "Break PAR 30 down by scheme.",
        "Now show PAR 30 by application branch.",
        "What is our current PAR 90 ratio?",
        "Which schemes have the highest overdue principal?",
    )),
    Chain(7, "CEO", "Strategy", "Product and scheme portfolio", (
        "Which schemes have the largest principal outstanding?",
        "For those schemes, show total disbursed amount.",
        "Also show their sanctioned loan count.",
        "Which schemes have the highest average ticket size?",
        "Which schemes combine high growth with low PAR 30?",
    )),
    Chain(8, "CFO", "Conversion", "Sanction-to-disbursement", (
        "Compare total sanctioned amount with total disbursed amount.",
        "Show the difference by scheme.",
        "Now show it by application branch.",
        "What is the sanction-to-disbursement conversion rate?",
        "Which schemes have the lowest conversion rate?",
    )),
    Chain(9, "CFO", "Collections", "Collection efficiency", (
        "What is our collection efficiency this month?",
        "Show total amount due and total amount collected behind that result.",
        "Break collection efficiency down by scheme.",
        "Now show it by application branch.",
        "Compare this month with last month.",
    )),
    Chain(10, "CFO", "Income", "Interest performance", (
        "How much interest have we collected this financial year?",
        "Show the monthly trend.",
        "Break it down by scheme.",
        "Now show it by application branch.",
        "What is the weighted average contractual interest rate?",
    )),
    Chain(11, "CFO", "Repayment", "Principal cash flows", (
        "How much principal has been repaid this financial year?",
        "Show the monthly principal repayment trend.",
        "Break principal repaid down by scheme.",
        "Now compare principal repaid with disbursed amount.",
        "Which schemes have the lowest principal repayment percentage?",
    )),
    Chain(12, "CFO", "Unit economics", "Ticket size", (
        "What is the average sanctioned ticket size?",
        "Break average ticket size down by scheme.",
        "Now show it by application branch.",
        "Which ten borrowers received the largest sanctioned amounts?",
        "How has average ticket size changed by month this year?",
    )),
    Chain(13, "CFO", "Liquidity", "Disbursement and collection cash flow", (
        "Show monthly disbursements and total collections for this financial year.",
        "Which months had collections below disbursements?",
        "What was the largest monthly cash-flow gap?",
        "Break the current total collection amount down by scheme.",
        "Which branches collected the most this financial year?",
    )),
    Chain(14, "CFO", "Capital", "Equity and book leverage", (
        "What is the current share capital balance in the general ledger?",
        "Show the general-ledger accounts included in that balance.",
        "What is current principal outstanding relative to share capital?",
        "How much total interest is outstanding?",
        "Break interest outstanding down by scheme.",
    )),
    Chain(15, "CGO", "Distribution", "Agent customer franchise", (
        "Show the top 10 agents with the highest customer count.",
        "Show me customers under Vanitha.",
        "Add scheme name and tenure.",
        "Also include the disbursed loan amount.",
        "Show the linked loan account numbers.",
    )),
    Chain(16, "CGO", "Distribution", "Branch customer franchise", (
        "List customers in Ujire.",
        "Add scheme name and tenure.",
        "Also include disbursed amount.",
        "How many distinct customers are in that branch?",
        "What is total principal outstanding for that branch?",
    )),
    Chain(17, "CGO", "Product growth", "Scheme origination", (
        "Which ten schemes have the highest sanctioned loan count?",
        "Show their total sanctioned amount.",
        "Now add total disbursed amount.",
        "What is their average ticket size?",
        "Which of those schemes grew fastest this financial year?",
    )),
    Chain(18, "CGO", "Inclusion", "Gender participation", (
        "How many borrowers are female and how many are male?",
        "Show total disbursed amount by gender.",
        "Now show average sanctioned ticket size by gender.",
        "Break female borrower count down by scheme.",
        "Which application branches serve the most female borrowers?",
    )),
    Chain(19, "CGO", "Branch growth", "Origination network", (
        "Rank application branches by total disbursed amount this financial year.",
        "Add sanctioned loan count for each branch.",
        "Now add distinct borrower count.",
        "Which branch has the highest average ticket size?",
        "Which branches have declining monthly disbursements?",
    )),
    Chain(20, "CGO", "Agent productivity", "Agent volume and quality", (
        "Rank the top 10 agents by sanctioned loan count.",
        "Now rank them by total disbursed amount.",
        "Add distinct borrower count.",
        "Which agents have the highest principal outstanding?",
        "For the leading agent, show the linked customers.",
    )),
)


@dataclass
class Result:
    id: int
    chain_id: int
    turn: int
    role: str
    category: str
    chain_title: str
    question: str
    conversation_id: str = ""
    status: str = "Error"
    latency_s: float = 0.0
    db_duration_ms: int | None = None
    route_sources: list[str] = field(default_factory=list)
    route_model: str = ""
    card_types: list[str] = field(default_factory=list)
    row_count: int | None = None
    answer: str = ""
    sql: str = ""
    error: str = ""

    @property
    def answered(self) -> bool:
        return self.status in {"Answered", "Partial"}


def load_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


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
                "User-Agent": "Moneypal-Executive-Loanbook-Chains/1.0",
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
        except Exception as exc:  # noqa: BLE001 - benchmark records and continues
            result.error = f"Unexpected error: {exc}"
        result.latency_s = time.monotonic() - started
        parse_events(result, events)
        return result


def run_chain(chain: Chain, client: Client, progress: Callable[[Result], None]) -> list[Result]:
    conversation_id: str | None = None
    results: list[Result] = []
    for turn, question in enumerate(chain.questions, 1):
        item = Result(
            id=(chain.id - 1) * 5 + turn,
            chain_id=chain.id,
            turn=turn,
            role=chain.role,
            category=chain.category,
            chain_title=chain.title,
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
    ordered = sorted(values)
    index = max(0, math.ceil(pct * len(ordered)) - 1)
    return ordered[index]


def markdown_report(
    results: list[Result], base_url: str, elapsed_s: float, timeout_s: int, workers: int,
) -> str:
    ordered = sorted(results, key=lambda item: item.id)
    counts = Counter(item.status for item in ordered)
    latencies = [item.latency_s for item in ordered]
    answered = sum(item.answered for item in ordered)
    answer_rate = answered / len(ordered) * 100 if ordered else 0.0
    complete_chains = sum(
        len(rows := [item for item in ordered if item.chain_id == chain.id]) == 5
        and all(item.answered for item in rows)
        for chain in CHAINS
    )
    lines = [
        "# GICC Loan Book — 100-Question Executive Chain Benchmark",
        "",
        f"**Generated:** {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"**Endpoint:** `{base_url}`",
        f"**Questions completed:** {len(ordered)} / 100",
        f"**Wall-clock time:** {elapsed_s:.2f}s",
        f"**Per-question client SLA:** {timeout_s}s",
        f"**Concurrent chain workers:** {workers}",
        "",
        "## Summary",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Answered or partial | {answered} / {len(ordered)} ({answer_rate:.1f}%) |",
        f"| Fully answered | {counts['Answered']} |",
        f"| Partial | {counts['Partial']} |",
        f"| Clarification | {counts['Clarification']} |",
        f"| Refused | {counts['Refused']} |",
        f"| Errors | {counts['Error']} |",
        f"| Complete five-turn chains | {complete_chains} / 20 |",
        (f"| Mean latency | {statistics.mean(latencies):.2f}s |" if latencies else "| Mean latency | 0.00s |"),
        (f"| Median latency | {statistics.median(latencies):.2f}s |" if latencies else "| Median latency | 0.00s |"),
        f"| P90 latency | {percentile(latencies, 0.90):.2f}s |",
        f"| P95 latency | {percentile(latencies, 0.95):.2f}s |",
        f"| Maximum latency | {max(latencies):.2f}s |" if latencies else "| Maximum latency | 0.00s |",
        "",
        "## Results by executive role",
        "",
        "| Role | Completed | Answered/partial | Errors | Mean latency |",
        "|---|---:|---:|---:|---:|",
    ]
    for role in ("CEO", "CFO", "CGO"):
        rows = [item for item in ordered if item.role == role]
        mean = statistics.mean(item.latency_s for item in rows) if rows else 0.0
        lines.append(
            f"| {role} | {len(rows)} | {sum(item.answered for item in rows)} | "
            f"{sum(item.status == 'Error' for item in rows)} | {mean:.2f}s |"
        )
    lines += [
        "",
        "## Results by turn depth",
        "",
        "| Turn | Completed | Answered/partial | Errors | Mean latency |",
        "|---:|---:|---:|---:|---:|",
    ]
    for turn in range(1, 6):
        rows = [item for item in ordered if item.turn == turn]
        mean = statistics.mean(item.latency_s for item in rows) if rows else 0.0
        lines.append(
            f"| {turn} | {len(rows)} | {sum(item.answered for item in rows)} | "
            f"{sum(item.status == 'Error' for item in rows)} | {mean:.2f}s |"
        )
    lines += ["", "## Detailed results", ""]
    for chain in CHAINS:
        lines += [f"### Chain {chain.id}: {chain.role} — {chain.title}", ""]
        for item in [row for row in ordered if row.chain_id == chain.id]:
            sources = ", ".join(item.route_sources) or "none"
            lines += [
                f"#### Q{item.id:03d} / Turn {item.turn}: {item.question}",
                "",
                f"- Status: **{item.status}**",
                f"- Latency: `{item.latency_s:.2f}s`",
                f"- Route: `{sources}` via `{item.route_model or 'unknown'}`",
                f"- Card types: `{', '.join(item.card_types) or 'none'}`",
                f"- Rows: `{item.row_count if item.row_count is not None else 'n/a'}`",
                f"- Database duration: `{item.db_duration_ms if item.db_duration_ms is not None else 'n/a'} ms`",
                "",
                item.answer or item.error or "No response text.",
                "",
            ]
            if item.sql:
                lines += ["<details><summary>SQL</summary>", "", "```sql", item.sql, "```", "", "</details>", ""]
    lines += [
        "## Methodology",
        "",
        "- Exactly 100 questions are grouped into 20 five-turn conversations.",
        "- Turns in each chain share the API-issued conversation ID and run sequentially.",
        "- Independent chains may run concurrently; wall-clock time therefore differs from summed latency.",
        "- No source is pinned. External sources are disabled so every question must be handled by the loan book or fail visibly.",
        "- 'Answered' is based on the Workbench SSE answer/card contract, not a separate semantic correctness judge.",
        "- SQL, row counts, route, and database duration are retained for manual correctness review.",
        "",
    ]
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run 100 executive loan-book questions in 20 chains")
    parser.add_argument("--url", default="http://100.70.118.31:4321")
    parser.add_argument("--token", default=None)
    parser.add_argument("--env-file", default=".env.prod")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output-md", default="benchmark_100_executive_loanbook_chains.md")
    parser.add_argument("--output-json", default="benchmark_100_executive_loanbook_chains.json")
    parser.add_argument("--questions-only", action="store_true")
    args = parser.parse_args()

    if len(CHAINS) != 20 or sum(len(chain.questions) for chain in CHAINS) != 100:
        raise RuntimeError("The benchmark corpus must contain exactly 20 chains and 100 questions")
    env = load_env(Path(args.env_file))
    token = args.token or env.get("BENCHMARK_AUTH_TOKEN") or "mock-token-gicc_admin"
    markdown = Path(args.output_md)
    json_path = Path(args.output_json)
    if args.questions_only:
        write_outputs(
            [], markdown=markdown, json_path=json_path, base_url=args.url, elapsed_s=0.0,
            timeout_s=args.timeout, workers=args.workers,
        )
        print(f"Question corpus written to {markdown.resolve()}")
        return 0

    client = Client(args.url, token, args.timeout)
    results: list[Result] = []
    lock = threading.Lock()
    started = time.monotonic()

    def progress(item: Result) -> None:
        with lock:
            print(
                f"[{item.id:03d}/100] chain={item.chain_id:02d} turn={item.turn} {item.role} "
                f"{item.status} {item.latency_s:.2f}s — {item.question}",
                flush=True,
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        future_map = {pool.submit(run_chain, chain, client, progress): chain for chain in CHAINS}
        for future in concurrent.futures.as_completed(future_map):
            chain = future_map[future]
            try:
                results.extend(future.result())
            except Exception as exc:  # noqa: BLE001 - preserve remaining benchmark chains
                print(f"Chain {chain.id} crashed: {exc}", flush=True)
            write_outputs(
                results, markdown=markdown, json_path=json_path,
                base_url=args.url, elapsed_s=time.monotonic() - started,
                timeout_s=args.timeout, workers=args.workers,
            )

    elapsed = time.monotonic() - started
    write_outputs(
        results, markdown=markdown, json_path=json_path, base_url=args.url, elapsed_s=elapsed,
        timeout_s=args.timeout, workers=args.workers,
    )
    answered = sum(item.answered for item in results)
    print(
        f"Completed {len(results)}/100: {answered} answered/partial, "
        f"{sum(item.status == 'Error' for item in results)} errors in {elapsed:.2f}s",
        flush=True,
    )
    print(f"Report: {markdown.resolve()}", flush=True)
    print(f"Raw results: {json_path.resolve()}", flush=True)
    return 0 if len(results) == 100 else 1


if __name__ == "__main__":
    raise SystemExit(main())
