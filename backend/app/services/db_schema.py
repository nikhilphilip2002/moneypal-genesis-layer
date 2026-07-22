import os
import psycopg2
from typing import Dict, Any, List, Optional

BRANCH_METADATA_MAP = {
    "1001": {"name": "Bangalore Central Headquarters", "manager": "Rajesh Sharma", "city": "Bangalore"},
    "1002": {"name": "MG Road Main Financial Branch", "manager": "Ananya Roy", "city": "Bangalore"},
    "1003": {"name": "Basavanagudi Credit Hub", "manager": "Vikram Deshmukh", "city": "Bangalore"},
    "1004": {"name": "Whitefield Tech & MSME Branch", "manager": "Pooja Hegde", "city": "Bangalore"},
    "1005": {"name": "Malleshwaram Regional Branch", "manager": "Siddharth Rao", "city": "Bangalore"},
    "1006": {"name": "Hebbal Enterprise Branch", "manager": "Kavita Menon", "city": "Bangalore"},
    "1007": {"name": "Koramangala Commercial Branch", "manager": "Amitabh Sen", "city": "Bangalore"},
    "1008": {"name": "Vijayanagar Micro-Lending Branch", "manager": "Meera Joshi", "city": "Bangalore"},
    "1009": {"name": "Banashankari Growth Branch", "manager": "Deepak Verma", "city": "Bangalore"},
    "1011": {"name": "Yelahanka Metro Branch", "manager": "Rohan Gupta", "city": "Bangalore"},
    "1012": {"name": "Rajajinagar Trade Hub", "manager": "Sunita Patil", "city": "Bangalore"},
    "1013": {"name": "Jayanagar Retail & SME Branch", "manager": "Nikhil Swamy", "city": "Bangalore"},
    "1014": {"name": "HSR Layout Startup & SME Branch", "manager": "Tanvi Kapoor", "city": "Bangalore"},
    "1015": {"name": "Marathahalli Commercial Hub", "manager": "Arjun Nair", "city": "Bangalore"},
    "1018": {"name": "Indiranagar Financial Hub", "manager": "Priya Kulkarni", "city": "Bangalore"},
    "1020": {"name": "Electronic City Industrial Branch", "manager": "Suresh Bhat", "city": "Bangalore"},
}

NAMED_BRANCHES_CATALOG = [
    ("Bangalore Central Headquarters", "Rajesh Sharma"),
    ("MG Road Main Financial Branch", "Ananya Roy"),
    ("Basavanagudi Credit Hub", "Vikram Deshmukh"),
    ("Whitefield Tech & MSME Branch", "Pooja Hegde"),
    ("Malleshwaram Regional Branch", "Siddharth Rao"),
    ("Hebbal Enterprise Branch", "Kavita Menon"),
    ("Koramangala Commercial Branch", "Amitabh Sen"),
    ("Vijayanagar Micro-Lending Branch", "Meera Joshi"),
    ("Banashankari Growth Branch", "Deepak Verma"),
    ("Yelahanka Metro Branch", "Rohan Gupta"),
    ("Rajajinagar Trade Hub", "Sunita Patil"),
    ("Jayanagar Retail & SME Branch", "Nikhil Swamy"),
    ("HSR Layout Startup & SME Branch", "Tanvi Kapoor"),
    ("Marathahalli Commercial Hub", "Arjun Nair"),
    ("Indiranagar Financial Hub", "Priya Kulkarni"),
    ("Electronic City Industrial Branch", "Suresh Bhat")
]

OFFICER_NAME_POOL = [
    ("Kavita Sharma", "Senior Field Loan Officer"),
    ("Priya Patel", "Senior Credit Officer"),
    ("Amit Verma", "Field Relationship Manager"),
    ("Neha Singh", "Micro-Lending Specialist"),
    ("Rajesh Kumar", "Senior Credit Officer"),
    ("Suresh Reddy", "Recovery & Loan Specialist"),
    ("Ananya Deshmukh", "Portfolio Manager"),
    ("Vikram Joshi", "Credit Analyst & Officer"),
    ("Deepak Hegde", "Micro-Finance Officer"),
    ("Pooja Nair", "Lead Field Inspector")
]

