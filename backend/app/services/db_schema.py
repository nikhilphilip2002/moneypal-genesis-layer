import os
import psycopg2
from typing import Dict, Any, List

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
    "gnlnac_epi_pymt_day": "EPI Payment Day",
    "gnlnac_epi_wkly_day": "EPI Weekly Day",
    "gnlnac_epi_noi": "EPI Number of Installments",
    "gnlnac_holiday_noi": "Holiday Number of Installments",
    "gnlnac_repay_stdt": "Repayment Start Date",
    "gnlnac_repay_lastdt": "Repayment Last Date",
    "gnlnac_tot_accr_dec": "Total Accrual Declared",
    "gnlnac_tot_accr_amt": "Total Accrued Interest Amount",
    "gnlnac_last_accr_date": "Last Interest Accrual Date",
    "gnlnac_tot_post_amt": "Total Posted Amount",
    "gnlnac_last_post_date": "Last Posting Date",
    "gnlnac_lndisb_amt": "Loan Disbursement Amount",
    "gnlnac_pri_repay_amt": "Principal Repay Amount",
    "gnlnac_int_repay_amt": "Interest Repay Amount",
    "gnlnac_tot_chgs_appl": "Total Charges Applied",
    "gnlnac_tot_chgs_rcvd": "Total Charges Received",
    "gnlnac_first_disb_date": "First Disbursement Date",
    "gnlnac_last_disb_date": "Last Disbursement Date",
    "gnlnac_epi_amt": "EPI Amount",
    "gnlnac_last_pymt_date": "Last Payment Date",
    "gnlnac_last_fpymt_date": "Last Full Payment Date",
    "gnlnac_int_method": "Interest Method",
    "gnlnac_ln_intrate": "Loan Interest Rate",
    "gnlnac_from_slab_amt": "From Slab Amount",
    "gnlnac_upto_slab_amt": "Upto Slab Amount",
    "gnlnac_penal_intrate": "Penal Interest Rate",
    "gnlnac_fut_epi_recd": "Future EPIs Received",
    "gnlnac_fut_epi_adj": "Future EPIs Adjusted",
    "gnlnac_closure_date": "Account Closure Date",
    "gnlnac_cust_name": "Customer Name",
    "gnlnac_pldg_rel_date": "Pledge Release Date",
    "gnlnac_penal_post_amt": "Penal Posted Amount",
    "gnlnac_penal_post_date": "Penal Posting Date",
    "gnlnac_penal_repay_amt": "Penal Repay Amount",
    "gnlnac_intrim_post_amt": "Interim Posted Amount",

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
    "genlndisb_disb_cur": "Disbursement Currency",
    "genlndisb_disb_amt": "Disbursement Amount",
    "genlndisb_tot_chgs_amt": "Total Charges Amount",
    "genlndisb_net_pay_amt": "Net Payment Amount",
    "genlndisb_ept_inst_freq": "EPI Installment Frequency",
    "genlndisb_epi_wkly_day": "EPI Weekly Day",
    "genlndisb_epi_pymt_day": "EPI Payment Day",
    "genlndisb_epi_amt": "EMI/Payment Amount",
    "genlndisb_disb_to": "Disbursed To (Beneficiary/Self)",
    "genlndisb_agency_code": "Agency Code",
    "genlndisb_agen_acnt_sl": "Agency Account Serial Number",
    "genlndisb_cust_acnt_sl": "Customer Account Serial Number",
    "genlndisb_otp_seq_no": "OTP Sequence Number",
    "genlndisb_otp_source": "OTP Source",
    "genlndisb_admin_reason": "Administration Reason",
    "genlndisb_admin_remarks": "Administration Remarks",
    "post_tran_brn": "Posting Transaction Branch",
    "post_tran_date": "Posting Transaction Date",
    "post_tran_batch_num": "Posting Transaction Batch Number",
    "genlndisb_entd_by": "Entered By",
    "genlndisb_entd_on": "Entered On",
    "genlndisb_last_mod_by": "Last Modified By",
    "genlndisb_last_mod_on": "Last Modified On",
    "genlndisb_auth_by": "Authorized By",
    "genlndisb_auth_on": "Authorized On",
    "genlndisb_rej_by": "Rejected By",
    "genlndisb_rej_on": "Rejected On",
}

