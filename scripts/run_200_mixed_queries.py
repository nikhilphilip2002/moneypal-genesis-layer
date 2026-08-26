#!/usr/bin/env python3
"""Run a 200-question, unpinned Workbench routing and answer benchmark.

The corpus contains 160 balanced single-source questions across Loan Book, Macro,
Competitive, Regulatory, and General Banking, plus 40 multi-source questions.
The HTTP request body intentionally contains only the user's question. Expected
sources and category labels are evaluator-side metadata and are never sent to the
application.

Credentials, timeout, and endpoint defaults follow the existing production
benchmark runner and may be overridden from the command line.  The report is
checkpointed to ``benchmark.md`` after every completed request.
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


DOMAIN_SOURCES = {
    "Loan Book": ("db",),
    "Macro": ("macro",),
    "Competitive": ("competitive",),
    "Regulatory": ("regulatory",),
    "General Banking": ("knowledge",),
}


# Topics were selected from the Gold semantic catalog (PostgreSQL), macro source
# inventory, institution registry, and regulation registry.  These labels never
# leave this process; only each question string is posted to the Workbench.
QUESTION_BANK: dict[str, list[tuple[str, str]]] = {
    "Loan Book": [
        ("Portfolio", "What is the total principal outstanding across our loan book?"),
        ("Portfolio", "Show our principal outstanding by product."),
        ("Portfolio", "Which branches have the highest principal outstanding?"),
        ("Portfolio", "Break down our current outstanding by asset classification."),
        ("Portfolio", "How many open loan accounts are in our portfolio?"),
        ("Portfolio", "What is our average principal outstanding per active account?"),
        ("Portfolio", "Show open versus closed loan accounts by product."),
        ("Portfolio", "What share of our principal outstanding is in Gold Loans?"),
        ("Origination", "What is our total sanctioned amount this financial year?"),
        ("Origination", "How many loans did we sanction in each month of the last year?"),
        ("Origination", "Show our average sanctioned loan amount by product."),
        ("Origination", "Which schemes have the highest sanctioned amount?"),
        ("Origination", "Show loans sanctioned by agent for all time."),
        ("Origination", "Which five branches sanctioned the most loans?"),
        ("Origination", "Compare our sanctioned amount with disbursed amount by branch."),
        ("Origination", "Show our monthly sanction amount trend for the last 12 months."),
        ("Disbursement", "What is our total disbursed amount this financial year?"),
        ("Disbursement", "Show monthly disbursement by product for the last year."),
        ("Disbursement", "Which branches have the highest disbursement amount?"),
        ("Disbursement", "What is our sanction-to-disbursement conversion ratio?"),
        ("Collections", "What is our overall collection efficiency?"),
        ("Collections", "Show collection efficiency by branch."),
        ("Collections", "Show total due and total paid by month."),
        ("Collections", "Which products have the largest collection shortfall?"),
        ("Collections", "What is the total amount collected in the current financial year?"),
        ("Collections", "Show our repayment trend for the last 12 months."),
        ("Risk", "What is our current PAR 30 ratio?"),
        ("Risk", "What is our current NPA ratio?"),
        ("Risk", "Show principal outstanding by DPD bucket."),
        ("Risk", "How many accounts are classified as SMA-2?"),
        ("Risk", "Which branches have the highest overdue amount?"),
        ("Risk", "Show Standard, SMA and NPA account counts by product."),
        ("Directory", "How many agents are in the governed agent directory?"),
        ("Directory", "Show the information for agent AGNT45."),
        ("Directory", "List the branches available in the loan book."),
        ("Customer", "Show customer ID 128 details."),
        ("Customer", "What is the loan amount and sanction date for customer ID 128?"),
        ("Customer", "Show the repayment history for SHEELAVATHI M K."),
        ("Customer", "What is the disbursement date for customer SHEELAVATHI M K?"),
        ("Worklist", "List the ten loan accounts with the highest overdue amount."),
    ],
    "Macro": [
        ("Growth", "What is the latest supported estimate of India's GDP growth?"),
        ("Growth", "What does the indexed evidence say about Karnataka's GSDP growth?"),
        ("Growth", "Which sectors are driving Karnataka's economic growth?"),
        ("Growth", "How has India's real gross value added changed in the latest supported period?"),
        ("Growth", "What are the main downside risks to India's growth outlook?"),
        ("Growth", "How does Karnataka's economic structure differ from the national economy?"),
        ("Growth", "What does the Economic Survey say about private investment conditions?"),
        ("Growth", "Summarize the latest supported industrial growth trend in India."),
        ("Inflation", "What is the latest inflation trend supported by the macro sources?"),
        ("Inflation", "What factors are driving food inflation in India?"),
        ("Inflation", "How could inflation affect household borrowing demand?"),
        ("Inflation", "What does the evidence say about rural versus urban inflation?"),
        ("Monetary Policy", "What policy stance does the latest indexed RBI material describe?"),
        ("Monetary Policy", "How do repo-rate changes transmit to lending rates?"),
        ("Monetary Policy", "What does the RBI evidence say about liquidity conditions?"),
        ("Monetary Policy", "How could tighter monetary conditions affect MSME credit demand?"),
        ("Credit", "How is bank credit growth trending in the latest supported period?"),
        ("Credit", "What macro factors are influencing retail credit growth?"),
        ("Credit", "What does the indexed evidence say about credit conditions for small firms?"),
        ("Credit", "Are deposit growth and credit growth moving at similar rates?"),
        ("MSME", "What is the latest supported outlook for India's MSME sector?"),
        ("MSME", "What financing gaps do Indian MSMEs face?"),
        ("MSME", "Which MSME segments appear most credit constrained?"),
        ("MSME", "What does the MSME annual report say about enterprise formalization?"),
        ("MSME", "How important are micro enterprises within the Indian MSME base?"),
        ("MSME", "What barriers limit MSME access to formal credit?"),
        ("MSME", "How could digital public infrastructure improve MSME lending?"),
        ("MSME", "What macro indicators should a Karnataka MSME lender monitor?"),
        ("Karnataka", "What are the main economic strengths of Karnataka?"),
        ("Karnataka", "Which Karnataka sectors create opportunities for MSME lending?"),
        ("Karnataka", "What regional risks could weaken credit demand in Karnataka?"),
        ("Karnataka", "How does urbanization influence Karnataka's lending opportunity?"),
        ("External", "How could global growth conditions affect Indian borrowers?"),
        ("External", "What external risks could affect India's inflation outlook?"),
        ("External", "How can oil-price changes affect Indian lending conditions?"),
        ("External", "What does the evidence say about export conditions for Indian MSMEs?"),
        ("Gold", "What macro factors tend to influence gold prices?"),
        ("Gold", "How can gold-price movements affect gold-loan collateral coverage?"),
        ("Outlook", "Summarize the macro outlook relevant to a Karnataka co-operative lender."),
        ("Outlook", "What leading indicators should be watched for a change in credit conditions?"),
    ],
    "Competitive": [
        ("Landscape", "Who are the indexed competitors serving Karnataka MSME borrowers?"),
        ("Landscape", "How do co-operative banks and NBFCs differ in their MSME positioning?"),
        ("Landscape", "Where does the indexed competitor evidence show white space in MSME lending?"),
        ("Landscape", "Which indexed lenders emphasize small-business finance?"),
        ("Landscape", "Compare the geographic positioning of the indexed Karnataka lenders."),
        ("Landscape", "Which competitors appear focused on underserved enterprise segments?"),
        ("Products", "What loan products does Kinara Capital highlight for MSMEs?"),
        ("Products", "What lending products are described for SIDBI?"),
        ("Products", "What business-loan products are documented for KSFC?"),
        ("Products", "What loan facilities does Belagavi DCCB offer?"),
        ("Products", "What loan products are listed by Belgaum Industrial Co-operative Bank?"),
        ("Products", "What products does Bellary Urban Co-operative Bank promote?"),
        ("Products", "What loan facilities are documented for Bhatkal Urban Co-operative Bank?"),
        ("Products", "What lending services are described for Karnataka State Co-operative Apex Bank?"),
        ("Products", "What products are documented for Kaujalgi Urban Co-operative Bank?"),
        ("Products", "What loan offerings are indexed for National Co-operative Bank?"),
        ("Products", "What lending products are described for South Canara DCCB?"),
        ("Pricing", "What interest-rate information is available for Belagavi DCCB loans?"),
        ("Pricing", "What lending-rate evidence is indexed for Bellary Urban Co-operative Bank?"),
        ("Pricing", "Compare available loan-pricing evidence across the indexed co-operative banks."),
        ("Pricing", "Does the indexed evidence provide MSME pricing for Kinara Capital?"),
        ("Pricing", "What pricing gaps remain in the competitor evidence?"),
        ("Distribution", "What branch information is available for Bhatkal Urban Co-operative Bank?"),
        ("Distribution", "What does the evidence say about South Canara DCCB's reach?"),
        ("Distribution", "Compare the documented distribution presence of the indexed lenders."),
        ("Distribution", "Which indexed competitors appear strongest outside Bengaluru?"),
        ("Capabilities", "Which competitor sources mention digital banking capabilities?"),
        ("Capabilities", "What customer-service channels are documented across competitors?"),
        ("Capabilities", "Which indexed banks describe agriculture-linked lending capabilities?"),
        ("Capabilities", "What collateral-backed loan offerings appear across competitors?"),
        ("Benchmark", "How does SIDBI position itself as an MSME finance benchmark?"),
        ("Benchmark", "What differentiates Kinara Capital from co-operative-bank competitors?"),
        ("Benchmark", "Compare KSFC and SIDBI based on the indexed evidence."),
        ("Benchmark", "Compare Belagavi DCCB with South Canara DCCB on documented offerings."),
        ("Benchmark", "Compare Bhatkal Urban Co-operative Bank with National Co-operative Bank."),
        ("Strategy", "What competitive threats are visible for a Karnataka MSME lender?"),
        ("Strategy", "What product gaps could a Karnataka lender investigate based on competitor evidence?"),
        ("Strategy", "Which borrower segments appear most contested by the indexed lenders?"),
        ("Strategy", "What claims in the competitor data need better evidence before strategic use?"),
        ("Strategy", "Summarize the indexed competitive landscape for Karnataka MSME lending."),
    ],
    "Regulatory": [
        ("Digital Lending", "What do the indexed RBI digital-lending directions require?"),
        ("Digital Lending", "What obligations apply when a lender uses a lending service provider?"),
        ("Digital Lending", "What does RBI require for digital-loan disclosures to borrowers?"),
        ("Digital Lending", "What controls apply to digital collection and use of borrower data?"),
        ("Fair Practices", "What does the Fair Practices Code require in loan communication?"),
        ("Fair Practices", "What fair-practice requirements apply during loan recovery?"),
        ("Fair Practices", "What grievance-redressal expectations are stated for lenders?"),
        ("Fair Practices", "How should changes in loan terms be communicated under the Fair Practices Code?"),
        ("KYC AML", "What customer due-diligence requirements are described in the KYC directions?"),
        ("KYC AML", "What does RBI require for periodic KYC updation?"),
        ("KYC AML", "What AML monitoring and suspicious-transaction controls are required?"),
        ("KYC AML", "What KYC recordkeeping obligations are supported by the indexed directions?"),
        ("Prudential", "What asset-classification rules are stated in the prudential norms?"),
        ("Prudential", "What provisioning principles apply to non-performing assets?"),
        ("Prudential", "What capital requirements are described for NBFCs in the indexed material?"),
        ("Prudential", "What exposure and concentration controls are described in the prudential norms?"),
        ("Governance", "What board-oversight responsibilities are set out in the governance directions?"),
        ("Governance", "Which policies require board approval under the indexed governance material?"),
        ("Governance", "What management-accountability expectations are described for NBFCs?"),
        ("Governance", "What control-framework requirements appear in the governance directions?"),
        ("Outsourcing", "What due diligence is required before outsourcing a financial service?"),
        ("Outsourcing", "What ongoing vendor-monitoring controls are required for outsourced services?"),
        ("Outsourcing", "What exit-planning requirements apply to material outsourcing arrangements?"),
        ("Outsourcing", "Which outsourced responsibilities remain with the regulated entity?"),
        ("Information Security", "What information-security governance controls are required for NBFCs?"),
        ("Information Security", "What cyber-incident handling obligations are described in the indexed directions?"),
        ("Information Security", "What controls support digital operational resilience?"),
        ("Information Security", "What board responsibilities apply to cyber and information-security risk?"),
        ("Master Directions", "What areas are covered by the indexed NBFC master directions?"),
        ("Master Directions", "How should an institution determine which RBI master direction applies to it?"),
        ("Master Directions", "What registration requirements are described in the NBFC master directions?"),
        ("Master Directions", "What scale-based regulatory obligations are supported by the indexed material?"),
        ("Circulars", "What recent RBI circulars in the index may affect lending operations?"),
        ("Circulars", "What effective dates are stated in the recent indexed RBI circulars?"),
        ("Notifications", "Which indexed RBI notifications are relevant to NBFC lending?"),
        ("Notifications", "What actions are required by the latest applicable indexed notification?"),
        ("Registry", "What can the indexed RBI NBFC and bank registry confirm?"),
        ("Registry", "How should active regulatory status be checked using the indexed registry?"),
        ("Applicability", "Which indexed regulatory requirements concern customer-facing lending conduct?"),
        ("Applicability", "Summarize the main compliance themes across the indexed RBI material."),
    ],
    "General Banking": [
        ("Definitions", "What is principal outstanding?"),
        ("Definitions", "What is the difference between sanctioned amount and disbursed amount?"),
        ("Definitions", "What is a loan account number?"),
        ("Definitions", "What does loan maturity mean?"),
        ("Definitions", "What is an amortizing loan?"),
        ("Definitions", "What is a bullet-repayment loan?"),
        ("Definitions", "What is a secured loan?"),
        ("Definitions", "What is an unsecured loan?"),
        ("Repayment", "What is an EMI and how is it calculated?"),
        ("Repayment", "What is the difference between principal due and principal paid?"),
        ("Repayment", "What does repayment frequency mean?"),
        ("Repayment", "What is a repayment schedule?"),
        ("Repayment", "What is a collection shortfall?"),
        ("Repayment", "How is collection efficiency calculated?"),
        ("Repayment", "What is prepayment of a loan?"),
        ("Repayment", "What is loan foreclosure?"),
        ("Risk", "What does days past due mean?"),
        ("Risk", "How are DPD buckets used in lending?"),
        ("Risk", "What is PAR 30 and how is it calculated?"),
        ("Risk", "What is the difference between PAR and NPA ratio?"),
        ("Risk", "What do SMA-0, SMA-1 and SMA-2 mean?"),
        ("Risk", "What is a non-performing asset?"),
        ("Risk", "What is credit risk?"),
        ("Risk", "What is concentration risk in a loan portfolio?"),
        ("Pricing", "What is a loan interest rate?"),
        ("Pricing", "What is the difference between fixed and floating interest rates?"),
        ("Pricing", "What is reducing-balance interest?"),
        ("Pricing", "What is flat-rate interest?"),
        ("Pricing", "What is average ticket size in lending?"),
        ("Pricing", "What is yield on a loan portfolio?"),
        ("Operations", "What is loan origination?"),
        ("Operations", "What is loan underwriting?"),
        ("Operations", "What is loan disbursement?"),
        ("Operations", "What is the difference between a loan product and a loan scheme?"),
        ("Operations", "What does a branch code identify?"),
        ("Operations", "What is a sourcing agent in lending?"),
        ("Accounting", "What is a general ledger in banking?"),
        ("Accounting", "What is the difference between debit and credit balances?"),
        ("Accounting", "What is provisioning for loan losses?"),
        ("Accounting", "What is a write-off and how does it differ from loan closure?"),
    ],
}


HYBRID_QUESTIONS: list[tuple[str, str, tuple[str, ...]]] = [
    # Loan Book + Macro (10)
    ("Book + Macro", "Compare our loan-book growth with the latest supported national credit-growth trend.", ("db", "macro")),
    ("Book + Macro", "How does our MSME disbursement trend compare with the macro outlook for Indian MSMEs?", ("db", "macro")),
    ("Book + Macro", "Compare our Gold Loan portfolio trend with the macro factors affecting gold prices.", ("db", "macro")),
    ("Book + Macro", "Assess our collection-efficiency trend alongside the latest supported inflation conditions.", ("db", "macro")),
    ("Book + Macro", "Compare our average sanctioned interest rate with the indexed RBI monetary-policy context.", ("db", "macro")),
    ("Book + Macro", "How does our branch-level disbursement trend align with Karnataka's economic outlook?", ("db", "macro")),
    ("Book + Macro", "Compare our retail-loan growth with the macro evidence on household credit conditions.", ("db", "macro")),
    ("Book + Macro", "Assess our current PAR 30 against the macro risks facing MSME borrowers.", ("db", "macro")),
    ("Book + Macro", "Compare our monthly sanctions with the latest supported industrial-growth trend.", ("db", "macro")),
    ("Book + Macro", "What do our disbursement figures and the macro credit outlook together imply for near-term lending demand?", ("db", "macro")),

    # Loan Book + Competitive (10)
    ("Book + Competitive", "Compare our MSME product mix with the products documented for Karnataka competitors.", ("db", "competitive")),
    ("Book + Competitive", "How does our average MSME ticket size compare with available competitor evidence?", ("db", "competitive")),
    ("Book + Competitive", "Compare our Gold Loan presence with collateral-backed products offered by competitors.", ("db", "competitive")),
    ("Book + Competitive", "Assess our branch concentration against the documented geographic reach of competitors.", ("db", "competitive")),
    ("Book + Competitive", "Compare our sanctioned interest rates with available competitor loan-pricing evidence.", ("db", "competitive")),
    ("Book + Competitive", "Which gaps between our scheme mix and competitor offerings could represent white space?", ("db", "competitive")),
    ("Book + Competitive", "Compare our MSME disbursement trend with Kinara Capital's documented positioning.", ("db", "competitive")),
    ("Book + Competitive", "How does our portfolio focus compare with SIDBI's documented MSME priorities?", ("db", "competitive")),
    ("Book + Competitive", "Compare our lending footprint with Belagavi DCCB and South Canara DCCB.", ("db", "competitive")),
    ("Book + Competitive", "Use our product performance and indexed competitor evidence to identify contested borrower segments.", ("db", "competitive")),

    # Loan Book + Regulatory (10)
    ("Book + Regulatory", "Compare our current asset classifications with the indexed regulatory prudential definitions.", ("db", "regulatory")),
    ("Book + Regulatory", "Assess our NPA and PAR position in the context of regulatory asset-classification requirements.", ("db", "regulatory")),
    ("Book + Regulatory", "Compare our overdue-account profile with the regulatory fair-practice expectations for recovery.", ("db", "regulatory")),
    ("Book + Regulatory", "Relate our agent-sourced loan volumes to regulatory outsourcing oversight requirements.", ("db", "regulatory")),
    ("Book + Regulatory", "Compare our digital-loan portfolio indicators with regulatory digital-lending obligations.", ("db", "regulatory")),
    ("Book + Regulatory", "Assess our concentration by borrower and scheme against regulatory concentration-risk principles.", ("db", "regulatory")),
    ("Book + Regulatory", "Use our repayment performance to explain which regulatory prudential risks deserve attention.", ("db", "regulatory")),
    ("Book + Regulatory", "Compare our branch and agent structure with regulatory governance and control expectations.", ("db", "regulatory")),
    ("Book + Regulatory", "Relate our customer KYC coverage to the indexed regulatory KYC and AML obligations.", ("db", "regulatory")),
    ("Book + Regulatory", "Which regulatory themes are most relevant to the current risk profile of our loan book?", ("db", "regulatory")),

    # External-source combinations (6)
    ("Macro + Competitive", "How do current macro credit conditions affect the positioning of Karnataka MSME competitors?", ("macro", "competitive")),
    ("Macro + Competitive", "Compare the macro outlook for MSMEs with the products emphasized by indexed competitors.", ("macro", "competitive")),
    ("Macro + Competitive", "Which competitor strategies appear best aligned with Karnataka's economic outlook?", ("macro", "competitive")),
    ("Macro + Regulatory", "How could the monetary-policy outlook interact with regulatory prudential requirements for lenders?", ("macro", "regulatory")),
    ("Macro + Regulatory", "Relate the MSME macro outlook to applicable regulatory lending-conduct requirements.", ("macro", "regulatory")),
    ("Competitive + Regulatory", "Compare indexed digital-lending competitor capabilities with regulatory digital-lending requirements.", ("competitive", "regulatory")),

    # Three-source combinations (4)
    ("Book + Macro + Competitive", "Compare our MSME growth with macro credit conditions and indexed competitor positioning.", ("db", "macro", "competitive")),
    ("Book + Macro + Regulatory", "Assess our portfolio-risk trend using macro conditions and regulatory prudential expectations.", ("db", "macro", "regulatory")),
    ("Book + Competitive + Regulatory", "Compare our digital-lending position with competitor capabilities and regulatory requirements.", ("db", "competitive", "regulatory")),
    ("Book + Macro + Competitive", "Use our product performance, Karnataka's macro outlook, and competitor evidence to identify lending opportunities.", ("db", "macro", "competitive")),
]


@dataclass(frozen=True, slots=True)
class BenchmarkQuestion:
    id: int
    domain: str
    subdomain: str
    question: str
    expected_sources: tuple[str, ...]


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
    """Load simple KEY=VALUE configuration without importing app dependencies."""
    candidates = [
        path,
        Path(".env.prod"),
        Path(__file__).resolve().parents[1] / ".env.prod",
        Path(".env"),
    ]
    target = next((candidate for candidate in candidates if candidate and candidate.is_file()), None)
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
    """Return 32 per single source plus 40 hybrid questions, 200 overall."""
    questions: list[BenchmarkQuestion] = []
    next_id = 1
    for domain, rows in QUESTION_BANK.items():
        if len(rows) != 40:
            raise ValueError(f"{domain} candidate bank must contain 40 questions; found {len(rows)}")
        for subdomain, question in rows[:32]:
            questions.append(BenchmarkQuestion(
                id=next_id,
                domain=domain,
                subdomain=subdomain,
                question=question,
                expected_sources=DOMAIN_SOURCES[domain],
            ))
            next_id += 1
    if len(HYBRID_QUESTIONS) != 40:
        raise ValueError(f"hybrid bank must contain 40 questions; found {len(HYBRID_QUESTIONS)}")
    for subdomain, question, expected_sources in HYBRID_QUESTIONS:
        questions.append(BenchmarkQuestion(
            id=next_id,
            domain="Hybrid",
            subdomain=subdomain,
            question=question,
            expected_sources=expected_sources,
        ))
        next_id += 1
    if len(questions) != 200:
        raise ValueError(f"benchmark must contain 200 questions; found {len(questions)}")
    normalized = [item.question.casefold().strip() for item in questions]
    if len(normalized) != len(set(normalized)):
        raise ValueError("benchmark questions must be unique")
    return questions


def request_payload(question: str) -> dict[str, str]:
    """The sole application payload: no pins, history, labels, or expected answers."""
    return {"question": question}


class WorkbenchClient:
    def __init__(self, base_url: str, timeout_s: int, token: str):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.token = token

    def execute(self, item: BenchmarkQuestion) -> BenchmarkResult:
        body = request_payload(item.question)
        request = urllib.request.Request(
            f"{self.base_url}/api/workbench/ask",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "Moneypal-Mixed-Benchmark/1.0",
            },
        )
        started = time.monotonic()
        events: list[tuple[str, dict[str, Any]]] = []
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
        except urllib.error.HTTPError as exc:
            error = f"HTTP {exc.code}: {exc.reason}"
        except urllib.error.URLError as exc:
            error = f"Connection error: {exc.reason}"
        except TimeoutError:
            error = f"Request timed out after {self.timeout_s}s"
        except Exception as exc:  # noqa: BLE001 - benchmark must record and continue
            error = f"Unexpected error: {exc}"
        return _result_from_events(item, events, time.monotonic() - started, error)


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
                "answered": "Answered", "partial": "Partial", "clarify": "Clarification",
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
        "# Moneypal Genesis — 200 Mixed Intelligence Questions Benchmark",
        "",
        f"**Generated:** {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"**Endpoint:** `{base_url}`",
        f"**Mode:** {'Question corpus only (not executed)' if questions_only else 'Execution benchmark'}",
        f"**Selected questions:** {len(selected)} / 200",
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
        f"| Answered | {status_counts['Answered']} |",
        f"| Partial | {status_counts['Partial']} |",
        f"| Clarification | {status_counts['Clarification']} |",
        f"| Refused | {status_counts['Refused']} |",
        f"| Errors | {status_counts['Error']} |",
        f"| Expected route observed | {route_matches} / {len(results)} |",
        f"| Average latency | {avg_latency:.2f}s |",
        "",
        "## Domain coverage",
        "",
        "| Domain | Selected | Completed | Answered | Route match |",
        "|---|---:|---:|---:|---:|",
    ]
    for domain in [*QUESTION_BANK, "Hybrid"]:
        domain_items = [item for item in selected if item.domain == domain]
        domain_results = [result for result in results if result.item.domain == domain]
        lines.append(
            f"| {domain} | {len(domain_items)} | {len(domain_results)} | "
            f"{sum(r.status == 'Answered' for r in domain_results)} | "
            f"{sum(r.route_matches for r in domain_results)} |"
        )

    lines += ["", "## Question results", ""]
    for item in selected:
        result = by_id.get(item.id)
        lines += [
            f"### Q{item.id:03d} — {_md(item.question)}",
            "",
            f"- Domain: **{item.domain} / {item.subdomain}**",
            f"- Expected source: `{', '.join(item.expected_sources)}`",
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
        "- Loan Book coverage is based on the governed Gold semantic YAML and PostgreSQL-backed views.",
        "- Macro coverage reflects the configured macro Qdrant collection and local source inventory.",
        "- Competitive coverage reflects all 11 registered institution Qdrant collections.",
        "- Regulatory coverage reflects all 12 registered regulatory Qdrant collections.",
        "- General Banking questions test natural routing to the catalog-backed concept explainer.",
        "- Hybrid questions test natural multi-source routing without a source pin or routing hint.",
        "- Expected sources are used only to score routing and are never sent to the application.",
        "",
    ]
    return "\n".join(lines)


def _select_questions(
    all_questions: list[BenchmarkQuestion], args: argparse.Namespace, parser: argparse.ArgumentParser,
) -> list[BenchmarkQuestion]:
    if args.ids and args.sample is not None:
        parser.error("--ids and --sample cannot be used together")
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
    if not 1 <= args.limit <= len(all_questions):
        parser.error(f"--limit must be between 1 and {len(all_questions)}")
    return all_questions[:args.limit]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run 200 unpinned questions across all Genesis intelligence sources",
    )
    parser.add_argument("--url", default=None, help="Application base URL")
    parser.add_argument("--env-file", default=".env.prod", help="Environment file for defaults")
    parser.add_argument("--output-md", default="benchmark.md", help="Markdown report path")
    parser.add_argument("--timeout", type=int, default=None, help="Per-question timeout in seconds")
    parser.add_argument("--token", default=None, help="Authentication token")
    parser.add_argument("--limit", type=int, default=200, help="Run the first N questions")
    parser.add_argument("--ids", help="Run specific IDs, such as 1,41,81,121,161")
    parser.add_argument("--sample", type=int, help="Run a reproducible random sample")
    parser.add_argument("--seed", type=int, default=20260826, help="Seed for --sample")
    parser.add_argument(
        "--questions-only", action="store_true",
        help="Write the 200-question report without calling the application",
    )
    args = parser.parse_args()

    env = load_env_file(Path(args.env_file) if args.env_file else None)
    base_url = args.url or env.get("BENCHMARK_BASE_URL") or "http://100.70.118.31:4321"
    timeout_s = args.timeout or int(env.get("NLQ_REQUEST_BUDGET_S", "120"))
    token = args.token or env.get("BENCHMARK_AUTH_TOKEN") or "mock-token-gicc_admin"
    output = Path(args.output_md)
    all_questions = build_questions()
    selected = _select_questions(all_questions, args, parser)

    print("Moneypal Genesis mixed intelligence benchmark", flush=True)
    print(f"Questions: {len(selected)} | Endpoint: {base_url} | Output: {output}", flush=True)
    print("Request payload: question only (routing is unpinned)", flush=True)

    results: list[BenchmarkResult] = []
    started = time.monotonic()
    if args.questions_only:
        output.write_text(render_report(
            selected, results, base_url=base_url, elapsed_s=0.0, questions_only=True,
        ), encoding="utf-8")
        print(f"Question corpus written to {output.resolve()}", flush=True)
        return 0

    client = WorkbenchClient(base_url, timeout_s, token)
    for index, item in enumerate(selected, 1):
        print(
            f"[{index:03d}/{len(selected):03d}] Q{item.id:03d} "
            f"[{item.domain}] {item.question}",
            flush=True,
        )
        result = client.execute(item)
        results.append(result)
        print(
            f"  -> {result.status} | sources={','.join(result.actual_sources) or 'none'} "
            f"| route={'match' if result.route_matches else 'miss'} | {result.latency_s:.2f}s",
            flush=True,
        )
        output.write_text(render_report(
            selected, results, base_url=base_url,
            elapsed_s=time.monotonic() - started, questions_only=False,
        ), encoding="utf-8")

    failures = sum(result.status == "Error" for result in results)
    route_misses = sum(not result.route_matches for result in results)
    print(
        f"Completed {len(results)} questions with {failures} errors and {route_misses} route misses. "
        f"Report: {output.resolve()}",
        flush=True,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