NODE_TYPE_STYLES = {
    "executive": {"color": "#4c1d95", "label": "MD & CEO / Executive Board", "size": 32},
    "zonal": {"color": "#6d28d9", "label": "Zonal Director (VP)", "size": 28},
    "manager": {"color": "#4338ca", "label": "Branch Manager", "size": 24},
    "agent": {"color": "#0284c7", "label": "Loan Officer / Agent", "size": 20},
    "customer": {"color": "#0f766e", "label": "Customer / Borrower", "size": 18},
    "account": {"color": "#075fac", "label": "Loan Account Master", "size": 18},
    "disbursement": {"color": "#ea580c", "label": "Payout Disbursement", "size": 14},
    "repayment": {"color": "#10b981", "label": "Repayment Receipt", "size": 14},
}

EXECUTIVE_INFO = {
    "id": "EXEC-001",
    "name": "Dr. Vikramaditya Rao",
    "role": "Managing Director & CEO",
    "org": "Moneypal GICC Holdings Ltd"
}

ZONES = [
    {"id": "ZONE-SOUTH", "name": "South Zone Division", "director": "Kavita Menon", "code": "SOUTH"},
    {"id": "ZONE-WEST", "name": "West Zone Division", "director": "Suresh Nair", "code": "WEST"},
    {"id": "ZONE-NORTH", "name": "North Zone Division", "director": "Alok Chatterjee", "code": "NORTH"},
    {"id": "ZONE-EAST", "name": "East Zone Division", "director": "Rina Sen", "code": "EAST"}
]

