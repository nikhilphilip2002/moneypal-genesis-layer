import json
from pathlib import Path

chains_data = []

# 1. Agent to Loan Details (5 turns)
chains_data.append({
    "id": 1, "role": "Branch Manager", "category": "Agent Portfolio",
    "title": "Agent Vanitha Sourcing & Follow-up", "view": "gold.semantic_loan_account",
    "questions": [
        "customers under vanitha",
        "include tenure and santioned amount with the above details",
        "filter to active loans only",
        "which branch are they from?",
        "show the monthly trend of these sanctions"
    ]
})

# 2. Disbursement Trajectory & Grouping (5 turns)
chains_data.append({
    "id": 2, "role": "CFO", "category": "Disbursement Flow",
    "title": "Disbursement Trajectory & Schemewise Grouping", "view": "gold.semantic_disbursement_event",
    "questions": [
        "total disbursements this financial year",
        "break that down schemewise",
        "now show it monthwise",
        "break it down by application branch",
        "compare with the previous financial year"
    ]
})

# 3. Portfolio Quality & Delinquencies (5 turns)
chains_data.append({
    "id": 3, "role": "CRO", "category": "Credit Risk",
    "title": "NPA Profile and Large Exposure Arrears", "view": "gold.semantic_portfolio_snapshot",
    "questions": [
        "what is our current NPA ratio?",
        "break it down by scheme",
        "show overdue principal by branch",
        "list top 10 overdue accounts",
        "include borrower name and days past due with the above details"
    ]
})

# 4. Long Compaction Chain (10 turns) - explicitly verifies compaction triggers
chains_data.append({
    "id": 4, "role": "Collection Head", "category": "Recovery Operations",
    "title": "Deep Recovery Investigation & Compaction", "view": "gold.semantic_collection_activity",
    "questions": [
        "what is our collection efficiency this month?",
        "break it down branchwise",
        "how much was collected in Aluva?",
        "which agent collected the most there?",
        "list the accounts handled by that agent",
        "include tenure and sanction amount",
        "filter to standard accounts only",
        "what is the total outstanding for these accounts?",
        "show the scheduled repayments for next month",
        "summarize our total exposure for this group"
    ]
})

# 5. Customer KYC & Demographics (5 turns)
chains_data.append({
    "id": 5, "role": "Compliance Officer", "category": "Customer Master",
    "title": "Customer Demographics and KYC Verification", "view": "gold.semantic_customer_profile",
    "questions": [
        "how many customer profiles are in our database?",
        "break down customer count by gender",
        "show the occupation distribution for female borrowers",
        "which customers have missing or expired KYC documents?",
        "list the top 10 oldest customer relationships"
    ]
})

# 6. Customer Document Expiry (5 turns)
chains_data.append({
    "id": 6, "role": "Operations Manager", "category": "Document Management",
    "title": "Customer Document Expiry Funnel", "view": "gold.semantic_customer_document",
    "questions": [
        "list customer documents expiring in the next 90 days",
        "filter to Aadhaar and PAN documents only",
        "group the expiring count by document type",
        "break this down by customer branch",
        "show customer name and mobile number for expiring documents"
    ]
})

# 7. Branch Performance & Operations (5 turns)
chains_data.append({
    "id": 7, "role": "COO", "category": "Branch Operations",
    "title": "Branch Network & Performance Hierarchy", "view": "gold.semantic_branch",
    "questions": [
        "show all operating branches and their branch codes",
        "which branches have the highest active loan count?",
        "what is the total sanctioned amount for Aluva branch?",
        "break down Aluva loans by scheme",
        "show average ticket size across all branches"
    ]
})

# 8. Product Terms and Schemes (5 turns)
chains_data.append({
    "id": 8, "role": "Head of Lending Products", "category": "Product Governance",
    "title": "Product Schemes, ROI & Tenor Matrix", "view": "gold.semantic_product",
    "questions": [
        "list all loan product schemes with minimum and maximum interest rates",
        "which scheme offers the lowest interest rate?",
        "show the maximum loan tenor in months for each scheme",
        "what is the total disbursed amount productwise?",
        "which product scheme has the highest average ticket size?"
    ]
})

