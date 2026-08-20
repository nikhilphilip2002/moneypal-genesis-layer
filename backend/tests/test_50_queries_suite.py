#!/usr/bin/env python3
"""Enterprise 50-Questions Test Suite for Moneypal Genesis AI Assistant.

Usage:
    python backend/tests/test_50_queries_suite.py
    NLQ_TEST_URL=http://localhost:8000 python backend/tests/test_50_queries_suite.py
    python backend/tests/test_50_queries_suite.py --workers 1 --output results.json
"""

import argparse
import concurrent.futures
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_URL = os.environ.get("NLQ_TEST_URL", "http://100.70.118.31:4321")

QUESTIONS = [
    # A. CEO / Enterprise
    (1, "A. CEO / Enterprise", "How is the business performing today, and what are the 5 things I need to know?"),
    (2, "A. CEO / Enterprise", "What has changed materially in the business this month, and why?"),
    (3, "A. CEO / Enterprise", "Are we on track against our annual business plan?"),
    (4, "A. CEO / Enterprise", "Which business KPIs are currently off-target?"),
    (5, "A. CEO / Enterprise", "What are the biggest risks to achieving this quarter's targets?"),
    (6, "A. CEO / Enterprise", "Which products, geographies or channels are driving growth?"),
    (7, "A. CEO / Enterprise", "Where are we underperforming, and what is causing it?"),
    (8, "A. CEO / Enterprise", "What are the biggest emerging issues that management should be concerned about?"),
    (9, "A. CEO / Enterprise", "What decisions require my attention today?"),
    (10, "A. CEO / Enterprise", "What am I not asking you that I should be asking?"),

    # B. Sales & Distribution
    (11, "B. Sales & Distribution", "Why are disbursements above or below target?"),
    (12, "B. Sales & Distribution", "Which branches are performing above and below expectations?"),
    (13, "B. Sales & Distribution", "Which products and channels are generating the highest growth?"),
    (14, "B. Sales & Distribution", "Which sales teams or locations are consistently underperforming?"),
    (15, "B. Sales & Distribution", "Where are we losing customers during the acquisition process?"),
    (16, "B. Sales & Distribution", "What is the conversion rate at each stage of the sales funnel?"),
    (17, "B. Sales & Distribution", "Which customer segments have the highest potential for growth?"),
    (18, "B. Sales & Distribution", "Which branches or channels have the best combination of growth and credit quality?"),

    # C. Credit & Risk
    (19, "C. Credit & Risk", "How healthy is our credit portfolio right now?"),
    (20, "C. Credit & Risk", "Why is portfolio risk increasing or decreasing?"),
    (21, "C. Credit & Risk", "Which products, regions, branches or customer segments have the highest risk?"),
    (22, "C. Credit & Risk", "Which loans are most likely to become delinquent in the next 30/60/90 days?"),
    (23, "C. Credit & Risk", "Which borrowers show early warning signs of default?"),
    (24, "C. Credit & Risk", "How is our vintage performance changing?"),
    (25, "C. Credit & Risk", "Where are approval rates changing significantly, and why?"),
    (26, "C. Credit & Risk", "Are there unusual patterns in applications, approvals or disbursements that indicate potential risk?"),
    (27, "C. Credit & Risk", "What is our concentration risk across customers, industries, geographies or products?"),
    (28, "C. Credit & Risk", "What will happen to portfolio quality if current delinquency trends continue?"),

    # D. Collections & Recovery
    (29, "D. Collections & Recovery", "Which accounts should Collections focus on today to maximise recovery?"),
    (30, "D. Collections & Recovery", "Which overdue customers have the highest probability of payment if contacted now?"),
    (31, "D. Collections & Recovery", "What is driving the deterioration in collections performance?"),
    (32, "D. Collections & Recovery", "Which collection agencies, branches or teams are performing best?"),
    (33, "D. Collections & Recovery", "Which delinquency buckets are deteriorating fastest?"),
    (34, "D. Collections & Recovery", "What collection strategy should we use for different customer segments?"),
    (35, "D. Collections & Recovery", "Which accounts should be escalated for legal or recovery action?"),

    # E. Finance
    (36, "E. Finance", "Where are we making and losing money across products, branches, channels and customers?"),
    (37, "E. Finance", "Why is profitability different from budget?"),
    (38, "E. Finance", "What are the biggest cost overruns and what is causing them?"),
    (39, "E. Finance", "Which products or customer segments have the highest contribution margin?"),
    (40, "E. Finance", "How is our cost of acquisition changing?"),
    (41, "E. Finance", "What are the major financial leakages or anomalies I should investigate?"),

    # F. Operations / Technology
    (42, "F. Operations / Technology", "Where are our biggest operational bottlenecks?"),
    (43, "F. Operations / Technology", "Which processes have the highest rejection, rework, exception or turnaround time?"),
    (44, "F. Operations / Technology", "What operational issues are currently impacting customer experience or revenue?"),
    (45, "F. Operations / Technology", "Which technology or data issues are currently impacting business performance?"),

    # G. Compliance / Legal / HR / Strategy
    (46, "G. Compliance / Legal / Strategy", "Are there any significant compliance or regulatory exceptions that require attention?"),
    (47, "G. Compliance / Legal / Strategy", "Which legal matters, contracts or cases require management attention?"),
    (48, "G. Compliance / Legal / Strategy", "What control failures or recurring audit observations should management be concerned about?"),
    (49, "G. Compliance / Legal / Strategy", "Are we achieving our strategic initiatives, and which ones are off-track?"),
    (50, "G. Compliance / Legal / Strategy", "Where are we facing people, productivity or capability gaps that could affect business performance?"),
]


def parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.strip().split("\n\n"):
        if not block.strip():
            continue
        lines = block.strip().split("\n")
        event_name = None
        data_lines = []
        for line in lines:
            if line.startswith("event:"):
                event_name = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        if event_name:
            data_str = "\n".join(data_lines)
            try:
                data_obj = json.loads(data_str)
            except Exception:
                data_obj = data_str
            events.append({"event": event_name, "data": data_obj})
    return events


def test_question(q_tuple: tuple[int, str, str], base_url: str) -> dict:
    q_id, cat, q_text = q_tuple
    payload = json.dumps({"question": q_text}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/nlq/ask",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer mock-token-admin",
        },
        method="POST",
    )
    start_t = time.time()
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                raw = resp.read()
                elapsed = time.time() - start_t
                events = parse_sse(raw.decode("utf-8", errors="replace"))

                plan_ev = next((e for e in events if e.get("event") == "plan"), None)
                route = plan_ev.get("data", {}).get("route") if plan_ev else "unknown"

                res = {
                    "id": q_id,
                    "category": cat,
                    "question": q_text,
                    "duration_s": round(elapsed, 2),
                    "route": route,
                    "status": "unknown",
                    "output_type": "",
                    "headline": "",
                    "row_count": 0,
                    "signals_count": 0,
                    "findings_count": 0,
                    "refusal_reason": "",
                    "refusal_message": "",
                    "details": "",
                }

                for ev in events:
                    etype = ev.get("event")
                    data = ev.get("data", {})
                    if not isinstance(data, dict):
                        continue

                    if etype == "briefing" and data.get("briefing"):
                        b = data["briefing"]
                        res["status"] = "answered"
                        res["output_type"] = "briefing"
                        res["headline"] = b.get("headline", "")
                        res["signals_count"] = len(b.get("signals", []))
                        res["details"] = f"Briefing ({b.get('persona')}): {b.get('headline')} ({res['signals_count']} signals)"

                    elif etype == "analysis" and data.get("analysis"):
                        a = data["analysis"]
                        res["status"] = "answered"
                        res["output_type"] = "analysis"
                        res["headline"] = a.get("headline", "")
                        res["findings_count"] = len(a.get("findings", []))
                        res["details"] = f"Analysis '{a.get('title')}': {a.get('headline')} ({res['findings_count']} findings)"

                    elif etype == "worklist" and data.get("worklist"):
                        w = data["worklist"]
                        items = w.get("items", [])
                        res["status"] = "answered"
                        res["output_type"] = "worklist"
                        res["headline"] = w.get("title", "")
                        res["row_count"] = len(items)
                        res["details"] = f"Worklist '{w.get('title')}': {len(items)} accounts"

                    elif etype == "chart" and data.get("chart"):
                        c = data["chart"]
                        rows = c.get("data", []) or c.get("rows", [])
                        res["status"] = "answered"
                        res["output_type"] = f"chart ({c.get('chart_type')})"
                        res["headline"] = c.get("title", "")
                        res["row_count"] = len(rows)
                        res["details"] = f"Chart '{c.get('title')}' ({c.get('chart_type')}): {len(rows)} rows"

                    elif etype == "refusal":
                        res["status"] = "refused"
                        res["output_type"] = "refusal"
                        res["refusal_reason"] = data.get("reason", "")
                        res["refusal_message"] = data.get("message", "")
                        res["details"] = f"Refusal [{data.get('reason')}]: {data.get('message')}"

                    elif etype == "clarify":
                        res["status"] = "clarify"
                        res["output_type"] = "clarify"
                        res["details"] = f"Clarification: {data.get('prompt')}"

                return res
        except Exception as e:
            if attempt == 1:
                return {
                    "id": q_id,
                    "category": cat,
                    "question": q_text,
                    "duration_s": round(time.time() - start_t, 2),
                    "route": "error",
                    "status": "error",
                    "output_type": "error",
                    "details": f"Failed: {e}",
                }
            time.sleep(1)


