import os
import psycopg2
from typing import Dict, Any, List, Optional

COLUMN_MEANINGS = {
    "gnlnac_entity_num": "Entity/Branch Number",
    "gnlnac_acnt_num": "Account Number (PRIMARY KEY)",
    "gnlnac_cust_id": "Customer ID",
    "gnlnac_cust_name": "Customer / Borrower Name",
    "gnlnac_prod_code": "Product Code",
    "gnlnac_schm_code": "Scheme Code",
    "gnlnac_sanc_date": "Sanction/Approval Date",
    "gnlnac_sanc_amt": "Sanctioned Amount",
    "gnlnac_loan_type": "Loan Type",
    "gnlnac_ln_intrate": "Loan Interest Rate",
    "lnrepay_repay_date": "Repayment Date",
    "lnrepay_prin_pdamt": "Principal Paid Amount",
    "lnrepay_int_pdamt": "Interest Paid Amount",
    "genlndisb_disb_amt": "Disbursement Amount",
    "genlndisb_disb_date": "Disbursement Date",
}

# Refined Enterprise Hierarchy Node Styling
NODE_TYPE_STYLES = {
    "executive": {"color": "#4c1d95", "label": "MD & CEO / Executive Board", "size": 32}, # Deep Violet 900
    "zonal": {"color": "#6d28d9", "label": "Zonal Director (VP)", "size": 28},           # Purple 700
    "manager": {"color": "#4338ca", "label": "Branch Manager", "size": 24},             # Indigo 700
    "agent": {"color": "#0284c7", "label": "Loan Officer / Agent", "size": 20},         # Sky 600
    "customer": {"color": "#0f766e", "label": "Customer / Borrower", "size": 18},        # Teal 700
    "account": {"color": "#075fac", "label": "Loan Account Master", "size": 18},        # Moneypal Brand Blue
    "disbursement": {"color": "#ea580c", "label": "Payout Disbursement", "size": 14},   # Orange 600
    "repayment": {"color": "#10b981", "label": "Repayment Receipt", "size": 14},        # Emerald 500
}

# Enterprise Governance Structure
EXECUTIVE_INFO = {
    "id": "EXEC-001",
    "name": "Dr. Vikramaditya Rao",
    "role": "Managing Director & CEO",
    "org": "Moneypal GICC Holdings Ltd",
    "color": "#4c1d95"
}

ZONAL_DIRECTORS = [
    {
        "id": "ZONE-SOUTH",
        "name": "Kavita Menon",
        "role": "Zonal Vice President",
        "zone": "South India Zone (Karnataka, TN, Kerala)",
        "color": "#6d28d9"
    },
    {
        "id": "ZONE-WEST",
        "name": "Suresh Nair",
        "role": "Zonal Vice President",
        "zone": "West & Central Zone (Maharashtra, Gujarat)",
        "color": "#6d28d9"
    }
]

BRANCH_MANAGERS = [
    {
        "id": "MGR-101",
        "name": "Rajesh Sharma",
        "role": "Branch Operations Manager",
        "branch": "Bangalore Flagship Branch",
        "zone_id": "ZONE-SOUTH",
        "color": "#4338ca"
    },
    {
        "id": "MGR-102",
        "name": "Ananya Roy",
        "role": "Branch Credit Manager",
        "branch": "Chennai Regional Branch",
        "zone_id": "ZONE-SOUTH",
        "color": "#4338ca"
    },
    {
        "id": "MGR-103",
        "name": "Vikram Deshmukh",
        "role": "Branch Operations Manager",
        "branch": "Mumbai Commercial Branch",
        "zone_id": "ZONE-WEST",
        "color": "#4338ca"
    }
]

MOCK_AGENTS = [
    {
        "id": "AGENT-101",
        "name": "Priya Patel",
        "role": "Senior Credit Officer",
        "code": "AGT-PRIYA",
        "manager_id": "MGR-101",
        "color": "#0284c7"
    },
    {
        "id": "AGENT-102",
        "name": "Amit Verma",
        "role": "Field Relationship Manager",
        "code": "AGT-AMIT",
        "manager_id": "MGR-101",
        "color": "#0284c7"
    },
    {
        "id": "AGENT-103",
        "name": "Neha Singh",
        "role": "Micro-Lending Officer",
        "code": "AGT-NEHA",
        "manager_id": "MGR-102",
        "color": "#0284c7"
    }
]

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