# 9. Agent Performance & Sourcing (5 turns)
chains_data.append({
    "id": 9, "role": "Chief Growth Officer", "category": "Sales Distribution",
    "title": "Field Agent Productivity & Portfolio", "view": "gold.semantic_agent",
    "questions": [
        "rank agents by total sanctioned loan volume",
        "who are the top 5 agents by customer count?",
        "show loans sourced by agent 1001",
        "break down agent 1001 volume by scheme",
        "what is the collection efficiency for loans sourced by agent 1001?"
    ]
})

# 10. Sales Hierarchy & Reporting Lines (5 turns)
chains_data.append({
    "id": 10, "role": "HR Head", "category": "Sales Organization",
    "title": "Sales Reporting Structure & Managers", "view": "gold.semantic_sales_hierarchy",
    "questions": [
        "show current sales reporting lines with actor user ID and manager ID",
        "which managers oversee more than 10 agents?",
        "list all active sales agents under regional manager R01",
        "show the total portfolio size managed under R01",
        "break down R01 portfolio by branch"
    ]
})

# 11. Repayment Cash Flow & Collections (5 turns)
chains_data.append({
    "id": 11, "role": "Treasurer", "category": "Cash Management",
    "title": "Principal vs Interest Inflow", "view": "gold.semantic_repayment_event",
    "questions": [
        "show total repayments collected this financial year",
        "split repayments between principal collected and interest collected",
        "show the monthly trend of interest collected",
        "break down interest collected schemewise",
        "which branch collected the highest interest this month?"
    ]
})

# 12. Repayment Schedules & Liquidity Forecast (5 turns)
chains_data.append({
    "id": 12, "role": "ALM Desk", "category": "Asset Liability Management",
    "title": "Scheduled Cash Inflows & Future EMIs", "view": "gold.semantic_repayment_schedule",
    "questions": [
        "what is the total scheduled instalment amount for next month?",
        "show scheduled EMI inflow monthwise for the next 6 months",
        "break down next month scheduled dues by scheme",
        "which branches have the highest scheduled dues next month?",
        "how many accounts are scheduled to pay an EMI next month?"
    ]
})

# 13. PAR 30 & Vintage Analysis (5 turns)
chains_data.append({
    "id": 13, "role": "Risk Analytics", "category": "Vintage Cohorts",
    "title": "Origination Vintage PAR & Delinquency Timing", "view": "gold.semantic_vintage_par",
    "questions": [
        "show PAR 30 by origination vintage and months on book",
        "which vintage year has the highest PAR 30 at month 6?",
        "show the vintage delinquency trend for 2025 originations",
        "break down 2025 vintage PAR by scheme",
        "compare 2024 and 2025 origination performance at month 12"
    ]
})

# 14. Loan Applications & Pipeline (5 turns)
chains_data.append({
    "id": 14, "role": "Credit Ops", "category": "Application Processing",
    "title": "Loan Application Inflow & Rejection Funnel", "view": "gold.semantic_application",
    "questions": [
        "how many loan applications were received this month?",
        "break down loan applications monthwise for the past 12 months",
        "show applications by application branch",
        "what is the application rejection rate by scheme?",
        "which branch has the highest approval rate?"
    ]
})

# 15. Payment Receipts & Channels (5 turns)
chains_data.append({
    "id": 15, "role": "Operations Controller", "category": "Payment Receipts",
    "title": "Payment Receipts & Payment Modes", "view": "gold.semantic_payment_receipt",
    "questions": [
        "show total payment receipts collected this month",
        "break down payment receipts by payment mode",
        "what is the cash payment percentage versus digital modes?",
        "show the daily receipt volume for the past 30 days",
        "which branch processed the most cash receipts?"
    ]
})