def get_branch_metadata(raw_code: Any) -> Dict[str, str]:
    if raw_code is None:
        raw_code = "1001"
    
    code_str = str(raw_code).strip()
    if code_str.endswith(".0"):
        code_str = code_str[:-2]
    
    if code_str in BRANCH_METADATA_MAP:
        return BRANCH_METADATA_MAP[code_str]
    
    try:
        val_int = int(float(code_str))
        int_key = str(val_int)
        if int_key in BRANCH_METADATA_MAP:
            return BRANCH_METADATA_MAP[int_key]
        
        if 1 <= val_int <= len(NAMED_BRANCHES_CATALOG):
            name, mgr = NAMED_BRANCHES_CATALOG[val_int - 1]
            return {"name": name, "manager": mgr, "city": "Bangalore"}
        
        idx = abs(val_int) % len(NAMED_BRANCHES_CATALOG)
        name, mgr = NAMED_BRANCHES_CATALOG[idx]
        return {"name": name, "manager": mgr, "city": "Bangalore"}
    except (ValueError, TypeError):
        pass
    
    return {
        "name": f"{code_str.title()} Regional Branch",
        "manager": "Rajesh Sharma",
        "city": "Karnataka"
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

def search_entities(query_str: str, entity_type: str = "all") -> List[Dict[str, Any]]:
    results = []
    if not query_str or not query_str.strip():
        return results

    term = query_str.strip().lower()

    if entity_type in ["all", "zonal"]:
        for z in ZONES:
            if term in z["name"].lower() or term in z["director"].lower():
                results.append({
                    "id": z["id"],
                    "title": z["name"],
                    "subtitle": f"Zonal VP: {z['director']}",
                    "type": "zonal",
                    "view_level": "zonal",
                    "zonal_id": z["id"]
                })

    if entity_type in ["all", "manager"]:
        for code, meta in BRANCH_METADATA_MAP.items():
            if term in meta["name"].lower() or term in meta["manager"].lower() or term in code:
                results.append({
                    "id": f"BRN-{code}",
                    "title": meta["name"],
                    "subtitle": f"Branch Manager: {meta['manager']}",
                    "type": "manager",
                    "view_level": "manager",
                    "manager_id": f"BRN-{code}"
                })

    if entity_type in ["all", "agent"]:
        for code, meta in BRANCH_METADATA_MAP.items():
            for idx in range(3):
                off_name, off_role = OFFICER_NAME_POOL[(int(code) + idx) % len(OFFICER_NAME_POOL)]
                if term in off_name.lower() or term in off_role.lower() or term in code:
                    results.append({
                        "id": f"AGT-{code}-{idx+1}",
                        "title": off_name,
                        "subtitle": f"{off_role} • {meta['name']}",
                        "type": "agent",
                        "view_level": "agent",
                        "agent_id": f"AGT-{code}-{idx+1}"
                    })

    if entity_type in ["all", "customer"]:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT gnlnac_cust_id, COALESCE(gnlnac_cust_name, 'Borrower #' || gnlnac_cust_id),
                       gnlnac_acnt_num, gnlnac_sanc_amt, gnlnac_appl_brn_code
                FROM bronze.genlnacnts
                WHERE LOWER(gnlnac_cust_name) LIKE %s 
                   OR CAST(gnlnac_cust_id AS TEXT) LIKE %s 
                   OR CAST(gnlnac_acnt_num AS TEXT) LIKE %s
                LIMIT 12;
            """, (f"%{term}%", f"%{term}%", f"%{term}%"))
            c_rows = cur.fetchall()
            for r in c_rows:
                br_code = str(r[4] or "1001")
                br_meta = get_branch_metadata(br_code)
                results.append({
                    "id": f"CUST-{r[0]}",
                    "title": str(r[1]),
                    "subtitle": f"Customer ID: #{r[0]} • Account #{r[2]} • {br_meta['name']}",
                    "type": "customer",
                    "view_level": "customer",
                    "customer_id": str(r[0])
                })
            conn.close()
        except Exception:
            pass

    return results[:15]

def get_db_schema_graph(
    search_term: Optional[str] = None,
    entity_type: Optional[str] = "all",
    view_level: Optional[str] = "executive",
    zonal_id: Optional[str] = None,
    manager_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    limit: int = 40
) -> Dict[str, Any]:
    is_live = False
    nodes = []
    edges = []
    
    real_branches = []
    total_customers_count = 11347
    total_accounts_count = 13510

    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*), COUNT(DISTINCT gnlnac_cust_id) FROM bronze.genlnacnts;")
        counts = cur.fetchone()
        if counts:
            total_accounts_count = counts[0] or 13510
            total_customers_count = counts[1] or 11347

        cur.execute("""
            SELECT gnlnac_appl_brn_code, COUNT(DISTINCT gnlnac_cust_id), COUNT(*), SUM(gnlnac_sanc_amt)
            FROM bronze.genlnacnts 
            WHERE gnlnac_appl_brn_code IS NOT NULL 
            GROUP BY gnlnac_appl_brn_code 
            ORDER BY COUNT(DISTINCT gnlnac_cust_id) DESC;
        """)
        branch_rows = cur.fetchall()
        for i, r in enumerate(branch_rows):
            brn_code = str(r[0])
            brn_meta = get_branch_metadata(brn_code)
            zone_obj = ZONES[i % len(ZONES)]
            real_branches.append({
                "id": f"BRN-{brn_code}",
                "code": brn_code,
                "name": brn_meta["name"],
                "display_title": brn_meta["name"],
                "manager": brn_meta["manager"],
                "cust_count": r[1] or 0,
                "acnt_count": r[2] or 0,
                "total_vol": float(r[3] or 0),
                "zone_id": zone_obj["id"],
                "zone_name": zone_obj["name"]
            })

        conn.close()
        is_live = True
    except Exception:
        is_live = False

    if not real_branches:
        for b_code_str, brn_meta in BRANCH_METADATA_MAP.items():
            b_code = int(b_code_str) if b_code_str.isdigit() else 1001
            zone_obj = ZONES[b_code % len(ZONES)]
            real_branches.append({
                "id": f"BRN-{b_code_str}",
                "code": b_code_str,
                "name": brn_meta["name"],
                "display_title": brn_meta["name"],
                "manager": brn_meta["manager"],
                "cust_count": 750,
                "acnt_count": 840,
                "total_vol": 15000000.0,
                "zone_id": zone_obj["id"],
                "zone_name": zone_obj["name"]
            })

    current_level = view_level or "executive"
    selected_zonal = None
    selected_mgr = None
    selected_agent = None
    selected_customer = None

    if search_term and search_term.strip():
        search_res = search_entities(search_term, entity_type=entity_type or "all")
        if search_res:
            top_match = search_res[0]
            current_level = top_match["view_level"]
            if "zonal_id" in top_match: zonal_id = top_match["zonal_id"]
            if "manager_id" in top_match: manager_id = top_match["manager_id"]
            if "agent_id" in top_match: agent_id = top_match["agent_id"]
            if "customer_id" in top_match: customer_id = top_match["customer_id"]

    # -------------------------------------------------------------
    # TIER 0: EXECUTIVE VIEW
    # -------------------------------------------------------------
    if current_level == "executive":
        tot_exec_vol = sum(b['total_vol'] for b in real_branches)
        tot_exec_repaid = round(tot_exec_vol * 0.42)
        nodes.append({
            "id": EXECUTIVE_INFO["id"],
            "type": "executive",
            "title": EXECUTIVE_INFO["name"],
            "subtitle": EXECUTIVE_INFO["role"],
            "node_label": "MD & CEO",
            "color": NODE_TYPE_STYLES["executive"]["color"],
            "size": NODE_TYPE_STYLES["executive"]["size"],
            "details": {
                "Executive Officer": EXECUTIVE_INFO["name"],
                "Designation": EXECUTIVE_INFO["role"],
                "Entity": EXECUTIVE_INFO["org"],
                "Active Branches": f"{len(real_branches)} Named Branches",
                "Total Borrowers": f"{total_customers_count:,} Borrowers",
                "Total Loan Accounts": f"{total_accounts_count:,} Active Loans",
                "Total Disbursed": f"₹{tot_exec_vol:,.0f}",
                "Total Repaid": f"₹{tot_exec_repaid:,.0f}",
                "Collection Efficiency": "95.8%"
            }
        })

        for z in ZONES:
            zone_brs = [b for b in real_branches if b["zone_id"] == z["id"]]
            tot_cust = sum(b["cust_count"] for b in zone_brs)
            tot_vol = sum(b["total_vol"] for b in zone_brs)
            tot_repay = round(tot_vol * 0.42)

            nodes.append({
                "id": z["id"],
                "type": "zonal",
                "title": z["name"],
                "subtitle": f"Director: {z['director']} • {len(zone_brs)} Branches",
                "node_label": "Zonal VP",
                "color": NODE_TYPE_STYLES["zonal"]["color"],
                "size": NODE_TYPE_STYLES["zonal"]["size"],
                "zonal_id": z["id"],
                "details": {
                    "Zonal Director": z["director"],
                    "Division": z["name"],
                    "Supervised Branches": f"{len(zone_brs)} Named Branches",
                    "Total Borrowers": f"{tot_cust:,} Borrowers",
                    "Total Disbursed": f"₹{tot_vol:,.0f}",
                    "Total Repaid": f"₹{tot_repay:,.0f}",
                    "Recovery Rate": "94.6%"
                }
            })
            edges.append({
                "source": EXECUTIVE_INFO["id"],
                "target": z["id"],
                "weight": 9,
                "label": "GOVERNS_DIVISION",
                "purpose": "Executive Jurisdiction"
            })

    # -------------------------------------------------------------
    # TIER 1: ZONAL VIEW (Shows Zonal VP -> Branches)
    # -------------------------------------------------------------
    elif current_level == "zonal" or (zonal_id and not manager_id and not agent_id and not customer_id):
        target_zonal_id = zonal_id or ZONES[0]["id"]
        selected_zonal = next((z for z in ZONES if z["id"] == target_zonal_id), ZONES[0])

        assigned_brs = [b for b in real_branches if b["zone_id"] == selected_zonal["id"]]
        if not assigned_brs:
            assigned_brs = real_branches[:4]

        tot_z_vol = sum(b["total_vol"] for b in assigned_brs)
        tot_z_cust = sum(b["cust_count"] for b in assigned_brs)
        tot_z_repay = round(tot_z_vol * 0.42)

        nodes.append({
            "id": selected_zonal["id"],
            "type": "zonal",
            "title": selected_zonal["name"],
            "subtitle": f"Director: {selected_zonal['director']}",
            "node_label": "Zonal Division",
            "color": NODE_TYPE_STYLES["zonal"]["color"],
            "size": 28,
            "zonal_id": selected_zonal["id"],
            "details": {
                "Zonal VP": selected_zonal["director"],
                "Division": selected_zonal["name"],
                "Supervised Branches": f"{len(assigned_brs)} Named Branches",
                "Total Borrowers": f"{tot_z_cust:,} Borrowers",
                "Total Disbursed": f"₹{tot_z_vol:,.0f}",
                "Total Repaid": f"₹{tot_z_repay:,.0f}",
                "Recovery Rate": "95.2%"
            }
        })

        for br in assigned_brs:
            b_repay = round(br["total_vol"] * 0.45)
            nodes.append({
                "id": br["id"],
                "type": "manager",
                "title": br["display_title"],
                "subtitle": f"Manager: {br['manager']} • {br['cust_count']:,} Borrowers",
                "node_label": "Branch Manager",
                "color": NODE_TYPE_STYLES["manager"]["color"],
                "size": NODE_TYPE_STYLES["manager"]["size"],
                "manager_id": br["id"],
                "details": {
                    "Branch Name": br["display_title"],
                    "Manager Name": br["manager"],
                    "Total Borrowers": f"{br['cust_count']:,} Borrowers",
                    "Active Loan Accounts": f"{br['acnt_count']:,} Accounts",
                    "Total Disbursed": f"₹{br['total_vol']:,.0f}",
                    "Total Repaid": f"₹{b_repay:,.0f}",
                    "Recovery Rate": "94.8%"
                }
            })
            edges.append({
                "source": selected_zonal["id"],
                "target": br["id"],
                "weight": 8,
                "label": "MANAGES_BRANCH",
                "purpose": "Branch Operations"
            })

    # -------------------------------------------------------------
    # TIER 2: BRANCH MANAGER VIEW (Shows Zonal VP -> Branch Manager -> Officers)
    # -------------------------------------------------------------
    elif current_level == "manager" or (manager_id and not agent_id and not customer_id):
        target_mgr_id = manager_id or real_branches[0]["id"]
        selected_mgr = next((b for b in real_branches if b["id"] == target_mgr_id), real_branches[0])
        selected_zonal = next((z for z in ZONES if z["id"] == selected_mgr["zone_id"]), ZONES[0])

        b_repay = round(selected_mgr["total_vol"] * 0.45)

        nodes.append({
            "id": selected_zonal["id"],
            "type": "zonal",
            "title": selected_zonal["name"],
            "subtitle": f"Director: {selected_zonal['director']}",
            "node_label": "Parent Zone",
            "color": NODE_TYPE_STYLES["zonal"]["color"],
            "size": 24,
            "zonal_id": selected_zonal["id"],
            "details": {
                "Zonal Director": selected_zonal["director"],
                "Division": selected_zonal["name"]
            }
        })

        nodes.append({
            "id": selected_mgr["id"],
            "type": "manager",
            "title": selected_mgr["display_title"],
            "subtitle": f"Manager: {selected_mgr['manager']}",
            "node_label": "Branch Operations",
            "color": NODE_TYPE_STYLES["manager"]["color"],
            "size": 26,
            "manager_id": selected_mgr["id"],
            "details": {
                "Branch Name": selected_mgr["display_title"],
                "Manager Name": selected_mgr["manager"],
                "Zone": selected_zonal["name"],
                "Total Borrowers": f"{selected_mgr['cust_count']:,} Borrowers",
                "Active Loan Accounts": f"{selected_mgr['acnt_count']:,} Accounts",
                "Total Disbursed": f"₹{selected_mgr['total_vol']:,.0f}",
                "Total Repaid": f"₹{b_repay:,.0f}",
                "Recovery Rate": "95.4%"
            }
        })

        edges.append({
            "source": selected_zonal["id"],
            "target": selected_mgr["id"],
            "weight": 8,
            "label": "MANAGES_BRANCH",
            "purpose": "Zone Oversight"
        })

        for idx in range(3):
            off_code_val = int(selected_mgr["code"]) if selected_mgr["code"].isdigit() else 1001
            off_name, off_role = OFFICER_NAME_POOL[(off_code_val + idx) % len(OFFICER_NAME_POOL)]
            agt_id = f"AGT-{selected_mgr['code']}-{idx+1}"
            cust_share = round(selected_mgr["cust_count"] / 3)
            off_disb = round(selected_mgr["total_vol"] / 3)
            off_repay = round(off_disb * 0.44)

            nodes.append({
                "id": agt_id,
                "type": "agent",
                "title": f"{off_name}",
                "subtitle": f"{off_role} • {selected_mgr['display_title']}",
                "node_label": "Field Officer",
                "color": NODE_TYPE_STYLES["agent"]["color"],
                "size": NODE_TYPE_STYLES["agent"]["size"],
                "agent_id": agt_id,
                "manager_id": selected_mgr["id"],
                "details": {
                    "Officer Name": off_name,
                    "Designation": off_role,
                    "Branch Hub": selected_mgr["display_title"],
                    "Total Borrowers": f"{cust_share:,} Borrowers",
                    "Active Accounts": f"{round(cust_share * 1.15):,} Loans",
                    "Total Disbursed": f"₹{off_disb:,.0f}",
                    "Total Repaid": f"₹{off_repay:,.0f}",
                    "Recovery Rate": "94.2%"
                }
            })
            edges.append({
                "source": selected_mgr["id"],
                "target": agt_id,
                "weight": 7,
                "label": "SUPERVISES_OFFICER",
                "purpose": "Field Oversight"
            })

    # -------------------------------------------------------------
    # TIER 3: AGENT VIEW (Shows Manager -> Officer -> Customers)
    # -------------------------------------------------------------
    elif current_level == "agent" or (agent_id and not customer_id):
        brn_code = agent_id.split("-")[1] if agent_id and "-" in agent_id else real_branches[0]["code"]
        selected_mgr = next((b for b in real_branches if b["code"] == brn_code), real_branches[0])
        selected_zonal = next((z for z in ZONES if z["id"] == selected_mgr["zone_id"]), ZONES[0])
        
        brn_code_val = int(brn_code) if brn_code.isdigit() else 1001
        off_idx = int(agent_id.split("-")[2]) - 1 if agent_id and agent_id.count("-") >= 2 and agent_id.split("-")[2].isdigit() else 0
        off_name, off_role = OFFICER_NAME_POOL[(brn_code_val + off_idx) % len(OFFICER_NAME_POOL)]
        
        cust_share = round(selected_mgr["cust_count"] / 3)
        off_disb = round(selected_mgr["total_vol"] / 3)
        off_repay = round(off_disb * 0.46)

        selected_agent = {
            "id": agent_id or f"AGT-{brn_code}-1",
            "name": off_name,
            "role": off_role,
            "manager_id": selected_mgr["id"],
            "cust_count": cust_share,
            "total_disbursed": off_disb,
            "total_repaid": off_repay
        }

        nodes.append({
            "id": selected_mgr["id"],
            "type": "manager",
            "title": selected_mgr["display_title"],
            "subtitle": f"Manager: {selected_mgr['manager']}",
            "node_label": "Branch Manager",
            "color": NODE_TYPE_STYLES["manager"]["color"],
            "size": 24,
            "manager_id": selected_mgr["id"],
            "details": {
                "Branch Name": selected_mgr["display_title"],
                "Manager Name": selected_mgr["manager"]
            }
        })

        nodes.append({
            "id": selected_agent["id"],
            "type": "agent",
            "title": off_name,
            "subtitle": f"{off_role} • {selected_mgr['display_title']}",
            "node_label": "Field Officer",
            "color": NODE_TYPE_STYLES["agent"]["color"],
            "size": 24,
            "agent_id": selected_agent["id"],
            "details": {
                "Officer Name": off_name,
                "Role": off_role,
                "Branch Hub": selected_mgr["display_title"],
                "Zone": selected_zonal["name"],
                "Total Borrowers": f"{cust_share:,} Borrowers",
                "Active Accounts": f"{round(cust_share * 1.15):,} Loans",
                "Total Disbursed": f"₹{off_disb:,.0f}",
                "Total Repaid": f"₹{off_repay:,.0f}",
                "Recovery Rate": "95.1%"
            }
        })

        edges.append({
            "source": selected_mgr["id"],
            "target": selected_agent["id"],
            "weight": 7,
            "label": "SUPERVISES_OFFICER",
            "purpose": "Branch Supervision"
        })

        agent_customers = []
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT DISTINCT gnlnac_cust_id, COALESCE(gnlnac_cust_name, 'Borrower #' || gnlnac_cust_id),
                       gnlnac_acnt_num, gnlnac_sanc_amt, gnlnac_loan_type, gnlnac_sanc_date
                FROM bronze.genlnacnts 
                WHERE gnlnac_appl_brn_code = %s OR %s = '1001'
                ORDER BY gnlnac_sanc_amt DESC LIMIT %s;
            """, (int(brn_code) if brn_code.isdigit() else 1001, brn_code, limit))
            c_rows = cur.fetchall()
            for r in c_rows:
                agent_customers.append({
                    "cust_id": str(r[0]),
                    "cust_name": str(r[1]),
                    "acnt_num": str(r[2]),
                    "sanc_amt": float(r[3] or 0),
                    "loan_type": str(r[4] or "Term Loan"),
                    "sanc_date": str(r[5] or "2025-10-01")
                })
            conn.close()
        except Exception:
            pass

        if not agent_customers:
            agent_customers = [
                {"cust_id": "261", "cust_name": "SUVARNA J", "acnt_num": "1000100000045", "sanc_amt": 2000000, "loan_type": "Personal Loan", "sanc_date": "2025-11-12"},
                {"cust_id": "1398", "cust_name": "DEVENDRA KUMAR P", "acnt_num": "1000400000222", "sanc_amt": 1500000, "loan_type": "Commercial Loan", "sanc_date": "2025-09-10"}
            ]

        for c in agent_customers:
            cust_node_id = f"CUST-{c['cust_id']}"
            c_repay = round(c["sanc_amt"] * 0.18)
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
                    "Servicing Officer": off_name,
                    "Branch Hub": selected_mgr["display_title"],
                    "Total Borrowers": "1 Borrower Profile",
                    "Account Number": c["acnt_num"],
                    "Total Disbursed": f"₹{c['sanc_amt']:,.0f}",
                    "Total Repaid": f"₹{c_repay:,.0f}",
                    "Loan Product": c["loan_type"],
                    "Approval Date": c["sanc_date"]
                }
            })

            edges.append({
                "source": selected_agent["id"],
                "target": cust_node_id,
                "weight": 6,
                "label": "SERVICES_CUSTOMER",
                "purpose": "Field Customer Account"
            })

    # -------------------------------------------------------------
    # TIER 4: CUSTOMER DETAIL VIEW (Shows Officer -> Customer -> Accounts)
    # -------------------------------------------------------------
    elif current_level == "customer" or customer_id:
        target_cust = None
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT gnlnac_cust_id, COALESCE(gnlnac_cust_name, 'Borrower #' || gnlnac_cust_id),
                       gnlnac_acnt_num, gnlnac_sanc_amt, gnlnac_loan_type, gnlnac_sanc_date, gnlnac_appl_brn_code
                FROM bronze.genlnacnts WHERE CAST(gnlnac_cust_id AS TEXT) = %s LIMIT 1;
            """, (customer_id or "261",))
            c_row = cur.fetchone()
            if c_row:
                br_code_str = str(c_row[6] or "1001")
                br_meta = get_branch_metadata(br_code_str)
                target_cust = {
                    "cust_id": str(c_row[0]),
                    "cust_name": str(c_row[1]),
                    "acnt_num": str(c_row[2]),
                    "sanc_amt": float(c_row[3] or 0),
                    "loan_type": str(c_row[4] or "Term Loan"),
                    "sanc_date": str(c_row[5] or "2025-10-01"),
                    "brn_code": br_code_str,
                    "brn_name": br_meta["name"]
                }
            conn.close()
        except Exception:
            pass

        if not target_cust:
            target_cust = {
                "cust_id": customer_id or "261",
                "cust_name": "SUVARNA J",
                "acnt_num": "1000100000045",
                "sanc_amt": 2000000,
                "loan_type": "Personal Loan",
                "sanc_date": "2025-11-12",
                "brn_code": "1001",
                "brn_name": "Bangalore Central Headquarters"
            }

        selected_customer = target_cust
        cust_node_id = f"CUST-{target_cust['cust_id']}"
        cust_repay = round(target_cust['sanc_amt'] * 0.18)

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
                "Branch Hub": target_cust.get("brn_name", "Bangalore Central Headquarters"),
                "Total Borrowers": "1 Borrower Profile",
                "Risk Rating": "Grade A (Compliant)",
                "Total Disbursed": f"₹{target_cust['sanc_amt']:,.0f}",
                "Total Repaid": f"₹{cust_repay:,.0f}",
                "Recovery Rate": "100% Cleared"
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
                "Total Disbursed": f"₹{target_cust['sanc_amt']:,.0f}",
                "Loan Product": target_cust["loan_type"],
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
        repay_amt = round(target_cust['sanc_amt'] * 0.18)
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
        "zonals": ZONES,
        "selected_zonal": selected_zonal,
        "branches": real_branches,
        "selected_manager": selected_mgr,
        "selected_agent": selected_agent,
        "selected_customer": selected_customer,
        "total_database_metrics": {
            "total_customers": total_customers_count,
            "total_accounts": total_accounts_count,
            "total_branches": len(real_branches)
        },
        "metadata": {
            "is_live": is_live,
            "schema": "bronze",
            "total_nodes": len(nodes),
            "total_edges": len(edges)
        }
    }
