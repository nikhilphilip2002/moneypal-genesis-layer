import os
import psycopg2
from typing import Dict, Any, List, Optional

COLUMN_MEANINGS = {
    # genlnacnts
    "gnlnac_entity_num": "Entity/Branch Number",
    "gnlnac_acnt_num": "Account Number (PRIMARY KEY)",
    "gnlnac_cust_id": "Customer ID",
    "gnlnac_prod_code": "Product Code",
    "gnlnac_schm_code": "Scheme Code",
    "gnlnac_appl_brn_code": "Application Branch Code",
    "gnlnac_appl_num": "Application Number",
    "gnlnac_sanc_date": "Sanction/Approval Date",
    "gnlnac_sanc_amt": "Sanctioned Amount",
    "gnlnac_sanc_by": "Sanctioned By",
    "gnlnac_acrual_method": "Accrual Method",
    "gnlnac_loan_type": "Loan Type",
    "gnlnac_epi_freq": "EPI Frequency",
    "gnlnac_prin_freq": "Principal Frequency",
    "gnlnac_int_freq": "Interest Frequency",
    "gnlnac_princ_noi": "Principal Number of Installments",
    "gnlnac_repay_stdt": "Repayment Start Date",
    "gnlnac_repay_lastdt": "Repayment Last Date",
    "gnlnac_ln_intrate": "Loan Interest Rate",

    # loanrepay
    "lnrepay_entity_num": "Entity/Branch Number",
    "lnrepay_acnt_no": "Account Number (FOREIGN KEY)",
    "lnrepay_sl_no": "Serial Number/Line Item",
    "lnrepay_repay_date": "Repayment Date",
    "lnrepay_prin_amt": "Principal Amount",
    "lnrepay_int_amt": "Interest Amount",
    "lnrepay_prin_pdamt": "Principal Paid Amount",
    "lnrepay_int_pdamt": "Interest Paid Amount",

    # loanschedule
    "lnsched_entity_num": "Entity/Branch Number",
    "lnsched_acnt_no": "Account Number (FOREIGN KEY)",
    "lnsched_sl_no": "Serial Number/Schedule Line",
    "lnsched_sched_date": "Scheduled Payment Date",
    "lnsched_prin_amt": "Principal Amount Due",
    "lnsched_int_amt": "Interest Amount Due",

    # genlndisb
    "genlndisb_entity_num": "Entity/Branch Number",
    "genlndisb_acnt_num": "Account Number (FOREIGN KEY)",
    "genlndisb_disb_sl": "Disbursement Serial Number",
    "genlndisb_disb_date": "Disbursement Date",
    "genlndisb_disb_amt": "Disbursement Amount",
    "genlndisb_net_pay_amt": "Net Payment Amount",
}

# Minimalist, clean color palette (subtle slates, darks, and minimal accents)
NODE_TYPE_STYLES = {
    "account": {"color": "#1e293b", "label": "Account Master", "size": 24},       # Slate 800
    "customer": {"color": "#0f172a", "label": "Borrower Profile", "size": 20},     # Slate 900
    "disbursement": {"color": "#334155", "label": "Disbursement Payout", "size": 16}, # Slate 700
    "repayment": {"color": "#475569", "label": "Repayment Log", "size": 16},      # Slate 600
    "schedule": {"color": "#64748b", "label": "Installment Schedule", "size": 14} # Slate 500
}

def get_connection():
    host = os.environ.get("POSTGRES_HOST", "100.70.118.31")
    if host.startswith("http://"):
        host = host[7:]
    if host.endswith("/"):
        host = host[:-1]
    
    port = int(os.environ.get("POSTGRES_PORT", "5432"))
    dbname = os.environ.get("POSTGRES_DB", "moneypaldb")
    user = os.environ.get("POSTGRES_USER", "moneypal")
    password = os.environ.get("POSTGRES_PASSWORD", "moneypal123")
    
    return psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        connect_timeout=3
    )