# 16. Loan Ledger Transactions & Balance Reconciliation (5 turns)
chains_data.append({
    "id": 16, "role": "Internal Auditor", "category": "Ledger Accounting",
    "title": "Loan Ledger Movements & Audit Trail", "view": "gold.semantic_loan_ledger_event",
    "questions": [
        "show the count of loan ledger transactions this month",
        "show the monthly trend of loan ledger movements",
        "list debit transactions exceeding 10 lakhs in the last 30 days",
        "which accounts had the highest number of ledger movements?",
        "show ledger movements for account 10001"
    ]
})

# 17. Field Collection Visits & Action Tracking (5 turns)
chains_data.append({
    "id": 17, "role": "Recovery Head", "category": "Collection Activity",
    "title": "Collection Visits & Delinquency Follow-up", "view": "gold.semantic_collection_activity",
    "questions": [
        "how many collection activities were logged this month?",
        "break down collection actions by activity type",
        "rank collection agents by number of borrower visits",
        "which branches logged the most collection activities?",
        "what percentage of visited accounts made a repayment within 7 days?"
    ]
})

# 18. General Ledger Balances (5 turns)
chains_data.append({
    "id": 18, "role": "Financial Controller", "category": "Financial Reporting",
    "title": "GL Account Balances & Accounting Reconciliation", "view": "gold.semantic_gl_balance",
    "questions": [
        "show current GL balances by ledger account",
        "what is the total balance on loan asset accounts?",
        "break down GL balances by branch",
        "compare current GL loan assets with the previous quarter",
        "show daily GL balance movements for the gold loan asset account"
    ]
})

# 19. MSME Lead Pipeline & Sourcing (5 turns)
chains_data.append({
    "id": 19, "role": "MSME Business Head", "category": "Lead Generation",
    "title": "MSME Sourcing & Lead Funnel", "view": "gold.semantic_msme_lead",
    "questions": [
        "how many MSME leads are currently in the pipeline?",
        "break down MSME leads by lead status",
        "show MSME leads by vendor ID",
        "which vendor has the highest lead conversion rate?",
        "what is the average ticket size of converted MSME loans?"
    ]
})

# 20. Second Compaction Chain (10 turns) - Large Multi-turn Workflow
chains_data.append({
    "id": 20, "role": "CEO", "category": "Executive Review",
    "title": "Comprehensive Portfolio & Sourcing Audit", "view": "gold.semantic_loan_account",
    "questions": [
        "what is the total principal outstanding across the loan book?",
        "break it down schemewise",
        "now show it by application branch",
        "which branch has the largest exposure?",
        "list the top 10 largest accounts in that branch",
        "include borrower name and interest rate",
        "also add tenure and sanction amount",
        "filter to loans sanctioned in the last 12 months",
        "who are the sourcing agents for these accounts?",
        "what is the overdue status on these loans?"
    ]
})

# Add remaining 50 chains (chains 21 to 70) with 5 turns each (250 questions)
# Covering all 18 views with realistic variants, grouping combinations, and slicing
view_list = [
    ("gold.semantic_loan_account", "Loan Account Details & Terms", "CFO"),
    ("gold.semantic_customer_profile", "Customer Demographics & Profiles", "CRO"),
    ("gold.semantic_customer_document", "Document Tracking & Verification", "COO"),
    ("gold.semantic_branch", "Branch Metrics & Origination", "Branch Head"),
    ("gold.semantic_product", "Product Performance & Pricing", "Product Head"),
    ("gold.semantic_agent", "Agent Portfolios & Quality", "Sales Head"),
    ("gold.semantic_sales_hierarchy", "Sales Supervision & Coverage", "COO"),
    ("gold.semantic_disbursement_event", "Disbursement Trends & Velocities", "Treasurer"),
    ("gold.semantic_repayment_event", "Collections Inflow & Performance", "CFO"),
    ("gold.semantic_repayment_schedule", "Repayment Due Projections", "ALM Desk"),
    ("gold.semantic_portfolio_snapshot", "Portfolio Risk & Asset Quality", "CRO"),
    ("gold.semantic_application", "Application Conversion Funnel", "Credit Head"),
    ("gold.semantic_payment_receipt", "Receipt Reconciliation & Modes", "Ops Controller"),
    ("gold.semantic_loan_ledger_event", "Ledger Accounting & Reconciliation", "Auditor"),
    ("gold.semantic_collection_activity", "Field Recoveries & Action Log", "Collection Head"),
    ("gold.semantic_vintage_par", "Vintage Risk & MOB Performance", "Chief Risk Officer"),
    ("gold.semantic_gl_balance", "General Ledger Accounting", "Financial Controller"),
    ("gold.semantic_msme_lead", "MSME Pipeline & Partner Channels", "MSME Head"),
]

