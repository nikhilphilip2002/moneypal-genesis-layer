#!/usr/bin/env python3
"""Run a 50-question unpinned Workbench routing and answer benchmark.

Evaluates the 'Top 50 questions an AI Assistant should answer' across 7 key business domains:
  A. CEO / Enterprise — 'What is happening in my business?' (Q1-10)
  B. Sales & Distribution — 'Where is growth coming from?' (Q11-18)
  C. Credit & Risk — 'Where is my risk?' (Q19-28)
  D. Collections & Recovery — 'Where should we focus?' (Q29-35)
  E. Finance — 'Where are we making money?' (Q36-41)
  F. Operations / Technology — 'What is slowing the business?' (Q42-45)
  G. Compliance / Legal / Audit / HR / Strategy (Q46-50)

The HTTP request body intentionally contains only the user's question. Expected sources
and category labels are evaluator-side metadata and are never sent to the application.

Configuration, token, timeout, and endpoint defaults follow the existing production benchmark
runners and may be overridden from the command line or environment files (.env.prod / .env).
The report is checkpointed to the output Markdown file after every completed request.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# --------------------------------------------------------------------------------------
# Top 50 Executive Question Bank Definitions
# --------------------------------------------------------------------------------------

TOP_50_QUESTIONS: list[dict[str, Any]] = [
    # A. CEO / Enterprise — “What is happening in my business?” (Q1-10)
    {
        "id": 1,
        "category_code": "A",
        "category_title": "CEO / Enterprise",
        "theme": "What is happening in my business?",
        "subdomain": "Executive Pulse",
        "question": "How is the business performing today, and what are the 5 things I need to know?",
        "expected_sources": ("db",),
    },
    {
        "id": 2,
        "category_code": "A",
        "category_title": "CEO / Enterprise",
        "theme": "What is happening in my business?",
        "subdomain": "Material Changes",
        "question": "What has changed materially in the business this month, and why?",
        "expected_sources": ("db",),
    },
    {
        "id": 3,
        "category_code": "A",
        "category_title": "CEO / Enterprise",
        "theme": "What is happening in my business?",
        "subdomain": "Plan vs Actual",
        "question": "Are we on track against our annual business plan?",
        "expected_sources": ("db",),
    },
    {
        "id": 4,
        "category_code": "A",
        "category_title": "CEO / Enterprise",
        "theme": "What is happening in my business?",
        "subdomain": "Off-Target KPIs",
        "question": "Which business KPIs are currently off-target?",
        "expected_sources": ("db",),
    },
    {
        "id": 5,
        "category_code": "A",
        "category_title": "CEO / Enterprise",
        "theme": "What is happening in my business?",
        "subdomain": "Quarterly Target Risks",
        "question": "What are the biggest risks to achieving this quarter's targets?",
        "expected_sources": ("db", "macro"),
    },
    {
        "id": 6,
        "category_code": "A",
        "category_title": "CEO / Enterprise",
        "theme": "What is happening in my business?",
        "subdomain": "Growth Drivers",
        "question": "Which products, geographies or channels are driving growth?",
        "expected_sources": ("db",),
    },
    {
        "id": 7,
        "category_code": "A",
        "category_title": "CEO / Enterprise",
        "theme": "What is happening in my business?",
        "subdomain": "Underperformance Drivers",
        "question": "Where are we underperforming, and what is causing it?",
        "expected_sources": ("db",),
    },
    {
        "id": 8,
        "category_code": "A",
        "category_title": "CEO / Enterprise",
        "theme": "What is happening in my business?",
        "subdomain": "Emerging Issues",
        "question": "What are the biggest emerging issues that management should be concerned about?",
        "expected_sources": ("db", "regulatory", "macro"),
    },
    {
        "id": 9,
        "category_code": "A",
        "category_title": "CEO / Enterprise",
        "theme": "What is happening in my business?",
        "subdomain": "Actionable Decisions",
        "question": "What decisions require my attention today?",
        "expected_sources": ("db",),
    },
    {
        "id": 10,
        "category_code": "A",
        "category_title": "CEO / Enterprise",
        "theme": "What is happening in my business?",
        "subdomain": "Proactive Discovery",
        "question": "What am I not asking you that I should be asking?",
        "expected_sources": ("db",),
    },

    # B. Sales & Distribution — “Where is growth coming from?” (Q11-18)
    {
        "id": 11,
        "category_code": "B",
        "category_title": "Sales & Distribution",
        "theme": "Where is growth coming from?",
        "subdomain": "Disbursement Variance",
        "question": "Why are disbursements above or below target?",
        "expected_sources": ("db",),
    },
    {
        "id": 12,
        "category_code": "B",
        "category_title": "Sales & Distribution",
        "theme": "Where is growth coming from?",
        "subdomain": "Branch Variance",
        "question": "Which branches are performing above and below expectations?",
        "expected_sources": ("db",),
    },
    {
        "id": 13,
        "category_code": "B",
        "category_title": "Sales & Distribution",
        "theme": "Where is growth coming from?",
        "subdomain": "High-Growth Products & Channels",
        "question": "Which products and channels are generating the highest growth?",
        "expected_sources": ("db",),
    },
    {
        "id": 14,
        "category_code": "B",
        "category_title": "Sales & Distribution",
        "theme": "Where is growth coming from?",
        "subdomain": "Underperforming Sales Units",
        "question": "Which sales teams or locations are consistently underperforming?",
        "expected_sources": ("db",),
    },
    {
        "id": 15,
        "category_code": "B",
        "category_title": "Sales & Distribution",
        "theme": "Where is growth coming from?",
        "subdomain": "Funnel Drop-off Points",
        "question": "Where are we losing customers during the acquisition process?",
        "expected_sources": ("db",),
    },
    {
        "id": 16,
        "category_code": "B",
        "category_title": "Sales & Distribution",
        "theme": "Where is growth coming from?",
        "subdomain": "Funnel Conversion Rates",
        "question": "What is the conversion rate at each stage of the sales funnel?",
        "expected_sources": ("db",),
    },
    {
        "id": 17,
        "category_code": "B",
        "category_title": "Sales & Distribution",
        "theme": "Where is growth coming from?",
        "subdomain": "High-Potential Customer Segments",
        "question": "Which customer segments have the highest potential for growth?",
        "expected_sources": ("db", "macro", "competitive"),
    },
    {
        "id": 18,
        "category_code": "B",
        "category_title": "Sales & Distribution",
        "theme": "Where is growth coming from?",
        "subdomain": "Growth & Credit Quality Frontier",
        "question": "Which branches or channels have the best combination of growth and credit quality?",
        "expected_sources": ("db",),
    },

    # C. Credit & Risk — “Where is my risk?” (Q19-28)
    {
        "id": 19,
        "category_code": "C",
        "category_title": "Credit & Risk",
        "theme": "Where is my risk?",
        "subdomain": "Credit Portfolio Health",
        "question": "How healthy is our credit portfolio right now?",
        "expected_sources": ("db",),
    },
    {
        "id": 20,
        "category_code": "C",
        "category_title": "Credit & Risk",
        "theme": "Where is my risk?",
        "subdomain": "Portfolio Risk Dynamics",
        "question": "Why is portfolio risk increasing or decreasing?",
        "expected_sources": ("db",),
    },
    {
        "id": 21,
        "category_code": "C",
        "category_title": "Credit & Risk",
        "theme": "Where is my risk?",
        "subdomain": "Risk Concentrations",
        "question": "Which products, regions, branches or customer segments have the highest risk?",
        "expected_sources": ("db",),
    },
    {
        "id": 22,
        "category_code": "C",
        "category_title": "Credit & Risk",
        "theme": "Where is my risk?",
        "subdomain": "Delinquency Prediction",
        "question": "Which loans are most likely to become delinquent in the next 30/60/90 days?",
        "expected_sources": ("db",),
    },
    {
        "id": 23,
        "category_code": "C",
        "category_title": "Credit & Risk",
        "theme": "Where is my risk?",
        "subdomain": "Early Warning Indicators",
        "question": "Which borrowers show early warning signs of default?",
        "expected_sources": ("db",),
    },
    {
        "id": 24,
        "category_code": "C",
        "category_title": "Credit & Risk",
        "theme": "Where is my risk?",
        "subdomain": "Vintage Performance",
        "question": "How is our vintage performance changing?",
        "expected_sources": ("db",),
    },
    {
        "id": 25,
        "category_code": "C",
        "category_title": "Credit & Risk",
        "theme": "Where is my risk?",
        "subdomain": "Underwriting Approval Shifts",
        "question": "Where are approval rates changing significantly, and why?",
        "expected_sources": ("db",),
    },
    {
        "id": 26,
        "category_code": "C",
        "category_title": "Credit & Risk",
        "theme": "Where is my risk?",
        "subdomain": "Origination Anomalies",
        "question": "Are there unusual patterns in applications, approvals or disbursements that indicate potential risk?",
        "expected_sources": ("db",),
    },
    {
        "id": 27,
        "category_code": "C",
        "category_title": "Credit & Risk",
        "theme": "Where is my risk?",
        "subdomain": "Portfolio Concentration Risk",
        "question": "What is our concentration risk across customers, industries, geographies or products?",
        "expected_sources": ("db",),
    },
    {
        "id": 28,
        "category_code": "C",
        "category_title": "Credit & Risk",
        "theme": "Where is my risk?",
        "subdomain": "Delinquency Trajectory Forecast",
        "question": "What will happen to portfolio quality if current delinquency trends continue?",
        "expected_sources": ("db",),
    },

    # D. Collections & Recovery — “Where should we focus?” (Q29-35)
    {
        "id": 29,
        "category_code": "D",
        "category_title": "Collections & Recovery",
        "theme": "Where should we focus?",
        "subdomain": "Recovery Priority Worklist",
        "question": "Which accounts should Collections focus on today to maximise recovery?",
        "expected_sources": ("db",),
    },
    {
        "id": 30,
        "category_code": "D",
        "category_title": "Collections & Recovery",
        "theme": "Where should we focus?",
        "subdomain": "Payment Propensity",
        "question": "Which overdue customers have the highest probability of payment if contacted now?",
        "expected_sources": ("db",),
    },
    {
        "id": 31,
        "category_code": "D",
        "category_title": "Collections & Recovery",
        "theme": "Where should we focus?",
        "subdomain": "Collection Deterioration Drivers",
        "question": "What is driving the deterioration in collections performance?",
        "expected_sources": ("db",),
    },
    {
        "id": 32,
        "category_code": "D",
        "category_title": "Collections & Recovery",
        "theme": "Where should we focus?",
        "subdomain": "Agency & Team Efficiency",
        "question": "Which collection agencies, branches or teams are performing best?",
        "expected_sources": ("db",),
    },
    {
        "id": 33,
        "category_code": "D",
        "category_title": "Collections & Recovery",
        "theme": "Where should we focus?",
        "subdomain": "Bucket Migration Rates",
        "question": "Which delinquency buckets are deteriorating fastest?",
        "expected_sources": ("db",),
    },
    {
        "id": 34,
        "category_code": "D",
        "category_title": "Collections & Recovery",
        "theme": "Where should we focus?",
        "subdomain": "Segmented Collection Treatment",
        "question": "What collection strategy should we use for different customer segments?",
        "expected_sources": ("db", "knowledge"),
    },
    {
        "id": 35,
        "category_code": "D",
        "category_title": "Collections & Recovery",
        "theme": "Where should we focus?",
        "subdomain": "Legal & Recovery Escalation",
        "question": "Which accounts should be escalated for legal or recovery action?",
        "expected_sources": ("db", "regulatory"),
    },

    # E. Finance — “Where are we making money?” (Q36-41)
    {
        "id": 36,
        "category_code": "E",
        "category_title": "Finance",
        "theme": "Where are we making money?",
        "subdomain": "P&L Breakdown",
        "question": "Where are we making and losing money across products, branches, channels and customers?",
        "expected_sources": ("db",),
    },
    {
        "id": 37,
        "category_code": "E",
        "category_title": "Finance",
        "theme": "Where are we making money?",
        "subdomain": "Budget Variance Analysis",
        "question": "Why is profitability different from budget?",
        "expected_sources": ("db",),
    },
    {
        "id": 38,
        "category_code": "E",
        "category_title": "Finance",
        "theme": "Where are we making money?",
        "subdomain": "Cost Overrun Drivers",
        "question": "What are the biggest cost overruns and what is causing them?",
        "expected_sources": ("db",),
    },
    {
        "id": 39,
        "category_code": "E",
        "category_title": "Finance",
        "theme": "Where are we making money?",
        "subdomain": "Contribution Margin Ranking",
        "question": "Which products or customer segments have the highest contribution margin?",
        "expected_sources": ("db",),
    },
    {
        "id": 40,
        "category_code": "E",
        "category_title": "Finance",
        "theme": "Where are we making money?",
        "subdomain": "CAC Evolution",
        "question": "How is our cost of acquisition changing?",
        "expected_sources": ("db",),
    },
    {
        "id": 41,
        "category_code": "E",
        "category_title": "Finance",
        "theme": "Where are we making money?",
        "subdomain": "Financial Leakages & Anomalies",
        "question": "What are the major financial leakages or anomalies I should investigate?",
        "expected_sources": ("db",),
    },

    # F. Operations / Technology — “What is slowing the business?” (Q42-45)
    {
        "id": 42,
        "category_code": "F",
        "category_title": "Operations / Technology",
        "theme": "What is slowing the business?",
        "subdomain": "Process Bottlenecks",
        "question": "Where are our biggest operational bottlenecks?",
        "expected_sources": ("db",),
    },
    {
        "id": 43,
        "category_code": "F",
        "category_title": "Operations / Technology",
        "theme": "What is slowing the business?",
        "subdomain": "Exceptions & Turnaround Time",
        "question": "Which processes have the highest rejection, rework, exception or turnaround time?",
        "expected_sources": ("db",),
    },
    {
        "id": 44,
        "category_code": "F",
        "category_title": "Operations / Technology",
        "theme": "What is slowing the business?",
        "subdomain": "Operational CX & Revenue Friction",
        "question": "What operational issues are currently impacting customer experience or revenue?",
        "expected_sources": ("db",),
    },
    {
        "id": 45,
        "category_code": "F",
        "category_title": "Operations / Technology",
        "theme": "What is slowing the business?",
        "subdomain": "Tech & Data Discrepancies",
        "question": "Which technology or data issues are currently impacting business performance?",
        "expected_sources": ("db",),
    },

    # G. Compliance / Legal / Audit / HR / Strategy (Q46-50)
    {
        "id": 46,
        "category_code": "G",
        "category_title": "Compliance / Legal / Audit / HR / Strategy",
        "theme": "Governance & Strategic Execution",
        "subdomain": "Regulatory Exceptions",
        "question": "Are there any significant compliance or regulatory exceptions that require attention?",
        "expected_sources": ("regulatory", "db"),
    },
    {
        "id": 47,
        "category_code": "G",
        "category_title": "Compliance / Legal / Audit / HR / Strategy",
        "theme": "Governance & Strategic Execution",
        "subdomain": "Legal & Contracts Review",
        "question": "Which legal matters, contracts or cases require management attention?",
        "expected_sources": ("regulatory", "db"),
    },
    {
        "id": 48,
        "category_code": "G",
        "category_title": "Compliance / Legal / Audit / HR / Strategy",
        "theme": "Governance & Strategic Execution",
        "subdomain": "Audit & Internal Controls",
        "question": "What control failures or recurring audit observations should management be concerned about?",
        "expected_sources": ("regulatory", "db"),
    },
    {
        "id": 49,
        "category_code": "G",
        "category_title": "Compliance / Legal / Audit / HR / Strategy",
        "theme": "Governance & Strategic Execution",
        "subdomain": "Strategic Initiative Delivery",
        "question": "Are we achieving our strategic initiatives, and which ones are off-track?",
        "expected_sources": ("db", "macro", "competitive"),
    },
    {
        "id": 50,
        "category_code": "G",
        "category_title": "Compliance / Legal / Audit / HR / Strategy",
        "theme": "Governance & Strategic Execution",
        "subdomain": "Capability & Productivity Gaps",
        "question": "Where are we facing people, productivity or capability gaps that could affect business performance?",
        "expected_sources": ("db",),
    },
]


@dataclass(frozen=True, slots=True)
class BenchmarkQuestion:
    id: int
    category_code: str
    category_title: str
    theme: str
    subdomain: str
    question: str
    expected_sources: tuple[str, ...]

    @property
    def display_domain(self) -> str:
        return f"{self.category_code}. {self.category_title}"


@dataclass(slots=True)
class BenchmarkResult:
    item: BenchmarkQuestion
    status: str
    latency_s: float = 0.0
    actual_sources: list[str] = field(default_factory=list)
    card_types: list[str] = field(default_factory=list)
    answer: str = ""
    sql: str = ""
    citations: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def route_matches(self) -> bool:
        return set(self.item.expected_sources).issubset(self.actual_sources)


def load_env_file(path: Path | None) -> dict[str, str]:
    """Load simple KEY=VALUE configuration without external dependencies."""
    candidates = [
        path,
        Path(".env.prod"),
        Path(__file__).resolve().parents[1] / ".env.prod",
        Path(".env"),
        Path(__file__).resolve().parents[1] / ".env",
    ]
    target = next((c for c in candidates if c and c.is_file()), None)
    values: dict[str, str] = {}
    if target is None:
        return values
    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def build_questions() -> list[BenchmarkQuestion]:
    """Return the validated Top 50 questions corpus."""
    if len(TOP_50_QUESTIONS) != 50:
        raise ValueError(f"Expected exactly 50 benchmark questions; found {len(TOP_50_QUESTIONS)}")
    
    questions: list[BenchmarkQuestion] = []
    seen_ids: set[int] = set()
    seen_questions: set[str] = set()

    for item in TOP_50_QUESTIONS:
        qid = item["id"]
        qtext = item["question"].strip()
        if qid in seen_ids:
            raise ValueError(f"Duplicate question ID: {qid}")
        if qtext.casefold() in seen_questions:
            raise ValueError(f"Duplicate question string: {qtext}")
        seen_ids.add(qid)
        seen_questions.add(qtext.casefold())

        questions.append(
            BenchmarkQuestion(
                id=qid,
                category_code=item["category_code"],
                category_title=item["category_title"],
                theme=item["theme"],
                subdomain=item["subdomain"],
                question=qtext,
                expected_sources=tuple(item["expected_sources"]),
            )
        )
    return questions


def request_payload(question: str) -> dict[str, str]:
    """Unpinned request payload: no manual pins, routing hints, or expected SQL."""
    return {"question": question}


def _decode_event(data_lines: list[str]) -> dict[str, Any]:
    raw = "\n".join(data_lines)
    try:
        value = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {"raw": raw}
    return value if isinstance(value, dict) else {"value": value}


def _result_from_events(
    item: BenchmarkQuestion,
    events: list[tuple[str, dict[str, Any]]],
    latency_s: float,
    transport_error: str,
) -> BenchmarkResult:
    sources: list[str] = []
    cards: list[str] = []
    answers: list[str] = []
    citations: list[str] = []
    sql = ""
    status = "Error"
    error = transport_error

    for event_name, data in events:
        if event_name == "route":
            for source in data.get("sources", []) or []:
                if source and source not in sources:
                    sources.append(str(source))
        elif event_name == "source_card":
            source = str(data.get("source", ""))
            card_type = str(data.get("card_type", ""))
            if source and source not in sources:
                sources.append(source)
            if card_type:
                cards.append(card_type)
            text = data.get("summary") or data.get("message") or data.get("headline")
            if text:
                answers.append(str(text))
            lineage = data.get("lineage")
            if isinstance(lineage, dict):
                sql = str(lineage.get("display_sql") or lineage.get("sql") or sql)
            if card_type == "clarify":
                status = "Clarification"
            elif card_type == "refusal":
                status = "Refused"
            elif card_type == "error" and status not in {"Answered", "Partial"}:
                error = str(data.get("message") or "Source error")
            elif card_type:
                status = "Answered"
            for source_ref in data.get("sources", []) or []:
                if isinstance(source_ref, dict):
                    label = source_ref.get("document") or source_ref.get("url")
                    if label:
                        citations.append(str(label))
        elif event_name in {"answer", "synthesis"}:
            text = data.get("text")
            if text:
                answers.append(str(text))
            answer_status = str(data.get("status", "answered"))
            status = {
                "answered": "Answered",
                "partial": "Partial",
                "clarify": "Clarification",
                "refused": "Refused",
            }.get(answer_status, status)
            for source_ref in data.get("citations", []) or []:
                if isinstance(source_ref, dict):
                    label = source_ref.get("document") or source_ref.get("url")
                    if label:
                        citations.append(str(label))
        elif event_name == "refusal":
            status = "Refused"
            answers.append(str(data.get("message") or "Request refused"))
        elif event_name == "error" and status not in {"Answered", "Partial"}:
            error = str(data.get("message") or "Workbench error")

    answer = "\n\n".join(dict.fromkeys(part.strip() for part in answers if part.strip()))
    if error and status == "Answered":
        status = "Partial"
    if status == "Error" and not error:
        error = "No usable answer event was returned"
    return BenchmarkResult(
        item=item,
        status=status,
        latency_s=latency_s,
        actual_sources=sources,
        card_types=cards,
        answer=answer,
        sql=sql,
        citations=list(dict.fromkeys(citations)),
        error=error,
    )


class WorkbenchClient:
    def __init__(self, base_url: str, timeout_s: int, token: str, retries: int = 3, retry_delay_s: float = 2.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.token = token
        self.retries = retries
        self.retry_delay_s = retry_delay_s

    def execute(self, item: BenchmarkQuestion) -> BenchmarkResult:
        body = request_payload(item.question)
        request = urllib.request.Request(
            f"{self.base_url}/api/workbench/ask",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "Moneypal-Executive-50-Benchmark/1.0",
            },
        )
        started = time.monotonic()
        events: list[tuple[str, dict[str, Any]]] = []
        error = ""
        for attempt in range(1, self.retries + 1):
            started = time.monotonic()
            events = []
            error = ""
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                    event_name = ""
                    data_lines: list[str] = []
                    for raw_line in response:
                        line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                        if not line:
                            if event_name:
                                events.append((event_name, _decode_event(data_lines)))
                            event_name, data_lines = "", []
                        elif line.startswith("event:"):
                            event_name = line.partition(":")[2].strip()
                        elif line.startswith("data:"):
                            data_lines.append(line.partition(":")[2].lstrip())
                    if event_name:
                        events.append((event_name, _decode_event(data_lines)))
                return _result_from_events(item, events, time.monotonic() - started, error)
            except urllib.error.HTTPError as exc:
                error = f"HTTP {exc.code}: {exc.reason}"
            except urllib.error.URLError as exc:
                error = f"Connection error: {exc.reason}"
            except TimeoutError:
                error = f"Request timed out after {self.timeout_s}s"
            except Exception as exc:  # noqa: BLE001 - benchmark must record and continue
                error = f"Unexpected error: {exc}"

            if attempt < self.retries:
                time.sleep(self.retry_delay_s * attempt)

        return _result_from_events(item, events, time.monotonic() - started, error)


def _md(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|")


def render_report(
    selected: list[BenchmarkQuestion],
    results: list[BenchmarkResult],
    *,
    base_url: str,
    elapsed_s: float,
    questions_only: bool,
) -> str:
    by_id = {result.item.id: result for result in results}
    status_counts = Counter(result.status for result in results)
    route_matches = sum(result.route_matches for result in results)
    avg_latency = sum(result.latency_s for result in results) / len(results) if results else 0.0

    lines = [
        "# Moneypal Genesis — Top 50 Executive Questions Benchmark",
        "",
        f"**Generated:** {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"**Endpoint:** `{base_url}`",
        f"**Mode:** {'Question corpus only (not executed)' if questions_only else 'Execution benchmark'}",
        f"**Selected questions:** {len(selected)} / 50",
        f"**Completed requests:** {len(results)}",
        f"**Elapsed:** {elapsed_s:.2f}s",
        "",
        "## Payload isolation",
        "",
        "Every request body contains exactly one key:",
        "",
        "```json",
        '{"question": "<plain user question>"}',
        "```",
        "",
        "No source pin, expected route, category, evaluation intent, conversation ID, history, "
        "answer hint, or expected SQL is sent by this benchmark client.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Total Questions | {len(selected)} |",
        f"| Answered | {status_counts['Answered']} |",
        f"| Partial | {status_counts['Partial']} |",
        f"| Clarification | {status_counts['Clarification']} |",
        f"| Refused | {status_counts['Refused']} |",
        f"| Errors | {status_counts['Error']} |",
        f"| Expected route observed | {route_matches} / {len(results)} |",
        f"| Average latency | {avg_latency:.2f}s |",
        "",
        "## Category breakdown",
        "",
        "| Code | Category / Business Domain | Questions | Completed | Answered | Route match |",
        "|---|---|---:|---:|---:|---:|",
    ]

    category_keys: list[tuple[str, str]] = [
        ("A", "CEO / Enterprise — “What is happening in my business?”"),
        ("B", "Sales & Distribution — “Where is growth coming from?”"),
        ("C", "Credit & Risk — “Where is my risk?”"),
        ("D", "Collections & Recovery — “Where should we focus?”"),
        ("E", "Finance — “Where are we making money?”"),
        ("F", "Operations / Technology — “What is slowing the business?”"),
        ("G", "Compliance / Legal / Audit / HR / Strategy"),
    ]

    for code, label in category_keys:
        domain_items = [item for item in selected if item.category_code == code]
        domain_results = [result for result in results if result.item.category_code == code]
        answered_cnt = sum(r.status == "Answered" for r in domain_results)
        route_cnt = sum(r.route_matches for r in domain_results)
        lines.append(
            f"| **{code}** | {label} | {len(domain_items)} | {len(domain_results)} | {answered_cnt} | {route_cnt} |"
        )

    lines += ["", "## Question results", ""]
    for item in selected:
        result = by_id.get(item.id)
        lines += [
            f"### Q{item.id:02d} — {_md(item.question)}",
            "",
            f"- Category: **{item.display_domain}**",
            f"- Theme / Subdomain: **{item.theme} ({item.subdomain})**",
            f"- Expected source(s): `{', '.join(item.expected_sources)}`",
        ]
        if result is None:
            lines.append("- Status: **Not run**")
        else:
            lines += [
                f"- Status: **{result.status}**",
                f"- Actual sources: `{', '.join(result.actual_sources) or 'none'}`",
                f"- Route match: **{'Yes' if result.route_matches else 'No'}**",
                f"- Latency: `{result.latency_s:.2f}s`",
                f"- Cards: `{', '.join(result.card_types) or 'none'}`",
                "",
                "#### Response",
                "",
                "````text",
                result.answer or result.error or "No response text",
                "````",
            ]
            if result.sql:
                lines += ["", "#### SQL", "", "````sql", result.sql, "````"]
            if result.citations:
                lines += ["", "#### Citations", ""]
                lines.extend(f"- {_md(citation)}" for citation in result.citations)
        lines += ["", "---", ""]

    lines += [
        "## Methodology",
        "",
        "- The 50 questions cover the top strategic questions an AI executive assistant must answer for enterprise lending leadership.",
        "- CEO / Enterprise questions evaluate whole-bank performance, variance, critical milestones, and emerging enterprise risks.",
        "- Sales & Distribution questions evaluate origination trajectory, channel/branch velocity, and sales funnel conversions.",
        "- Credit & Risk questions assess portfolio health, delinquency forecasting, vintage deterioration, and early warning triggers.",
        "- Collections & Recovery questions evaluate high-propensity recovery queues, bucket migration, and legal escalations.",
        "- Finance questions assess product/branch unit economics, contribution margins, cost variance, and revenue leakages.",
        "- Operations / Technology questions diagnose turnaround bottlenecks, process rework, and platform reliability.",
        "- Compliance / Strategy questions audit regulatory compliance exceptions, legal matters, and strategic execution.",
        "- Expected sources are evaluation benchmarks and are never passed in the HTTP request payload.",
        "",
    ]
    return "\n".join(lines)


def _select_questions(
    all_questions: list[BenchmarkQuestion], args: argparse.Namespace, parser: argparse.ArgumentParser,
) -> list[BenchmarkQuestion]:
    if args.ids and args.sample is not None:
        parser.error("--ids and --sample cannot be used together")
    if args.category:
        targets = [c.strip().upper() for c in args.category.split(",") if c.strip()]
        matched: list[BenchmarkQuestion] = []
        for q in all_questions:
            if q.category_code.upper() in targets:
                matched.append(q)
            elif any(t in q.category_title.upper() for t in targets if len(t) > 1):
                matched.append(q)
        all_questions = matched
        if not all_questions:
            parser.error(f"No questions matched category filter: {args.category}")
    if args.ids:
        try:
            ids = list(dict.fromkeys(int(value.strip()) for value in args.ids.split(",") if value.strip()))
        except ValueError:
            parser.error("--ids must be a comma-separated list of integers")
        indexed = {item.id: item for item in all_questions}
        missing = [item_id for item_id in ids if item_id not in indexed]
        if missing:
            parser.error(f"unknown question IDs: {', '.join(map(str, missing))}")
        return [indexed[item_id] for item_id in ids]
    if args.sample is not None:
        if not 1 <= args.sample <= len(all_questions):
            parser.error(f"--sample must be between 1 and {len(all_questions)}")
        return sorted(random.Random(args.seed).sample(all_questions, args.sample), key=lambda item: item.id)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be a positive integer")
    return all_questions[:min(args.limit, len(all_questions))]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run 50 Top Executive questions across Genesis intelligence workbench",
    )
    parser.add_argument("--url", default=None, help="Application base URL (e.g., http://100.70.118.31:4321)")
    parser.add_argument("--env-file", default=".env.prod", help="Environment file for defaults")
    parser.add_argument("--output-md", default="benchmark_50_executive_report.md", help="Markdown report path")
    parser.add_argument("--timeout", type=int, default=None, help="Per-question timeout in seconds")
    parser.add_argument("--token", default=None, help="Authentication token")
    parser.add_argument("--limit", type=int, default=50, help="Run the first N questions (default: 50)")
    parser.add_argument("--ids", help="Run specific IDs, such as 1,11,19,29,36,42,46")
    parser.add_argument("--category", help="Filter by category code (A, B, C, D, E, F, G) or name")
    parser.add_argument("--sample", type=int, help="Run a reproducible random sample")
    parser.add_argument("--seed", type=int, default=20260827, help="Seed for --sample")
    parser.add_argument(
        "--questions-only", action="store_true",
        help="Write the 50-question report without calling the application",
    )
    args = parser.parse_args()

    env = load_env_file(Path(args.env_file) if args.env_file else None)
    base_url = args.url or env.get("BENCHMARK_BASE_URL") or "http://100.70.118.31:4321"
    timeout_s = args.timeout or int(env.get("NLQ_REQUEST_BUDGET_S", "120"))
    token = args.token or env.get("BENCHMARK_AUTH_TOKEN") or "mock-token-gicc_admin"
    output = Path(args.output_md)
    all_questions = build_questions()
    selected = _select_questions(all_questions, args, parser)

    print("=" * 70, flush=True)
    print("Moneypal Genesis — Top 50 Executive Questions Benchmark", flush=True)
    print(f"Questions: {len(selected)} / 50 | Endpoint: {base_url} | Output: {output}", flush=True)
    print("Request payload: unpinned {'question': '...'} with SSE response capture", flush=True)
    print("=" * 70, flush=True)

    results: list[BenchmarkResult] = []
    started = time.monotonic()
    if args.questions_only:
        output.write_text(
            render_report(
                selected, results, base_url=base_url, elapsed_s=0.0, questions_only=True,
            ),
            encoding="utf-8",
        )
        print(f"Question corpus written to {output.resolve()}", flush=True)
        return 0

    client = WorkbenchClient(base_url, timeout_s, token)
    for index, item in enumerate(selected, 1):
        print(
            f"[{index:02d}/{len(selected):02d}] Q{item.id:02d} "
            f"[{item.category_code}: {item.category_title}] {item.question}",
            flush=True,
        )
        result = client.execute(item)
        results.append(result)
        print(
            f"  -> {result.status} | sources={','.join(result.actual_sources) or 'none'} "
            f"| route={'match' if result.route_matches else 'miss'} | {result.latency_s:.2f}s",
            flush=True,
        )
        output.write_text(
            render_report(
                selected, results, base_url=base_url,
                elapsed_s=time.monotonic() - started, questions_only=False,
            ),
            encoding="utf-8",
        )
        time.sleep(0.5)

    failures = sum(result.status == "Error" for result in results)
    route_misses = sum(not result.route_matches for result in results)
    print("=" * 70, flush=True)
    print(
        f"Completed {len(results)} questions with {failures} errors and {route_misses} route misses. "
        f"Report: {output.resolve()}",
        flush=True,
    )
    print("=" * 70, flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