def get_db_schema_graph(
    search_term: Optional[str] = None,
    view_level: Optional[str] = "executive",
    zonal_id: Optional[str] = None,
    manager_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    customer_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    5-Tier Enterprise Curiosity Graph Engine:
    - Level 0 ('executive'): MD & CEO -> Zonal Directors
    - Level 1 ('zonal'): Zonal Director -> Branch Managers
    - Level 2 ('manager'): Branch Manager -> Field Loan Officers
    - Level 3 ('agent'): Field Officer -> Assigned Customers
    - Level 4 ('customer'): Customer -> Loan Master Accounts, Payouts, Repayments
    """
    is_live = False
    nodes = []
    edges = []
    
    # Query live PostgreSQL accounts if available
    db_customers = []
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT gnlnac_cust_id, COALESCE(gnlnac_cust_name, 'Borrower #' || gnlnac_cust_id),
                   gnlnac_acnt_num, gnlnac_sanc_amt, gnlnac_loan_type, gnlnac_sanc_date
            FROM bronze.genlnacnts WHERE gnlnac_cust_id IS NOT NULL ORDER BY gnlnac_sanc_amt DESC LIMIT 30;
        """)
        rows = cur.fetchall()
        for r in rows:
            db_customers.append({
                "cust_id": str(r[0]),
                "cust_name": str(r[1]),
                "acnt_num": str(r[2]),
                "sanc_amt": float(r[3] or 0),
                "loan_type": str(r[4] or "Term Loan"),
                "sanc_date": str(r[5] or "2025-10-01")
            })
        conn.close()
        is_live = True
    except Exception as e:
        is_live = False

    # Fallback mock customers if offline
    if not db_customers:
        db_customers = [
            {"cust_id": "261", "cust_name": "SUVARNA J", "acnt_num": "1000100000045", "sanc_amt": 2000000, "loan_type": "Personal Loan", "sanc_date": "2025-11-12"},
            {"cust_id": "1398", "cust_name": "DEVENDRA KUMAR P", "acnt_num": "1000400000222", "sanc_amt": 1500000, "loan_type": "Commercial Loan", "sanc_date": "2025-09-10"},
            {"cust_id": "1395", "cust_name": "CHIDANANDA POOJARY", "acnt_num": "1000400000441", "sanc_amt": 1300000, "loan_type": "Working Capital", "sanc_date": "2025-10-05"},
            {"cust_id": "1229", "cust_name": "A KUMARA", "acnt_num": "1000400000319", "sanc_amt": 1300000, "loan_type": "Micro Loan", "sanc_date": "2025-08-14"},
            {"cust_id": "8779", "cust_name": "SUJATHA A", "acnt_num": "1000400003841", "sanc_amt": 1200000, "loan_type": "Asset Loan", "sanc_date": "2026-01-20"},
            {"cust_id": "5", "cust_name": "JAGADEESHA B", "acnt_num": "1000400001522", "sanc_amt": 1000000, "loan_type": "Term Loan", "sanc_date": "2025-12-01"}
        ]

    # Map customers to agents
    agent_customer_map = {agt["id"]: [] for agt in MOCK_AGENTS}
    for idx, c in enumerate(db_customers):
        assigned_agent_id = MOCK_AGENTS[idx % len(MOCK_AGENTS)]["id"]
        c["assigned_agent_id"] = assigned_agent_id
        agent_customer_map[assigned_agent_id].append(c)

    # Determine Active View Level
    current_level = view_level or "executive"
    selected_zonal = None
    selected_mgr = None
    selected_agent = None
    selected_customer = None

    # Handle Search override
    if search_term and search_term.strip():
        term = search_term.strip().lower()
        for z in ZONAL_DIRECTORS:
            if z["name"].lower() in term or z["zone"].lower() in term:
                current_level = "zonal"
                zonal_id = z["id"]
                break
        if current_level not in ["zonal"]:
            for m in BRANCH_MANAGERS:
                if m["name"].lower() in term or m["branch"].lower() in term:
                    current_level = "manager"
                    manager_id = m["id"]
                    zonal_id = m["zone_id"]
                    break
        if current_level not in ["zonal", "manager"]:
            for agt in MOCK_AGENTS:
                if agt["name"].lower() in term or agt["code"].lower() in term:
                    current_level = "agent"
                    agent_id = agt["id"]
                    manager_id = agt["manager_id"]
                    break
        if current_level not in ["zonal", "manager", "agent"]:
            for c in db_customers:
                if c["cust_name"].lower() in term or c["cust_id"] in term or c["acnt_num"] in term:
                    current_level = "customer"
                    customer_id = c["cust_id"]
                    agent_id = c["assigned_agent_id"]
                    break

    # -------------------------------------------------------------
    # LEVEL 0: EXECUTIVE VIEW (MD & CEO -> Zonal Directors)
    # -------------------------------------------------------------
    if current_level == "executive":
        nodes.append({
            "id": EXECUTIVE_INFO["id"],
            "type": "executive",
            "title": EXECUTIVE_INFO["name"],
            "subtitle": EXECUTIVE_INFO["role"],
            "node_label": "MD & CEO",
            "color": NODE_TYPE_STYLES["executive"]["color"],
            "size": NODE_TYPE_STYLES["executive"]["size"],
            "details": {
                "Executive Name": EXECUTIVE_INFO["name"],
                "Title": EXECUTIVE_INFO["role"],
                "Entity": EXECUTIVE_INFO["org"],
                "Zonal Divisions": f"{len(ZONAL_DIRECTORS)} Zones",
                "Branch Network": f"{len(BRANCH_MANAGERS)} Operating Branches",
                "Total Credit Portfolio": f"₹{sum(c['sanc_amt'] for c in db_customers):,}"
            }
        })

        for z in ZONAL_DIRECTORS:
            nodes.append({
                "id": z["id"],
                "type": "zonal",
                "title": z["name"],
                "subtitle": z["zone"],
                "node_label": "Zonal Director",
                "color": NODE_TYPE_STYLES["zonal"]["color"],
                "size": NODE_TYPE_STYLES["zonal"]["size"],
                "zonal_id": z["id"],
                "details": {
                    "Zonal Director": z["name"],
                    "Designation": z["role"],
                    "Jurisdiction": z["zone"],
                    "Managed Branches": f"{len([m for m in BRANCH_MANAGERS if m['zone_id'] == z['id']])} Branches"
                }
            })
            edges.append({
                "source": EXECUTIVE_INFO["id"],
                "target": z["id"],
                "weight": 9,
                "label": "GOVERNS_ZONE",
                "purpose": "Executive Jurisdiction"
            })

    # -------------------------------------------------------------
    # LEVEL 1: ZONAL VIEW (Zonal Director -> Branch Managers)
    # -------------------------------------------------------------
    elif current_level == "zonal" or (zonal_id and not manager_id and not agent_id and not customer_id):
        target_zonal_id = zonal_id or ZONAL_DIRECTORS[0]["id"]
        selected_zonal = next((z for z in ZONAL_DIRECTORS if z["id"] == target_zonal_id), ZONAL_DIRECTORS[0])

        nodes.append({
            "id": selected_zonal["id"],
            "type": "zonal",
            "title": selected_zonal["name"],
            "subtitle": selected_zonal["zone"],
            "node_label": "Zonal VP",
            "color": NODE_TYPE_STYLES["zonal"]["color"],
            "size": 28,
            "zonal_id": selected_zonal["id"],
            "details": {
                "Zonal Director": selected_zonal["name"],
                "Designation": selected_zonal["role"],
                "Jurisdiction": selected_zonal["zone"]
            }
        })

        assigned_mgrs = [m for m in BRANCH_MANAGERS if m["zone_id"] == selected_zonal["id"]]
        if not assigned_mgrs:
            assigned_mgrs = BRANCH_MANAGERS[:2]

        for m in assigned_mgrs:
            nodes.append({
                "id": m["id"],
                "type": "manager",
                "title": m["name"],
                "subtitle": m["branch"],
                "node_label": "Branch Manager",
                "color": NODE_TYPE_STYLES["manager"]["color"],
                "size": NODE_TYPE_STYLES["manager"]["size"],
                "manager_id": m["id"],
                "details": {
                    "Manager Name": m["name"],
                    "Role": m["role"],
                    "Branch Location": m["branch"]
                }
            })
            edges.append({
                "source": selected_zonal["id"],
                "target": m["id"],
                "weight": 8,
                "label": "MANAGES_BRANCH",
                "purpose": "Branch Operations Governance"
            })

    # -------------------------------------------------------------
    # LEVEL 2: MANAGER VIEW (Branch Manager -> Field Officers)
    # -------------------------------------------------------------
    elif current_level == "manager" or (manager_id and not agent_id and not customer_id):
        target_mgr_id = manager_id or BRANCH_MANAGERS[0]["id"]
        selected_mgr = next((m for m in BRANCH_MANAGERS if m["id"] == target_mgr_id), BRANCH_MANAGERS[0])
        selected_zonal = next((z for z in ZONAL_DIRECTORS if z["id"] == selected_mgr["zone_id"]), ZONAL_DIRECTORS[0])

        nodes.append({
            "id": selected_mgr["id"],
            "type": "manager",
            "title": selected_mgr["name"],
            "subtitle": selected_mgr["branch"],
            "node_label": "Branch Operations",
            "color": NODE_TYPE_STYLES["manager"]["color"],
            "size": 26,
            "manager_id": selected_mgr["id"],
            "details": {
                "Manager Name": selected_mgr["name"],
                "Branch": selected_mgr["branch"],
                "Zone": selected_zonal["name"]
            }
        })

        assigned_officers = [agt for agt in MOCK_AGENTS if agt["manager_id"] == selected_mgr["id"]]
        if not assigned_officers:
            assigned_officers = MOCK_AGENTS[:2]

        for agt in assigned_officers:
            assigned_c = agent_customer_map[agt["id"]]
            tot_vol = sum(c["sanc_amt"] for c in assigned_c)
            nodes.append({
                "id": agt["id"],
                "type": "agent",
                "title": agt["name"],
                "subtitle": f"{len(assigned_c)} Borrowers • ₹{tot_vol:,}",
                "node_label": "Field Officer",
                "color": NODE_TYPE_STYLES["agent"]["color"],
                "size": NODE_TYPE_STYLES["agent"]["size"],
                "agent_id": agt["id"],
                "details": {
                    "Officer Name": agt["name"],
                    "Officer Role": agt["role"],
                    "Officer Code": agt["code"],
                    "Assigned Borrowers": f"{len(assigned_c)} Customers",
                    "Active Volume": f"₹{tot_vol:,}"
                }
            })
            edges.append({
                "source": selected_mgr["id"],
                "target": agt["id"],
                "weight": 7,
                "label": "SUPERVISES_OFFICER",
                "purpose": "Field Supervision"
            })

    # -------------------------------------------------------------
    # LEVEL 3: AGENT VIEW (Field Officer -> Customers)
    # -------------------------------------------------------------
    elif current_level == "agent" or (agent_id and not customer_id):
        target_agent_id = agent_id or MOCK_AGENTS[0]["id"]
        selected_agent = next((a for a in MOCK_AGENTS if a["id"] == target_agent_id), MOCK_AGENTS[0])
        selected_mgr = next((m for m in BRANCH_MANAGERS if m["id"] == selected_agent["manager_id"]), BRANCH_MANAGERS[0])
        selected_zonal = next((z for z in ZONAL_DIRECTORS if z["id"] == selected_mgr["zone_id"]), ZONAL_DIRECTORS[0])

        nodes.append({
            "id": selected_agent["id"],
            "type": "agent",
            "title": selected_agent["name"],
            "subtitle": selected_agent["role"],
            "node_label": "Field Officer",
            "color": NODE_TYPE_STYLES["agent"]["color"],
            "size": 24,
            "agent_id": selected_agent["id"],
            "details": {
                "Officer Name": selected_agent["name"],
                "Role": selected_agent["role"],
                "Code": selected_agent["code"],
                "Branch": selected_mgr["branch"]
            }
        })

        assigned_customers = agent_customer_map[selected_agent["id"]]
        if not assigned_customers:
            assigned_customers = db_customers[:3]

        for c in assigned_customers:
            cust_node_id = f"CUST-{c['cust_id']}"
            nodes.append({
                "id": cust_node_id,
                "type": "customer",
                "title": c["cust_name"],
                "subtitle": f"Account #{c['acnt_num']} • ₹{c['sanc_amt']:,}",
                "node_label": "Borrower Profile",
                "color": NODE_TYPE_STYLES["customer"]["color"],
                "size": NODE_TYPE_STYLES["customer"]["size"],
                "customer_id": c["cust_id"],
                "details": {
                    "Customer Name": c["cust_name"],
                    "Customer ID": c["cust_id"],
                    "Assigned Officer": selected_agent["name"],
                    "Account Number": c["acnt_num"],
                    "Sanctioned Limit": f"₹{c['sanc_amt']:,}",
                    "Loan Product": c["loan_type"],
                    "Approval Date": c["sanc_date"]
                }
            })

            edges.append({
                "source": selected_agent["id"],
                "target": cust_node_id,
                "weight": 6,
                "label": "SERVICES_CUSTOMER",
                "purpose": "Field Account Servicing"
            })

    # -------------------------------------------------------------
    # LEVEL 4: CUSTOMER DETAIL VIEW (Customer -> Account, Payout, Repayment)
    # -------------------------------------------------------------
    elif current_level == "customer" or customer_id:
        target_cust = next((c for c in db_customers if c["cust_id"] == customer_id), db_customers[0])
        selected_customer = target_cust
        selected_agent = next((a for a in MOCK_AGENTS if a["id"] == target_cust["assigned_agent_id"]), MOCK_AGENTS[0])
        selected_mgr = next((m for m in BRANCH_MANAGERS if m["id"] == selected_agent["manager_id"]), BRANCH_MANAGERS[0])
        selected_zonal = next((z for z in ZONAL_DIRECTORS if z["id"] == selected_mgr["zone_id"]), ZONAL_DIRECTORS[0])

        cust_node_id = f"CUST-{target_cust['cust_id']}"
        nodes.append({
            "id": cust_node_id,
            "type": "customer",
            "title": target_cust["cust_name"],
            "subtitle": f"Customer ID: #{target_cust['cust_id']}",
            "node_label": "Borrower Profile",
            "color": NODE_TYPE_STYLES["customer"]["color"],
            "size": 24,
            "customer_id": target_cust["cust_id"],
            "details": {
                "Customer Name": target_cust["cust_name"],
                "Customer ID": str(target_cust["cust_id"]),
                "Assigned Officer": selected_agent["name"],
                "Branch": selected_mgr["branch"],
                "Risk Rating": "Grade A (Compliant)",
                "Total Sanction Limit": f"₹{target_cust['sanc_amt']:,}"
            }
        })

        acnt_node_id = f"ACNT-{target_cust['acnt_num']}"
        nodes.append({
            "id": acnt_node_id,
            "type": "account",
            "title": f"Account #{target_cust['acnt_num']}",
            "subtitle": f"Sanction: ₹{target_cust['sanc_amt']:,}",
            "node_label": "Loan Master",
            "color": NODE_TYPE_STYLES["account"]["color"],
            "size": 22,
            "details": {
                "Account Number": str(target_cust["acnt_num"]),
                "Borrower Name": target_cust["cust_name"],
                "Sanctioned Limit": f"₹{target_cust['sanc_amt']:,}",
                "Loan Product": target_cust["loan_type"],
                "Interest Rate": "12.5% p.a.",
                "Approval Date": target_cust["sanc_date"]
            }
        })

        edges.append({
            "source": cust_node_id,
            "target": acnt_node_id,
            "weight": 8,
            "label": "OWNS_ACCOUNT",
            "purpose": "Primary Loan Ownership"
        })

        disb_node_id = f"DISB-{target_cust['acnt_num']}-1"
        nodes.append({
            "id": disb_node_id,
            "type": "disbursement",
            "title": f"Disbursement: ₹{target_cust['sanc_amt']:,}",
            "subtitle": f"Date: {target_cust['sanc_date']}",
            "node_label": "Payout",
            "color": NODE_TYPE_STYLES["disbursement"]["color"],
            "size": 16,
            "details": {
                "Disbursement Payout": f"₹{target_cust['sanc_amt']:,}",
                "Date": target_cust["sanc_date"],
                "Payee": target_cust["cust_name"]
            }
        })
        edges.append({
            "source": acnt_node_id,
            "target": disb_node_id,
            "weight": 6,
            "label": "DISBURSED",
            "purpose": "Capital Payout"
        })

        repay_node_id = f"REPAY-{target_cust['acnt_num']}-1"
        repay_amt = round(target_cust['sanc_amt'] * 0.15)
        nodes.append({
            "id": repay_node_id,
            "type": "repayment",
            "title": f"Repayment: ₹{repay_amt:,}",
            "subtitle": "Last Receipt Paid",
            "node_label": "Credit Receipt",
            "color": NODE_TYPE_STYLES["repayment"]["color"],
            "size": 16,
            "details": {
                "Repayment Amount": f"₹{repay_amt:,}",
                "Posting Status": "Cleared / Verified"
            }
        })
        edges.append({
            "source": repay_node_id,
            "target": acnt_node_id,
            "weight": 6,
            "label": "PAID_REPAYMENT",
            "purpose": "Credit Receipt"
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "view_level": current_level,
        "executive_info": EXECUTIVE_INFO,
        "zonals": ZONAL_DIRECTORS,
        "selected_zonal": selected_zonal,
        "managers": BRANCH_MANAGERS,
        "selected_manager": selected_mgr,
        "agents": MOCK_AGENTS,
        "selected_agent": selected_agent,
        "selected_customer": selected_customer,
        "sample_customers": [
            {"cust_id": c["cust_id"], "cust_name": c["cust_name"], "acnt_num": c["acnt_num"], "amount": f"₹{c['sanc_amt']:,}"}
            for c in db_customers[:8]
        ],
        "metadata": {
            "is_live": is_live,
            "schema": "bronze",
            "total_nodes": len(nodes),
            "total_edges": len(edges)
        }
    }