# Generate Chains 21 to 70 (50 chains * 5 turns = 250 questions)
for i in range(21, 71):
    v_idx = (i - 21) % len(view_list)
    v_table, v_cat, v_role = view_list[v_idx]
    
    if v_table == "gold.semantic_loan_account":
        qs = [
            f"show active loan accounts with interest rate above {12 + (i % 6)}%",
            "include sanction amount and tenure",
            "filter by gold loan scheme",
            "which branch has the most such accounts?",
            "what is the total outstanding for these accounts?"
        ]
    elif v_table == "gold.semantic_customer_profile":
        qs = [
            f"how many borrowers are located in district {i % 5 + 1}?",
            "break down by occupation",
            "show customer count by gender",
            "which customers have more than 2 active loans?",
            "include customer name and total sanctioned amount"
        ]
    elif v_table == "gold.semantic_customer_document":
        qs = [
            f"how many customer documents were uploaded in month {i % 12 + 1}?",
            "break down by document type",
            "show documents pending verification",
            "which branch has the highest pending document count?",
            "list the oldest 5 pending verification documents"
        ]
    elif v_table == "gold.semantic_branch":
        qs = [
            f"compare loan sanction volume between branch 1001 and branch 1002",
            "break down sanctions by scheme for branch 1001",
            "show total disbursed amount for branch 1002",
            "what is the PAR 30 ratio for branch 1001?",
            "rank all branches by collection efficiency"
        ]
    elif v_table == "gold.semantic_product":
        qs = [
            f"show total outstanding productwise",
            "break down by scheme",
            "which scheme has the highest number of active loans?",
            "what is the average loan size for that scheme?",
            "show the monthly disbursement trend for that scheme"
        ]
    elif v_table == "gold.semantic_agent":
        qs = [
            f"show total loans sourced by agent A0{i % 20 + 1}",
            "include customer names and sanction amount",
            "also add loan tenure and interest rate",
            "what is the total overdue on these loans?",
            "show repayment status for these accounts"
        ]
    elif v_table == "gold.semantic_sales_hierarchy":
        qs = [
            f"show all reporting lines for sales manager M0{i % 10 + 1}",
            "how many field agents report to this manager?",
            "what is the total disbursement under this hierarchy this month?",
            "break it down schemewise",
            "which agent under this manager disbursed the most?"
        ]
    elif v_table == "gold.semantic_disbursement_event":
        qs = [
            f"what was the disbursement amount in quarter {i % 4 + 1}?",
            "break that down productwise",
            "now show it schemewise",
            "show monthly trend for that quarter",
            "which branch contributed the highest disbursement?"
        ]
    elif v_table == "gold.semantic_repayment_event":
        qs = [
            f"how much principal was repaid in month {i % 12 + 1}?",
            "how much interest was collected in the same month?",
            "break down the interest collected schemewise",
            "show collections by application branch",
            "compare total collections with the prior month"
        ]
    elif v_table == "gold.semantic_repayment_schedule":
        qs = [
            f"show scheduled instalments due in Q{i % 4 + 1}",
            "break down scheduled amount by branch",
            "how many accounts have scheduled payments in this period?",
            "what is the total principal scheduled versus interest scheduled?",
            "which scheme has the largest scheduled dues?"
        ]
    elif v_table == "gold.semantic_portfolio_snapshot":
        qs = [
            f"show total overdue principal across the loan book",
            "break down overdue principal by dpd bucket",
            "show accounts in SMA1 and SMA2",
            "which branch has the highest overdue amount?",
            "list top 10 borrowers in arrears"
        ]
    elif v_table == "gold.semantic_application":
        qs = [
            f"how many loan applications were approved in month {i % 12 + 1}?",
            "what was the total approved sanction value?",
            "break down approved applications by scheme",
            "show the average processing turnaround time by branch",
            "how many applications were rejected in that month?"
        ]
    elif v_table == "gold.semantic_payment_receipt":
        qs = [
            f"show payment receipts collected on weekend dates",
            "break down receipts by payment channel",
            "what is the average receipt ticket size?",
            "show receipt amount by branch",
            "list receipts exceeding 5 lakhs"
        ]
    elif v_table == "gold.semantic_loan_ledger_event":
        qs = [
            f"show total debit ledger entries in month {i % 12 + 1}",
            "show total credit ledger entries in the same month",
            "what is the net ledger balance change?",
            "break down ledger volume by branch",
            "list high value credit transactions above 10 lakhs"
        ]
    elif v_table == "gold.semantic_collection_activity":
        qs = [
            f"how many customer contact attempts were recorded this week?",
            "break down by outcome code",
            "which agents conducted more than 50 visits?",
            "show promised-to-pay conversion rate",
            "break down collection visits by branch"
        ]
    elif v_table == "gold.semantic_vintage_par":
        qs = [
            f"show 30+ DPD vintage curve for Q{i % 4 + 1} disbursements",
            "compare vintage performance across schemes",
            "which vintage cohort shows the steepest delinquency increase?",
            "show MOB 12 PAR 90 by branch",
            "compare vintage performance against portfolio average"
        ]
    elif v_table == "gold.semantic_gl_balance":
        qs = [
            f"show general ledger balances for interest income accounts",
            "break down interest income by branch",
            "compare this financial year interest income with last FY",
            "show GL balance for cash in transit accounts",
            "show daily ledger balance movements for the head office branch"
        ]
    else:  # msme lead
        qs = [
            f"how many MSME leads were sourced from digital channels?",
            "break down digital leads by status",
            "what is the conversion rate of digital leads?",
            "show average sanctioned amount for converted digital leads",
            "which branches processed the most digital MSME leads?"
        ]

    chains_data.append({
        "id": i, "role": v_role, "category": v_cat,
        "title": f"{v_cat} Workflow {i}", "view": v_table,
        "questions": qs
    })