def get_db_schema_graph(search_term: Optional[str] = None) -> Dict[str, Any]:
    """
    Constructs a Data Instance Curiosity Graph for a specific selected Customer/Account,
    showing its real connected disbursements, repayments, and amortization schedule lines.
    """
    sample_accounts = []
    selected_account = None
    is_live = False

    # Default fallback account data if DB is offline or search misses
    mock_accounts_db = [
        {
            "acnt_num": 1001044,
            "cust_id": 90412,
            "cust_name": "Apex Commercial Logistics",
            "sanc_amt": 350000,
            "sanc_date": "2025-11-10",
            "loan_type": "Term Loan",
            "interest_rate": 11.5,
            "disbursements": [
                {"sl": 1, "amt": 350000, "date": "2025-11-12", "to": "Self Account"}
            ],
            "repayments": [
                {"sl": 1, "prin": 25000, "int": 3354, "date": "2025-12-10"},
                {"sl": 2, "prin": 25000, "int": 3114, "date": "2026-01-10"},
                {"sl": 3, "prin": 25000, "int": 2875, "date": "2026-02-10"}
            ],
            "schedules": [
                {"sl": 1, "prin": 25000, "int": 3354, "date": "2025-12-10"},
                {"sl": 2, "prin": 25000, "int": 3114, "date": "2026-01-10"},
                {"sl": 3, "prin": 25000, "int": 2875, "date": "2026-02-10"},
                {"sl": 4, "prin": 25000, "int": 2635, "date": "2026-03-10"},
                {"sl": 5, "prin": 25000, "int": 2395, "date": "2026-04-10"}
            ]
        },
        {
            "acnt_num": 1002219,
            "cust_id": 90815,
            "cust_name": "Sunrise Agrotech NBFC",
            "sanc_amt": 500000,
            "sanc_date": "2025-08-20",
            "loan_type": "Working Capital",
            "interest_rate": 12.0,
            "disbursements": [
                {"sl": 1, "amt": 250000, "date": "2025-08-22", "to": "Vendor A"},
                {"sl": 2, "amt": 250000, "date": "2025-09-15", "to": "Vendor B"}
            ],
            "repayments": [
                {"sl": 1, "prin": 50000, "int": 5000, "date": "2025-09-20"},
                {"sl": 2, "prin": 50000, "int": 4500, "date": "2025-10-20"}
            ],
            "schedules": [
                {"sl": 1, "prin": 50000, "int": 5000, "date": "2025-09-20"},
                {"sl": 2, "prin": 50000, "int": 4500, "date": "2025-10-20"},
                {"sl": 3, "prin": 50000, "int": 4000, "date": "2025-11-20"},
                {"sl": 4, "prin": 50000, "int": 3500, "date": "2025-12-20"}
            ]
        },
        {
            "acnt_num": 1005112,
            "cust_id": 91204,
            "cust_name": "Vanguard Micro Enterprises",
            "sanc_amt": 1200000,
            "sanc_date": "2026-01-15",
            "loan_type": "Asset Finance",
            "interest_rate": 10.8,
            "disbursements": [],
            "repayments": [],
            "schedules": [
                {"sl": 1, "prin": 100000, "int": 10800, "date": "2026-02-15"}
            ]
        }
    ]

    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # 1. Fetch sample accounts list for quick selection
        cur.execute("SELECT gnlnac_acnt_num, gnlnac_cust_id, gnlnac_sanc_amt FROM bronze.genlnacnts ORDER BY gnlnac_sanc_amt DESC LIMIT 10;")
        sample_rows = cur.fetchall()
        sample_accounts = [
            {"account_num": str(r[0]), "cust_id": str(r[1] or 'N/A'), "amount": f"₹{r[2]:,}" if r[2] else "₹0"}
            for r in sample_rows
        ]

        # 2. Determine targeted account number
        target_acnt = None
        if search_term and search_term.strip():
            term = search_term.strip().replace("Account #", "").replace("CUST-", "")
            if term.isdigit():
                target_acnt = int(term)

        if not target_acnt and sample_rows:
            target_acnt = sample_rows[0][0]

        if target_acnt:
            # Query Account info
            cur.execute("""
                SELECT gnlnac_acnt_num, gnlnac_cust_id, gnlnac_sanc_amt, gnlnac_sanc_date, gnlnac_loan_type, gnlnac_ln_intrate
                FROM bronze.genlnacnts WHERE gnlnac_acnt_num = %s;
            """, (target_acnt,))
            acnt_row = cur.fetchone()
            
            if acnt_row:
                # Query Disbursements
                cur.execute("""
                    SELECT genlndisb_disb_sl, genlndisb_disb_amt, genlndisb_disb_date, genlndisb_disb_to
                    FROM bronze.genlndisb WHERE genlndisb_acnt_num = %s ORDER BY genlndisb_disb_sl LIMIT 10;
                """, (target_acnt,))
                disb_rows = cur.fetchall()

                # Query Repayments
                cur.execute("""
                    SELECT lnrepay_sl_no, lnrepay_prin_pdamt, lnrepay_int_pdamt, lnrepay_repay_date
                    FROM bronze.loanrepay WHERE lnrepay_acnt_no = %s ORDER BY lnrepay_sl_no LIMIT 10;
                """, (target_acnt,))
                repay_rows = cur.fetchall()

                # Query Schedules
                cur.execute("""
                    SELECT lnsched_sl_no, lnsched_prin_amt, lnsched_int_amt, lnsched_sched_date
                    FROM bronze.loanschedule WHERE lnsched_acnt_no = %s ORDER BY lnsched_sl_no LIMIT 10;
                """, (target_acnt,))
                sched_rows = cur.fetchall()

                selected_account = {
                    "acnt_num": acnt_row[0],
                    "cust_id": acnt_row[1] or 90000 + (acnt_row[0] % 1000),
                    "sanc_amt": float(acnt_row[2] or 0),
                    "sanc_date": str(acnt_row[3] or "2025-10-01"),
                    "loan_type": str(acnt_row[4] or "Term Loan"),
                    "interest_rate": float(acnt_row[5] or 11.5),
                    "disbursements": [{"sl": r[0], "amt": float(r[1] or 0), "date": str(r[2] or "N/A"), "to": str(r[3] or "Beneficiary")} for r in disb_rows],
                    "repayments": [{"sl": r[0], "prin": float(r[1] or 0), "int": float(r[2] or 0), "date": str(r[3] or "N/A")} for r in repay_rows],
                    "schedules": [{"sl": r[0], "prin": float(r[1] or 0), "int": float(r[2] or 0), "date": str(r[3] or "N/A")} for r in sched_rows]
                }
        conn.close()
        is_live = True

    except Exception as e:
        is_live = False

    # Fallback to mock dataset if query yielded nothing or DB is offline
    if not selected_account:
        selected_account = mock_accounts_db[0]
        if search_term and search_term.strip():
            for acc in mock_accounts_db:
                if str(acc["acnt_num"]) in search_term or str(acc["cust_id"]) in search_term:
                    selected_account = acc
                    break

    if not sample_accounts:
        sample_accounts = [
            {"account_num": str(acc["acnt_num"]), "cust_id": str(acc["cust_id"]), "amount": f"₹{acc['sanc_amt']:,}"}
            for acc in mock_accounts_db
        ]

    # Build Instance Graph Payload
    nodes = []
    edges = []

    # 1. Central Account Master Node
    acnt_id = f"ACNT-{selected_account['acnt_num']}"
    nodes.append({
        "id": acnt_id,
        "type": "account",
        "title": f"Account #{selected_account['acnt_num']}",
        "subtitle": f"Sanction: ₹{selected_account['sanc_amt']:,}",
        "node_label": "Loan Master",
        "color": NODE_TYPE_STYLES["account"]["color"],
        "size": NODE_TYPE_STYLES["account"]["size"],
        "details": {
            "Account Number": str(selected_account["acnt_num"]),
            "Customer ID": str(selected_account["cust_id"]),
            "Sanctioned Amount": f"₹{selected_account['sanc_amt']:,}",
            "Loan Type": selected_account["loan_type"],
            "Interest Rate": f"{selected_account['interest_rate']}% p.a.",
            "Sanction Date": selected_account["sanc_date"]
        }
    })

    # 2. Borrower Profile Node
    cust_id = f"CUST-{selected_account['cust_id']}"
    nodes.append({
        "id": cust_id,
        "type": "customer",
        "title": f"Borrower #{selected_account['cust_id']}",
        "subtitle": selected_account.get("cust_name", f"Customer ID #{selected_account['cust_id']}"),
        "node_label": "Borrower",
        "color": NODE_TYPE_STYLES["customer"]["color"],
        "size": NODE_TYPE_STYLES["customer"]["size"],
        "details": {
            "Customer ID": str(selected_account["cust_id"]),
            "Risk Profile": "Standard NBFC Category A",
            "Linked Accounts": f"1 Account (#{selected_account['acnt_num']})"
        }
    })
    edges.append({
        "source": cust_id,
        "target": acnt_id,
        "label": "HELD_BY",
        "purpose": "Primary Borrower Ownership"
    })

    # 3. Disbursement Nodes
    for disb in selected_account["disbursements"]:
        disb_id = f"DISB-{disb['sl']}"
        nodes.append({
            "id": disb_id,
            "type": "disbursement",
            "title": f"Disbursement #{disb['sl']}",
            "subtitle": f"₹{disb['amt']:,}",
            "node_label": "Payout",
            "color": NODE_TYPE_STYLES["disbursement"]["color"],
            "size": NODE_TYPE_STYLES["disbursement"]["size"],
            "details": {
                "Disbursement Line": str(disb["sl"]),
                "Payout Amount": f"₹{disb['amt']:,}",
                "Disbursement Date": disb["date"],
                "Disbursed To": disb.get("to", "Beneficiary")
            }
        })
        edges.append({
            "source": acnt_id,
            "target": disb_id,
            "label": "DISBURSED",
            "purpose": "Funds Payout"
        })

    # 4. Repayment Nodes
    for rep in selected_account["repayments"]:
        rep_id = f"REPAY-{rep['sl']}"
        tot_paid = rep["prin"] + rep["int"]
        nodes.append({
            "id": rep_id,
            "type": "repayment",
            "title": f"Repayment #{rep['sl']}",
            "subtitle": f"Paid: ₹{tot_paid:,}",
            "node_label": "Receipt",
            "color": NODE_TYPE_STYLES["repayment"]["color"],
            "size": NODE_TYPE_STYLES["repayment"]["size"],
            "details": {
                "Repayment Line": str(rep["sl"]),
                "Principal Paid": f"₹{rep['prin']:,}",
                "Interest Paid": f"₹{rep['int']:,}",
                "Total Amount Paid": f"₹{tot_paid:,}",
                "Payment Date": rep["date"]
            }
        })
        edges.append({
            "source": rep_id,
            "target": acnt_id,
            "label": "PAID_REPAYMENT",
            "purpose": "Credit Receipt"
        })

    # 5. Schedule Nodes
    for sch in selected_account["schedules"]:
        sch_id = f"SCHED-{sch['sl']}"
        tot_due = sch["prin"] + sch["int"]
        nodes.append({
            "id": sch_id,
            "type": "schedule",
            "title": f"Schedule #{sch['sl']}",
            "subtitle": f"Due: ₹{tot_due:,}",
            "node_label": "Installment",
            "color": NODE_TYPE_STYLES["schedule"]["color"],
            "size": NODE_TYPE_STYLES["schedule"]["size"],
            "details": {
                "Schedule Line": str(sch["sl"]),
                "Principal Due": f"₹{sch['prin']:,}",
                "Interest Due": f"₹{sch['int']:,}",
                "Total Scheduled Due": f"₹{tot_due:,}",
                "Scheduled Due Date": sch["date"]
            }
        })
        edges.append({
            "source": acnt_id,
            "target": sch_id,
            "label": "SCHEDULED_DUE",
            "purpose": "Planned Amortization"
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "selected_account": str(selected_account["acnt_num"]),
        "sample_accounts": sample_accounts,
        "metadata": {
            "is_live": is_live,
            "schema": "bronze",
            "total_nodes": len(nodes),
            "total_edges": len(edges)
        }
    }