SELECTED_IDS = [1, 2, 4, 6, 8, 9, 11, 13, 18, 19, 21, 23, 27, 29, 31, 33, 35, 36, 45, 46]


def parse_id_list(id_str: str) -> set[int]:
    ids = set()
    for part in id_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            ids.update(range(int(start_s.strip()), int(end_s.strip()) + 1))
        else:
            ids.add(int(part))
    return ids


def main():
    parser = argparse.ArgumentParser(description="Test runner for NLQ enterprise questions")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Base URL (default: {DEFAULT_URL})")
    parser.add_argument("--workers", type=int, default=1, help="Concurrency workers (default: 1)")
    parser.add_argument("--output", default="backend/tests/top_50_latest_results.json", help="Path to save output JSON")
    parser.add_argument("--ids", type=str, default="", help="Comma-separated IDs or ranges to run (e.g. '1,2,6,11' or '1-10')")
    parser.add_argument("--category", type=str, default="", help="Filter by category substring (e.g. 'CEO', 'Sales', 'Credit')")
    parser.add_argument("--selected", action="store_true", help="Run only the curated selected/answered enterprise queries")
    parser.add_argument("--remaining", action="store_true", help="Run the remaining queries (the ones outside the curated selected list)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print full output details for each response")
    args = parser.parse_args()

    active_questions = QUESTIONS
    if args.selected:
        active_questions = [q for q in active_questions if q[0] in SELECTED_IDS]
    elif args.remaining:
        active_questions = [q for q in active_questions if q[0] not in SELECTED_IDS]
    elif args.ids:
        target_ids = parse_id_list(args.ids)
        active_questions = [q for q in active_questions if q[0] in target_ids]

    if args.category:
        cat_lower = args.category.lower()
        active_questions = [q for q in active_questions if cat_lower in q[1].lower()]

    if not active_questions:
        print("❌ No matching questions found for the given criteria.")
        sys.exit(1)

    total_count = len(active_questions)
    print(f"🚀 Running NLQ Test Suite against: {args.url}")
    print(f"📋 Questions to run: {total_count} / {len(QUESTIONS)}")
    print(f"⚙️  Concurrency: {args.workers} worker(s)\n")

    results = []
    start_all = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {executor.submit(test_question, q, args.url): q for q in active_questions}
        for idx, future in enumerate(concurrent.futures.as_completed(future_map), 1):
            res = future.result()
            results.append(res)
            st_color = "✅" if res["status"] == "answered" else ("🛑" if res["status"] == "refused" else "❓")
            print(f"[{idx:02d}/{total_count:02d}] {st_color} Q{res['id']:02d} [{res['status'].upper()}] ({res['output_type']}) - {res['question'][:48]}... ({res['duration_s']}s)")
            if args.verbose and res.get("details"):
                print(f"       └─ {res['details']}")

    results.sort(key=lambda x: x["id"])
    total_elapsed = time.time() - start_all

    answered = sum(1 for r in results if r["status"] == "answered")
    refused = sum(1 for r in results if r["status"] == "refused")
    clarify = sum(1 for r in results if r["status"] == "clarify")
    errors = sum(1 for r in results if r["status"] == "error")

    print("\n" + "=" * 60)
    print(f"📊 SUMMARY REPORT (Total Time: {total_elapsed:.1f}s)")
    print("=" * 60)
    print(f"Total Questions Evaluated : {total_count}")
    print(f"Directly Answered         : {answered} ({answered/total_count*100:.1f}%)")
    print(f"Properly Refused          : {refused} ({refused/total_count*100:.1f}%)")
    print(f"Clarifications Requested  : {clarify} ({clarify/total_count*100:.1f}%)")
    print(f"Errors / Timeouts         : {errors} ({errors/total_count*100:.1f}%)")
    print("=" * 60)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"💾 Results saved to: {args.output}\n")


if __name__ == "__main__":
    main()