# Total questions from 70 chains: 360 questions
# Now add 140 standalone single-turn questions covering executive & operational questions (total = 500!)
standalone_questions = []

# Generate 140 distinct, high-value questions covering all 18 views
views_pool = [
    ("gold.semantic_loan_account", [
        "What is the total sanctioned loan amount across the loan book?",
        "How many active loan accounts are currently open?",
        "What is the average contractual interest rate on the loan book?",
        "Show total sanctioned loan count by account status.",
        "List all accounts sanctioned in the last 30 days.",
        "Which borrowers have sanctioned amount greater than 25 lakhs?",
        "Show distribution of loans by EMI amount bucket.",
        "What is the total cumulative disbursed amount across all loans?"
    ]),
    ("gold.semantic_customer_profile", [
        "How many distinct borrowers are in our customer master?",
        "Show customer count grouped by home branch.",
        "What is the male versus female borrower percentage?",
        "List all customers with staff status.",
        "Show customer count by occupation category.",
        "Which branch has the highest number of new customer onboardings this year?",
        "How many customer profiles have completed full KYC verification?",
        "Show average customer age across the portfolio."
    ]),
    ("gold.semantic_customer_document", [
        "How many customer documents are currently recorded?",
        "Show document count grouped by document type.",
        "List documents with expiry date in the current calendar year.",
        "Which branch has the most expired customer documents?",
        "Show count of verified versus unverified customer documents.",
        "How many passport documents are recorded in the system?",
        "Show document verification completion percentage by branch.",
        "List documents uploaded in the last 7 days."
    ]),
    ("gold.semantic_branch", [
        "How many active operating branches do we have?",
        "List all branches sorted by branch code.",
        "Which branch has the highest total principal outstanding?",
        "Show total sanctioned loan volume by branch.",
        "What is the total overdue amount in Aluva branch?",
        "Which branch has the lowest PAR 30 ratio?",
        "Show branch-wise borrower count across all operating branches.",
        "What is the average loan ticket size in Ernakulam branch?"
    ]),
    ("gold.semantic_product", [
        "List all loan products and sub-products currently offered.",
        "What is the minimum interest rate across all product schemes?",
        "What is the maximum tenor allowed on agricultural loans?",
        "Show total active loan count by product code.",
        "Which product scheme has the lowest default rate?",
        "Compare ticket sizes across personal loans and gold loans.",
        "Show the sanctioned amount distribution by scheme.",
        "Which product line generated the highest interest income this year?"
    ]),
    ("gold.semantic_agent", [
        "How many active sourcing agents are linked to loans?",
        "Rank top 10 field agents by loan count sanctioned.",
        "Which agent has the lowest delinquency rate on their portfolio?",
        "Show the agent-wise distribution of sanctioned amount.",
        "How many agents sourced loans in Aluva branch?",
        "List all agents who joined in the current financial year.",
        "What is the average customer count per agent?",
        "Which agents have zero delinquent accounts in their book?"
    ]),
    ("gold.semantic_sales_hierarchy", [
        "Show the complete executive sales reporting structure.",
        "How many regional sales managers are currently active?",
        "Which sales manager controls the highest aggregate loan volume?",
        "List all sales supervisors and their reporting branch codes.",
        "Show the ratio of field agents to team leaders.",
        "Which sales team achieved the highest disbursement target this quarter?",
        "Show sales hierarchy coverage for northern branches.",
        "List managers with vacancies in their reporting structure."
    ]),
    ("gold.semantic_disbursement_event", [
        "What is our total disbursed amount all time?",
        "Show monthly disbursement amount for the last 12 months.",
        "Show monthly disbursement count trend.",
        "Which scheme had the highest disbursement volume last month?",
        "Break down disbursements this quarter by application branch.",
        "What is the average daily disbursement run rate this month?",
        "Compare disbursement volume between Q1 and Q2.",
        "Which payment mode accounted for the highest disbursement volume?"
    ]),
    ("gold.semantic_repayment_event", [
        "What is the total repayment amount collected all time?",
        "Show principal collected monthwise for the current financial year.",
        "Show interest collected monthwise for the current financial year.",
        "Which branch had the highest repayment collections this month?",
        "Show daily collection trend for the last 14 days.",
        "What is the total prepayment amount received this month?",
        "Compare repayment collections between this month and last month.",
        "Show collections breakdown by loan scheme."
    ]),
    ("gold.semantic_repayment_schedule", [
        "What is the total instalment amount scheduled for the next 30 days?",
        "Show the 12-month future repayment schedule projection.",
        "How many accounts have scheduled repayments falling due this week?",
        "Break down next quarter scheduled principal dues by scheme.",
        "Which branch has the highest scheduled collections in the upcoming month?",
        "Show scheduled interest inflow for the next financial year.",
        "What percentage of total portfolio is scheduled to mature in 2027?",
        "List accounts with monthly EMI exceeding 50,000 rupees."
    ]),
    ("gold.semantic_portfolio_snapshot", [
        "What is the portfolio at risk 30 days ratio today?",
        "What is the current gross NPA ratio across the book?",
        "Show total overdue amount broken down by branch.",
        "How many accounts are in SMA0 status?",
        "Show the asset classification breakdown across STD, SMA and NPA.",
        "What is the total principal outstanding in NPA accounts?",
        "Which scheme has the highest concentration of delinquent loans?",
        "List top 20 accounts by total overdue amount."
    ]),
    ("gold.semantic_application", [
        "How many total loan applications have been submitted to date?",
        "Show application approval rate by product scheme.",
        "What is the average loan amount requested in applications?",
        "Show the monthly application trend by application branch.",
        "How many applications were rejected due to credit policy?",
        "Which branch received the highest number of applications last month?",
        "Show the loan application conversion funnel from submission to sanction.",
        "What is the median turnaround time from application to sanction?"
    ]),
    ("gold.semantic_payment_receipt", [
        "What is the total value of payment receipts logged this financial year?",
        "Show count of payment receipts by payment mode.",
        "What is the total cash collected across branch counters?",
        "Show receipt volume trend month by month.",
        "Which branch logged the highest number of payment receipts?",
        "What is the average payment receipt amount?",
        "List receipts processed with reversal or cancellation status.",
        "Compare online receipt collections with counter cash receipts."
    ]),
    ("gold.semantic_loan_ledger_event", [
        "How many loan ledger events were recorded in the last 30 days?",
        "Show the daily debit versus credit ledger totals for the past week.",
        "What is the total value of interest charged to accounts this month?",
        "Which accounts had penalty charges debited in the current period?",
        "Show ledger movement count by transaction type.",
        "List all loan accounts with credit adjustments exceeding 1 lakh.",
        "What is the total principal recovery credited through ledger entries?",
        "Show loan ledger event count grouped by branch."
    ]),
    ("gold.semantic_collection_activity", [
        "How many total borrower visits were recorded this month?",
        "Show collection activity breakdown by action code.",
        "What is the success rate of collection calls resulting in repayment?",
        "Which collection agency logged the most field visits?",
        "Show the number of accounts contacted per recovery agent.",
        "What is the average number of visits required before an NPA account cures?",
        "Show collection activity count month by month.",
        "List accounts with more than 5 collection visits in the last 60 days."
    ]),
    ("gold.semantic_vintage_par", [
        "What is the 30+ DPD rate at month 6 for the 2025 vintage?",
        "Show the vintage delinquency matrix across all origination years.",
        "Compare vintage loss curves between gold loans and business loans.",
        "Which origination quarter shows the best repayment track record?",
        "What is the cumulative default rate by months on book?",
        "Show the 90+ DPD vintage performance by branch.",
        "Which scheme has the most stable vintage performance?",
        "Show vintage recovery rates for accounts written off after 24 months."
    ]),
    ("gold.semantic_gl_balance", [
        "What is the total cash balance in branch vault accounts today?",
        "Show general ledger balance for loan provision accounts.",
        "What is the total equity and share capital in the general ledger?",
        "Show branch-wise trial balance summary for loan assets.",
        "What is the current balance in accrued interest receivable?",
        "Compare GL liability balances between this quarter and last quarter.",
        "Show GL balance trend for operational expenditure accounts.",
        "What is the reconciliation difference between loan sub-ledger and GL balance?"
    ]),
    ("gold.semantic_msme_lead", [
        "How many active MSME business leads are currently unassigned?",
        "Show MSME lead conversion rate by sourcing partner.",
        "What is the total expected loan demand in the MSME pipeline?",
        "Which industry sector represents the largest share of MSME leads?",
        "Show the monthly trend of MSME leads converted into sanctioned loans.",
        "What is the drop-off rate between MSME lead qualification and credit assessment?",
        "Which regional hub generated the most qualified MSME leads?",
        "Show average time taken to convert an MSME lead into a disbursed loan."
    ])
]

# Pick standalone questions to reach exactly 500 total questions
current_total = sum(len(c["questions"]) for c in chains_data)
needed = 500 - current_total

standalone_id_start = len(chains_data) + 1
chain_id_counter = standalone_id_start

for view_table, q_list in views_pool:
    for q in q_list:
        if current_total >= 500:
            break
        chains_data.append({
            "id": chain_id_counter,
            "role": "Executive",
            "category": "Single Turn Analysis",
            "title": f"Single Query - {view_table.split('.')[-1].replace('_', ' ').title()}",
            "view": view_table,
            "questions": [q]
        })
        chain_id_counter += 1
        current_total += 1

total_q_count = sum(len(c["questions"]) for c in chains_data)
print(f"Generated {len(chains_data)} chains with a total of {total_q_count} questions.")

data_path = Path("scripts/fixtures/loanbook_500_questions.json")
data_path.write_text(json.dumps(chains_data, indent=2), encoding="utf-8")
print(f"Saved questions to {data_path.resolve()}")
