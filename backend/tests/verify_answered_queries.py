import json
import urllib.request
import time

BASE_URL = "http://100.70.118.31:4321"

ANSWERED_QUERIES = [
    (1, "A. CEO", "How is the business performing today, and what are the 5 things I need to know?"),
    (2, "A. CEO", "What has changed materially in the business this month, and why?"),
    (6, "A. CEO", "Which products, geographies or channels are driving growth?"),
    (8, "A. CEO", "What are the biggest emerging issues that management should be concerned about?"),
    (11, "B. Sales", "Why are disbursements above or below target?"),
    (13, "B. Sales", "Which products and channels are generating the highest growth?"),
    (18, "B. Sales", "Which branches or channels have the best combination of growth and credit quality?"),
    (19, "C. Risk", "How healthy is our credit portfolio right now?"),
    (21, "C. Risk", "Which products, regions, branches or customer segments have the highest risk?"),
    (23, "C. Risk", "Which borrowers show early warning signs of default?"),
    (27, "C. Risk", "What is our concentration risk across customers, industries, geographies or products?"),
    (29, "D. Collections", "Which accounts should Collections focus on today to maximise recovery?"),
    (31, "D. Collections", "What is driving the deterioration in collections performance?"),
    (33, "D. Collections", "Which delinquency buckets are deteriorating fastest?"),
    (35, "D. Collections", "Which accounts should be escalated for legal or recovery action?"),
    (36, "E. Finance", "Where are we making and losing money across products, branches, channels and customers?"),
    (46, "G. Compliance", "Are there any significant compliance or regulatory exceptions that require attention?"),
]

def parse_sse(text):
    events = []
    current_event = {}
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            if current_event:
                events.append(current_event)
                current_event = {}
            continue
        if line.startswith('event:'):
            current_event['event'] = line[6:].strip()
        elif line.startswith('data:'):
            data_str = line[5:].strip()
            try:
                current_event['data'] = json.loads(data_str)
            except Exception:
                current_event['data'] = data_str
    if current_event:
        events.append(current_event)
    return events

print("Cross-verifying the 17 answered queries in detail...\n")

for q_id, cat, q_text in ANSWERED_QUERIES:
    print(f"==================================================")
    print(f"Q{q_id} [{cat}]: \"{q_text}\"")
    print(f"==================================================")
    
    payload = json.dumps({"question": q_text}).encode('utf-8')
    req = urllib.request.Request(
        f"{BASE_URL}/api/nlq/ask",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer mock-token-admin"
        },
        method="POST"
    )
    start_t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read()
            elapsed = time.time() - start_t
            events = parse_sse(raw.decode('utf-8', errors='replace'))
            
            plan_ev = next((e for e in events if e.get('event') == 'plan'), None)
            route = plan_ev.get('data', {}).get('route') if plan_ev else "unknown"
            
            print(f"⏱️  Duration: {elapsed:.2f}s | Route: {route}")
            
            found_payload = False
            for ev in events:
                etype = ev.get('event')
                data = ev.get('data', {})
                
                if etype == 'briefing' and data.get('briefing'):
                    found_payload = True
                    b = data['briefing']
                    print(f"✅ Route: Briefing ({b.get('persona')})")
                    print(f"   Headline: \"{b.get('headline')}\"")
                    signals = b.get('signals', [])
                    print(f"   Signals Count: {len(signals)}")
                    for s in signals:
                        print(f"     • [{s.get('severity').upper()}] {s.get('label')}: {s.get('text')}")
                
                elif etype == 'analysis' and data.get('analysis'):
                    found_payload = True
                    a = data['analysis']
                    print(f"✅ Route: Analysis ({a.get('preset')})")
                    print(f"   Title: \"{a.get('title')}\"")
                    print(f"   Headline: \"{a.get('headline')}\"")
                    findings = a.get('findings', [])
                    print(f"   Findings Count: {len(findings)}")
                    for f in findings:
                        print(f"     • {f.get('label')}: {f.get('text')}")
                
                elif etype == 'worklist' and data.get('worklist'):
                    found_payload = True
                    w = data['worklist']
                    items = w.get('items', [])
                    print(f"✅ Route: Worklist")
                    print(f"   Title: \"{w.get('title')}\"")
                    print(f"   Total Accounts: {len(items)}")
                    if items:
                        top = items[0]
                        flds = top.get('fields', {})
                        print(f"   Rank #1 Account: {top.get('account')} | Borrower: {flds.get('borrower')} | Branch: {flds.get('branch')}")
                        print(f"   Overdue: ₹{flds.get('total_overdue'):,.2f} | DPD: {flds.get('dpd_days')} | Class: {flds.get('asset_class')}")
                        print(f"   Playbook Action: \"{top.get('action')}\"")
                        print(f"   Triggers: {top.get('triggered')}")
                
                elif etype == 'chart' and data.get('chart'):
                    found_payload = True
                    c = data['chart']
                    rows = c.get('data', [])
                    sql = c.get('sql', '')
                    print(f"📊 Route: Chart / SQL ({c.get('chart_type')})")
                    print(f"   Title: \"{c.get('title')}\"")
                    print(f"   SQL Query:\n     {sql.strip() if sql else 'None'}")
                    print(f"   Rows Returned: {len(rows)}")
                    if rows:
                        print(f"   Sample Rows (up to 2):")
                        for r in rows[:2]:
                            print(f"     {r}")
                    else:
                        print(f"   ⚠️ Note: 0 rows returned (Query executed successfully but dataset yielded no rows for this slice/period)")
                        
                elif etype == 'refusal':
                    found_payload = True
                    print(f"🛑 Refusal: [{data.get('reason')}] {data.get('message')}")
                    
            if not found_payload:
                print("⚠️ No payload event found in SSE stream")
                
    except Exception as e:
        print(f"❌ Error: {e}")
    print()