TABLE_INFO = {
    "genlnacnts": {
        "title": "GENLNACNTS",
        "label": "Master Loan Accounts",
        "purpose": "Core master registry containing details for every loan account, including sanctioned limits, interest rates, customer details, and accruals.",
        "color": "#075fac" # Moneypal primary brand color
    },
    "loanrepay": {
        "title": "LOANREPAY",
        "label": "Actual Repayments",
        "purpose": "Transaction ledger containing actual principal, interest, and penal interest repayments processed for each account.",
        "color": "#0f766e" # teal
    },
    "loanschedule": {
        "title": "LOANSCHEDULE",
        "label": "Planned Installments",
        "purpose": "Amortization schedule containing planned payment dates and principal/interest split allocations over the loan tenor.",
        "color": "#7c3aed" # purple
    },
    "genlndisb": {
        "title": "GENLNDISB",
        "label": "Loan Disbursements",
        "purpose": "Disbursement records showing actual payouts, bank transaction references, transaction charges, and beneficiary accounts.",
        "color": "#ea580c" # orange
    }
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

def get_db_schema_graph() -> Dict[str, Any]:
    """Inspects the postgres DB in the 'bronze' schema and returns an entity-relationship graph payload."""
    tables_list = ["genlnacnts", "loanrepay", "loanschedule", "genlndisb"]
    nodes = []
    edges = [
        {
            "source": "genlnacnts",
            "target": "loanrepay",
            "source_col": "gnlnac_acnt_num",
            "target_col": "lnrepay_acnt_no",
            "label": "gnlnac_acnt_num = lnrepay_acnt_no",
            "purpose": "Retrieve actual repayment logs for a loan account",
            "weight": 8
        },
        {
            "source": "genlnacnts",
            "target": "loanschedule",
            "source_col": "gnlnac_acnt_num",
            "target_col": "lnsched_acnt_no",
            "label": "gnlnac_acnt_num = lnsched_acnt_no",
            "purpose": "Look up planned payment schedule lines for an account",
            "weight": 8
        },
        {
            "source": "genlnacnts",
            "target": "genlndisb",
            "source_col": "gnlnac_acnt_num",
            "target_col": "genlndisb_acnt_num",
            "label": "gnlnac_acnt_num = genlndisb_acnt_num",
            "purpose": "Verify disbursement logs associated with a loan account",
            "weight": 8
        },
        {
            "source": "loanrepay",
            "target": "loanschedule",
            "source_col": "lnrepay_sl_no",
            "target_col": "lnsched_sl_no",
            "label": "lnrepay_acnt_no = lnsched_acnt_no AND lnrepay_sl_no = lnsched_sl_no",
            "purpose": "Match actual received repayments to planned schedule installments",
            "weight": 6
        }
    ]

    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        for table in tables_list:
            # Query row count
            cursor.execute(f"SELECT COUNT(*) FROM bronze.{table};")
            row_count = cursor.fetchone()[0]
            
            # Query columns
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = %s AND table_schema = 'bronze'
                ORDER BY ordinal_position;
            """, (table,))
            columns_data = cursor.fetchall()
            
            columns = []
            for col_name, data_type, is_nullable in columns_data:
                is_pk = (table == "genlnacnts" and col_name == "gnlnac_acnt_num")
                is_fk = (col_name in ["lnrepay_acnt_no", "lnsched_acnt_no", "genlndisb_acnt_num"])
                
                columns.append({
                    "name": col_name,
                    "type": data_type.upper(),
                    "meaning": COLUMN_MEANINGS.get(col_name, ""),
                    "required": is_pk or is_fk or (is_nullable == 'NO'),
                    "is_pk": is_pk,
                    "is_fk": is_fk
                })
            
            info = TABLE_INFO.get(table, {"title": table.upper(), "label": table, "purpose": "", "color": "#6b7280"})
            
            nodes.append({
                "id": table,
                "name": table,
                "title": info["title"],
                "label": info["label"],
                "purpose": info["purpose"],
                "color": info["color"],
                "row_count": row_count,
                "columns": columns
            })
            
        conn.close()
        is_live = True
        
    except Exception as e:
        # Graceful fallback: return mock data reflecting target schema
        is_live = False
        mock_counts = {
            "genlnacnts": 13510,
            "loanrepay": 13483,
            "loanschedule": 260437,
            "genlndisb": 5481
        }
        
        nodes = []
        for table in tables_list:
            row_count = mock_counts[table]
            info = TABLE_INFO.get(table, {"title": table.upper(), "label": table, "purpose": "", "color": "#6b7280"})
            
            columns = []
            # Synthesize columns from COLUMN_MEANINGS matching table prefix
            for col_name, meaning in COLUMN_MEANINGS.items():
                prefix = col_name.split("_")[0]
                belongs = False
                if table == "genlnacnts" and prefix in ["gnlnac", "post"]:
                    belongs = True
                elif table == "loanrepay" and prefix == "lnrepay":
                    belongs = True
                elif table == "loanschedule" and prefix == "lnsched":
                    belongs = True
                elif table == "genlndisb" and prefix in ["genlndisb", "post"]:
                    belongs = True
                    
                if belongs:
                    is_pk = (table == "genlnacnts" and col_name == "gnlnac_acnt_num")
                    is_fk = (col_name in ["lnrepay_acnt_no", "lnsched_acnt_no", "genlndisb_acnt_num"])
                    
                    columns.append({
                        "name": col_name,
                        "type": "BIGINT" if is_pk or is_fk else "VARCHAR" if "name" in col_name or "code" in col_name else "DATE" if "date" in col_name or "dt" in col_name else "NUMERIC",
                        "meaning": meaning,
                        "required": is_pk or is_fk,
                        "is_pk": is_pk,
                        "is_fk": is_fk
                    })
            
            nodes.append({
                "id": table,
                "name": table,
                "title": info["title"],
                "label": info["label"],
                "purpose": info["purpose"],
                "color": info["color"],
                "row_count": row_count,
                "columns": columns
            })
            
    curiosity_score = sum(node["row_count"] for node in nodes)
    
    return {
        "nodes": nodes,
        "edges": edges,
        "curiosity_score": curiosity_score,
        "metadata": {
            "is_live": is_live,
            "schema": "bronze",
            "total_tables": len(nodes),
            "total_relations": len(edges),
            "total_rows": curiosity_score
        }
    }
