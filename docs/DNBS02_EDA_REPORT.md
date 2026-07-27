# DNBS-02 Source Data EDA

**Database:** `moneypaldb` @ `192.168.1.183:5432` (PostgreSQL 16.13)
**Date of analysis:** 2026-07-27
**Purpose:** Establish which RBI DNBS-02 return fields are genuinely derivable from the
warehouse, and which are currently fabricated by `backend/app/services/dnbs02_service.py`.

> **Headline:** the live database is real and rich, but the generator queries the wrong
> tables. Three of its nine queries reference objects that **do not exist**, and the three
> largest sections of the return (Parts 1, 3, 6) are never queried at all. Meanwhile a
> purpose-built month-end snapshot table (`bronze.genln_rpt_day`) and a full GL trial
> balance (`bronze.glbbal` + `bronze.extgl`) sit unused and contain most of what the
> return actually needs.

---

## 1. Schema inventory

Three schemas. `silver` is a 1:1 renamed mirror of `bronze` (identical row counts on every
table), so either layer can be used; `silver` names are self-documenting and preferable.

| Table (bronze) | Silver equivalent | Rows | Relevance to DNBS-02 |
|---|---|---:|---|
| `genln_rpt_day` | `loan_daily_snapshot_summary` | 18,587 | ⭐ **Primary source.** Month-end loan snapshot, 180 cols |
| `genlnacnts` | `loan_account_master` | 13,510 | Loan master (no as-of dimension) |
| `asset_classify_dtls` | `asset_classification_details` | 6,833 | IRACP classification (thin history) |
| `glbbal` | `gl_daily_balances` | 1,221 | ⭐ GL balances by branch/year |
| `extgl` | `external_gl_master` | 723 | ⭐ GL chart of accounts |
| `indcifdata_10012025_indcifdata` | `individual_customer_master` | 33,907 | Individual KYC |
| `firmcifdata_dtl` | `corporate_customer_master` | 13,888 | Corporate/firm KYC (7,594 distinct cust_ids) |
| `nsecmsmemap` | `msme_sector_classification_mapping` | 10,571 | Security/LTV map (see §6) |
| `nbfclnscheme` | `loan_product_scheme_master` | 15 | Scheme master (product 16 only) |
| `loanrepay` | `loan_repayment_transactions` | 13,483 | Repayment flows |
| `genlndisb` | `loan_disbursement_transactions` | 5,481 | Disbursement flows |
| `loanschedule` | `loan_repayment_schedule` | 260,437 | Amortisation schedule (maturity buckets) |
| `cust_intf_pid_dtls` | `customer_kyc_details` | 36,144 | KYC/PID — **geography cols 100% NULL** |
| `glbbal`,`extgl`,`fvdata`,`genlnappl`,`genlnapplca`,`genlnapplga`,`appldocuplddtl`,`nbfcln_security` | — | — | Ancillary |

### 1.1 Tables the generator references that DO NOT EXIST

```
bronze.investments        →  ERROR: relation "bronze.investments" does not exist
bronze.mig_share_details  →  ERROR: relation "bronze.mig_share_details" does not exist
```

Both are wrapped in bare `except` blocks, so they fail silently on every single run.
`Annex 10` (Top 25 Investments) and `Annex 2` (Shareholding Pattern) have **never** been
populated from the database.

### 1.2 Column the generator references that DOES NOT EXIST

```
genlnacnts.gnlnac_int_rate  →  ERROR: column "gnlnac_int_rate" does not exist
```

The real column is **`gnlnac_ln_intrate`**. This appears in the Part 8A MSME query
(`dnbs02_service.py:322`), which means **the entire MSME query fails on every run** and
Part 8A is always the hardcoded fallback.

---

## 2. ⭐ `bronze.genln_rpt_day` — the table the report should be built on

18,587 rows = one row per loan account per **month-end**. This is a purpose-built
regulatory snapshot and solves the single biggest design flaw in the current generator
(no as-of date dimension).

**Coverage:** 2025-10-31 → 2026-06-30, exactly 9 month-end dates:

| report_date | accounts | customers | princ_os (₹L) | int_due (₹L) | month_int_coll (₹L) |
|---|---:|---:|---:|---:|---:|
| 2025-10-31 | 11 | 11 | — | — | — |
| 2025-11-30 | 92 | 92 | — | — | — |
| 2025-12-31 | 366 | 366 | 1,214.77 | 2.66 | 2.70 |
| 2026-01-31 | 857 | 857 | 2,878.64 | 2.48 | 20.32 |
| 2026-02-28 | 1,550 | 1,550 | 5,320.06 | 5.71 | 41.32 |
| 2026-03-31 | 2,454 | 2,454 | 8,744.05 | 0.24 | 87.83 |
| 2026-04-30 | 3,338 | 3,338 | 12,159.99 | 1.28 | 128.47 |
| **2026-05-31** | **4,445** | **4,444** | **16,661.41** | **3.14** | **179.87** |
| 2026-06-30 | 5,474 | 5,469 | 20,740.85 | 7.18 | 246.27 |

Columns that map directly onto return fields:

| Column | Feeds |
|---|---|
| `gnlnr_report_date` | **As-of date for every point-in-time field** |
| `gnlnr_princ_os`, `gnlnr_int_due`, `gnlnr_chg_due`, `gnlnr_penal_due` | Annex 9/11, Part 2, Part 8 |
| `gnlnr_pan_no` | Annex 9/11 PAN — **100% populated** (4,445/4,445 at 2026-05-31, 4,443 distinct) |
| `gnlnr_cust_name`, `gnlnr_cust_id` | Borrower identity + **aggregation key** |
| `gnlnr_cust_expo` | Borrower-level total exposure |
| `gnlnr_asset_cd`, `gnlnr_dpd`, `gnlnr_npa_dt` | Part 8 / Part 8C classification |
| `gnlnr_provision_amt`, `gnlnr_provision_post_amt` | Part 8C **actual** provision (no need to hardcode rates) |
| `gnlnr_month_int_coll`, `gnlnr_month_princ_coll`, `gnlnr_m_coll_intdue` | Part 3 period **flows** |
| `gnlnr_proc_fee`, `gnlnr_stamp_dty`, `gnlnr_insu_fee` | Part 3 fee income |
| `gnlnr_ln_intrate`, `gnlnr_base_int_rate` | Part 8A min/max/weighted-avg rate |
| `gnlnr_maturity_dt`, `gnlnr_future_inst` | Part 2 maturity buckets |
| `gnlnr_brn_code`, `gnlnr_adh_district`, `gnlnr_adh_pincode` | Annex 13 |
| `gnlnr_closed_date`, `gnlnr_acnt_status` | Open/closed filter (**`acnt_status` is 100% NULL — use `closed_date`**) |
| `gnlnr_schm_code`, `gnlnr_schm_name`, `gnlnr_purpose_code`, `gnlnr_purpose_name` | Part 8 sectoral split |
| `gnlnr_cibil_score`, `gnlnr_mobile_no` | Not required by DNBS-02 |

**Caveat:** `gnlnr_proc_fee` sums to 0.00 at every date — fee income must come from GL, not here.

---

## 3. Asset quality — the portfolio has **zero NPAs**

`bronze.asset_classify_dtls` (all history):

| asset_code | accounts | princ_os (₹L) |
|---|---:|---:|
| STD | 5,816 | 22,170.44 |
| SMA0 | 1,004 | 3,913.25 |
| SMA1 | 11 | 52.58 |
| SMA2 | 2 | 6.05 |

`genln_rpt_day` agrees: STD / SMA0 / SMA1 / SMA2 only, and `gnlnr_provision_amt` is
**0.00 across every row**.

### Consequences

1. **There is not a single NPA account** (`SUB`, `DBT`, `LOSS`, `NPA` never appear).
   Gross NPA = ₹0.00, GNPA% = 0.00%.
2. The generator's `CASE` (`dnbs02_service.py:285-289`) has an `ELSE 'Doubtful / Loss Assets'`
   catch-all. **SMA-2 falls into it** and is then provisioned at **100%**
   (`dnbs02_service.py:303`). SMA-2 is a *standard* asset under IRACP. The entire reported
   NPA figure is 2 accounts / ₹6.05 lakh of performing loans misclassified as total losses.
3. `Annex 11` (Top 25 NPAs) filters `IN ('SUB','NPA','DBT','LOSS','SMA2')` — it returns
   **only the 2 SMA-2 rows**, neither of which is an NPA.
4. `npa_ratio_pct` therefore falls back to the hardcoded `0.5` (`dnbs02_service.py:618`)
   or reports the misclassification. The truthful answer is 0.00%.

### Coverage gap

`asset_classify_dtls.ascd_effective_date` spans only **2026-05-22 → 2026-07-01** (41 days).
Any report with `end_date < 2026-05-22` returns **zero** asset rows and silently falls back
to fabricated asset quality. `genln_rpt_day` covers 2025-10-31 onward and should be
preferred.

---

## 4. Portfolio structure

### Products (`genlnacnts.gnlnac_prod_code`) — only three exist

| prod_code | accounts | disbursed (₹L) | avg rate | rate range | Generator's label | Correct? |
|---|---:|---:|---:|---|---|---|
| 13 | 7,715 | 7,504.11 | 20.06% | 3.11 – 26.62 | "Microfinance & JLG Loans" | unverified |
| 16 | 5,655 | 22,037.09 | 17.73% | 16.00 – 20.00 | "Secured MSME & Business Loans" | ❌ see below |
| 1 | 140 | 72.73 | 17.73% | 16.00 – 22.00 | "Retail Gold Loans" | unverified |

`nbfclnscheme` holds 15 schemes, **all for product 16**, and every one has
`lnschm_secure_flg = '0'` (unsecured) and `lnschm_sec_type = 0`:

```
1601 Purchase of Site      1606 FOUR WHEELER TAXI / CAR   1611 FARMING
1602 Repair of House       1607 TRACTOR                   1612 CATTLE
1603 PURCHASE OF FIXTURES  1608 LORRY/BUS NEW             1613 POULTRY/SHEEP/PIGS
1604 PURCHASE OF TWO WHEELERS 1609 USED VEHICLES <7 YRS   1614 DEBT SWAPPING
1605 NEW AUTORIKSHAW       1610 BUSINESS/SERVICE/INDUSTRY 1615 LOAN AGAINST PROPERTY
```

So calling product 16 "**Secured** MSME" contradicts the scheme master. Products 13 and 1
have **no scheme master rows at all** — their names in the generator are invented.
The secured/unsecured split for Part 2 C14/C15 is **not reliably derivable** today.

### Branches (`gnlnac_appl_brn_code`)

```
1 → 7,803 accts   4 → 5,567 accts   1002 → 31   1018 → 19   1013 → 17   1020 → 17
1021 → 12   1012 → 8   1001 → 7   1017 → 6   1016 → 6   1006 → 5   1010 → 5  ...
```

Two branches hold 99.0% of accounts. `db_schema.get_branch_info_from_db` maps only codes
`"1"`–`"8"` and falls through to `districts[int(code) % 8]` for everything else — so branch
1002 is reported as "Mandya District (District Code #1002)", a fabricated location.
The generator's `annex13_branches` fallback invents **8 branches** with invented customer
counts, none of which correspond to codes 1 and 4.

**Real geography is not available:** `cust_intf_pid_dtls.cipd_district` and `cipd_state`
are **100% NULL** (36,144/36,144). `genln_rpt_day.gnlnr_adh_district` holds numeric codes
(265, 796, 279, 275, 270, 281, …) with **no district-code master table in the database**.
Annex 13 address/city/state/district cannot be truthfully populated without a new reference feed.

### Open vs closed

| status | accounts | net outstanding (₹L) |
|---|---:|---:|
| OPEN (`closure_date IS NULL`) | 13,344 | 27,522.50 |
| CLOSED | 166 | 0.00 |

The generator never filters on `gnlnac_closure_date`, so 166 settled loans are eligible for
top-25 ranking.

---

## 5. ⭐ GL trial balance — the missing source for Parts 1, 3, 4, 8C

`glbbal` (balances, keyed by **branch + year**) joined to `extgl` (chart of accounts) on
`glbbal_glacc_code = extgl_access_code`. Years present: 2019–2026 (2025: 560 rows,
2026: 631 rows across 5 branches).

⚠️ **`glbbal` is annual, not daily** — despite the silver alias `gl_daily_balances`, the only
time key is `glbbal_year`. Monthly/quarterly Part 1 and Part 3 figures are therefore **not**
derivable at sub-annual granularity from this table. Summing across years double-counts.
**Always filter `glbbal_year = <FY>`.**

⚠️ The `extgl` classification flags (`extgl_int_income`, `extgl_invstmt_income`,
`extgl_int_expenses`, `extgl_operational_exps`, `extgl_other_staff_expenses`,
`extgl_depcreciation_costs`, `extgl_commn_income`, `extgl_disc_rcvd`) are **all NULL/'N'
across all 723 rows** — zero usable flags. Classification must be done on the
`extgl_access_code` prefix instead.

### GL head prefix map (FY2026, ₹ lakhs)

| Prefix | n | Balance | Meaning | Feeds |
|---|---:|---:|---|---|
| `1001` | 2 | 85.50 | Share capital | **Part 1 §2 Share Capital** |
| `1002` | 25 | 24,247.66 | Borrowings (bank OD, unsecured loans) | Part 1 sources of funds |
| `1003` | 10 | -24.65 | Fixed assets | Part 4 (intangibles) |
| `1004` | 8 | -111.05 | Receivables / GST | — |
| `1007` | 10 | 1,523.54 | **Income** | **Part 3** |
| `1008` | 8 | -218.84 | Establishment expenses | Part 3 |
| `1009` | 3 | -1,262.80 | **Investments** | **Part 2 / Annex 10** |
| `1013`,`1014`,`1021`,`1025`,`1026` | 224 | -1,357.74 | Operating/staff expenses | Part 3 |
| `1022` | 3 | 214.64 | **Provisions** (incl. taxation) | Part 8C |
| `1033` | 8 | 21,863.13 | **Reserves & surplus** | **Part 1 §3** |

### Part 1 — Sources of funds (FY2026, real values)

```
10010001003  EQUITY SHARES                            85.50
10010001002  APPLICATION MONEY ON RIGHTS SHARES        0.00
10330011006  SHARES PREMIUM                       21,322.50
10330011005  PROFIT AND LOSS ACCOUNT                 230.21
10330011007  SPECIAL RESERVE                         146.00
10330011002  GENERAL RESERVE                         120.00
10330011009  PROFIT & LOSS A/C                        44.18
10330011001  CAPITAL RESERVE                           0.23
10330011004  EQUITY SHARES                             0.00
10330011008  PROFIT AND LOSS FOR 25 AND 2026           0.00
                                        Reserves  21,863.13
```

**Cross-check:** the template workbook's prior filing shows `Share Capital = 85.5` and
`Reserves and Surplus = 22,355.63`. Equity matches **exactly**; reserves differ by 492.50
(FY boundary). This confirms the GL is the correct and intended source for Part 1.

**Versus what the generator reports today** (hardcoded, `dnbs02_service.py:514-519`):

| Line | Generator | Actual GL | Error |
|---|---:|---:|---|
| Paid-up Equity Capital | 2,500.00 | 85.50 | **29× overstated** |
| Free Reserves | 1,450.00 | 21,863.13 | 15× understated |
| Share Premium | 800.00 | 21,322.50 | 27× understated |
| Net Owned Funds | 4,600.00 | ≈ 21,948.63 | 4.8× understated |

### Part 3 — Income (FY2026, prefix 1007)

```
10070011001  MICRO ENTERPRISES - INTEREST INCOME     861.44
10070011013  INTEREST COLLECTED                      227.56
10070011010  PROFIT ON SALE OF MUTUAL FUNDS          222.02
10070011014  INTEREST ON FD WITH BANKS               145.49
10070011012  COMMISSION                               26.48
10070011006  INTEREST RECEIVED - LOANS AND ADVANCES   15.71
10070011004  DIVIDEND RECEIVED                        12.94
10070011002  BAD DEBTS RECOVERED                      11.10
10070011008  PROCESSING CHARGES RECEIVED               0.79
10070011015  INTEREST OTHERS                           0.02
                                          TOTAL   1,523.54
```

Fund-based interest income = 861.44 + 227.56 + 15.71 = **1,104.71**.
Investment income = 222.02 + 145.49 + 12.94 = **380.45**.
Fee income = 26.48 + 0.79 = **27.27**.

The generator instead computes income as `total_loan_book × 0.177` etc.
(`dnbs02_service.py:543-548`) — pure ratio invention.

### Annex 10 — Investments (FY2026, prefix 1009)

```
10090011003  INVESTMENTS IN MUTUAL FUND              813.59
10090011004  INVESTMENT IN PROPPERTIES               282.67
10090011005  INVESTMENT IN SHARES ( LONG TERM)       166.54
                                          TOTAL   1,262.80
```

(sign-flipped; assets carry credit-normal balances in `glbbal_bc_bal`)

⚠️ **Only 3 aggregate GL lines exist. There is no entity-level investment register in this
database.** Annex 10 requires "Top 25 investments **by entity name** with PAN, nature, type,
book value, amount outstanding". That is **not derivable**. The generator's 25-row
hardcoded list (`dnbs02_service.py:573-599`) — AL CARGO, AXIS, BEML, DSP, CANARA STEEL LTD
with PAN `AAACC7604B`, etc. — is copied verbatim from the prior filing in the template
workbook and is not backed by any data here.

Its GL fallback query (`dnbs02_service.py:238`) is also wrong: matching
`extgl_ext_head_descn ILIKE '%SHARE%'` pulls in **`SHARES PREMIUM` (₹21,322.50 lakh)** — a
*liability* — and reports it as the single largest investment holding.

---

## 6. MSME classification (Part 8A) — not derivable as specified

`bronze.nsecmsmemap` (silver: `msme_sector_classification_mapping`), 10,571 rows:

| msmp_sec_type | rows | distinct accounts | total value (₹L) |
|---|---:|---:|---:|
| 21 | 10,571 | 10,571 | 12,589.58 |

One row per account, a **single** security type, and columns
(`nsecm_sec_no`, `msmp_sec_value`, `msmp_sec_ltv`, `msmp_sec_post_ltv`) that describe
**collateral and LTV**, not enterprise size. It covers 10,571 of 13,510 accounts (78.2%).

**Findings:**
- This table identifies *which* accounts are MSME-mapped — useful as an MSME **filter**,
  which the generator does not currently apply. Today it classifies **all 13,510 loans**,
  including gold loans to individuals, as MSME exposure.
- It does **not** carry investment-in-plant-and-machinery or turnover, so the
  MSMED **Micro / Small / Medium** split required by Part 8A rows 17–19 **cannot be
  computed**. The generator's proxy — bucketing on *sanctioned amount*
  (`dnbs02_service.py:315-318`) — is not the statutory definition, and its labels are wrong
  anyway (`<= 10000000` is ₹1 crore but is labelled "₹25L – ₹5 Cr").
- Interest rate min/max/weighted-average (Part 8A cols G/H/I) **is** derivable, from
  **`genlnacnts.gnlnac_ln_intrate`**. That column is populated on all 13,344 open accounts
  (range 3.11%–26.62%) and is **identical to `genln_rpt_day.gnlnr_ln_intrate` wherever both
  exist** (4,445 of 4,445 rows at 2026-05-31), so it is the safe single source.

**Part 8A must be sourced from `genlnacnts`, not the snapshot.** `nsecmsmemap` joins to
`genlnacnts` on 7,715 rows but to `genln_rpt_day` on **0** — the MSME accounts are all
product 13, which the snapshot does not carry (§9a). Querying the snapshot returns nothing.
From the loan master the section resolves to:

| | value |
|---|---:|
| MSME accounts (open) | 7,653 |
| Outstanding | ₹6,387.05 lakh |
| Interest rate range | 3.11% – 26.62% |
| Weighted average rate | 21.42% |

Caveat carried in the section's provenance `note`: `genlnacnts` has no as-of dimension, so
the outstanding amount is a current balance rather than a period-end one. Account counts
and rates are unaffected.

---

## 7. Borrower identity & Annex 9

### Aggregation matters enormously

Top 5 by **customer** at 2026-05-31 (correct):

| cust_id | name | PAN | accts | princ_os (₹L) |
|---|---|---|---:|---:|
| 261 | SUVARNA J | JXTPS8952N | 1 | 18.17 |
| 1398 | DEVENDRA KUMAR P | AKVPP5380K | 1 | 13.37 |
| 1395 | CHIDANANDA POOJARY | FWKPP5221F | 1 | 12.45 |
| 1229 | A KUMARA | COYPK2317C | 1 | 12.24 |
| 8779 | SUJATHA | PHLPS7630R | 1 | 12.00 |

At this snapshot the top borrowers happen to hold one account each, so per-account and
per-customer ranking coincide — but with 4,445 accounts / 4,444 customers that is
coincidental, and it diverges at 2026-06-30 (5,474 accounts / 5,469 customers).
`GROUP BY gnlnr_cust_id` is required regardless; RBI asks for top 25 **borrowers**.

### Scale reality check

**The largest single borrower in the portfolio owes ₹18.17 lakh.** The generator's
hardcoded Annex 9 fallback opens with `S V SUBRAMANYA BHAT — ₹600.92 lakh`
(`dnbs02_service.py:448`), a **33× overstatement**, and lists 25 borrowers averaging
₹190 lakh. Those first four rows (with PANs `ACFPB2996P`, `AWNPM3131F`, `BZWPC0018A`,
`BGOPP3657D`) are lifted directly from the prior filing embedded in the template workbook —
i.e. **real customer PANs from an unrelated entity's return, committed to source control.**

### Borrower type — **not derivable**

`firmcifdata_dtl` looks like a corporate register but is not one. Of its 7,594 distinct
`firmd_cust_id` values, **7,294 also appear in `indcifdata`**; `firmd_assos_firm = 'I'`
and `firmd_cust_id = firmd_ind_cust_id` on most rows. It is an *associated firm / director*
detail table. Joining it to classify borrowers marks **every** borrower CORPORATE.

The generator's existing proxy (`prod_code = 16 → 'CORPORATE'`, `dnbs02_service.py:135`) is
equally unfounded. Legal constitution has **no source**; Annex 9/11 `Type of Borrower` must
be left blank.

### Customer master names disagree with the loan tables

Joining `genlnacnts` to `indcifdata` on `cust_id` — which the existing Annex 9 query does at
`dnbs02_service.py:143` — matches the first name only **7,836 of 13,253 times (59%)**. For
example `cust_id 261` is `SUVARNA J` in the loan tables and `BINEETHA C` in `indcifdata`.

By contrast `genln_rpt_day.gnlnr_cust_name` agrees with `genlnacnts.gnlnac_cust_name` on
**4,426 of 4,445** rows, and `gnlnr_cust_id` matches on **4,445 of 4,445**. Borrower names
must therefore come from the snapshot directly, with no customer-master join.

### PAN

`genln_rpt_day.gnlnr_pan_no` is **100% populated**. The generator hardcodes `'NA'` in both
Annex 9 (line 132) and Annex 11 (line 414).

---

## 8. Units

`genlnacnts`, `asset_classify_dtls` and `genln_rpt_day` amounts are in **rupees**; dividing
by 100,000 for ₹ lakhs is correct and is corroborated by the cross-check in §5
(GL equity 85.50 lakh == template's 85.5).

`glbbal_bc_bal` is **also in rupees** — same divisor.

The generator's per-row unit heuristic in the Annex 10 query
(`CASE WHEN book_value > 10000 THEN /100000.0 ELSE book_value END`, `dnbs02_service.py:217`)
is unnecessary and actively harmful: it scales rows differently based on their own
magnitude. Since the table it reads doesn't exist, this has never executed — but it must
not be carried into the rewrite.

---

## 9. Derivability summary

| Return section | Source | Status |
|---|---|---|
| Part 1 — Sources of funds | `glbbal`+`extgl` prefix 1001/1002/1033, `glbbal_year` | ✅ Derivable (annual only) |
| Part 2 — Application of funds | `genln_rpt_day`; maturity from `loanschedule` | ✅ Derivable (except secured/unsecured, §4) |
| Part 3 — Profitability | `glbbal`+`extgl` prefix 1007/1008/1013/1014/1021/1025 | ✅ Derivable (annual only) |
| Part 4 — NOF | Part 1 less `1003` intangibles | ✅ Derivable |
| Part 6 — Sensitive sectors | `extgl` 1009 (property/capital-market exposure) | ⚠️ Partial |
| Part 8 — Sectoral asset quality | `genln_rpt_day` + `gnlnr_purpose_code` | ⚠️ Partial — RBI sector taxonomy needs a mapping |
| Part 8A — MSME | `nsecmsmemap` filter + `gnlnr_ln_intrate` | ⚠️ Filter + rates only; **size split not derivable** |
| Part 8C — Asset classification | `genln_rpt_day.gnlnr_asset_cd` / `gnlnr_provision_amt` | ✅ Derivable (all Standard, provision 0) |
| Annex 2 — Shareholding | — | ❌ **No source. Table does not exist.** |
| Annex 9 — Top 25 borrowers | `genln_rpt_day` GROUP BY `gnlnr_cust_id` | ✅ Fully derivable incl. PAN |
| Annex 10 — Top 25 investments | `glbbal` 1009 (3 aggregate lines only) | ❌ **Entity-level not derivable** |
| Annex 11 — Top 25 NPAs | `genln_rpt_day` | ✅ Derivable — correct answer is **empty (zero NPAs)** |
| Annex 13 — Branches | `gnlnr_brn_code` | ⚠️ Counts yes; **address/city/state/district have no source** |
| Annex 1/3/4/5/6/7/8/12, Part 5/7/7A/8B/9, AuthorisedSignatory | — | ❌ No source; currently exported from the prior filing verbatim |

---

## 9a. Snapshot coverage — `genln_rpt_day` holds **product 16 only**

The snapshot table is the right shape but not the whole book:

| | accounts | ₹ lakh |
|---|---:|---:|
| Open accounts in `genlnacnts` | 13,344 | 27,522.50 |
| Covered by the 2026-05-31 snapshot | 4,441 | 16,661.41 |
| **No dated snapshot** | **7,884** | **6,773.53** |

`SELECT gnlnr_prod_code, COUNT(*) FROM bronze.genln_rpt_day GROUP BY 1` returns a single
row: **product 16**. Products 13 (7,653 open accounts) and 1 (99) never appear, plus 132
product-16 accounts.

Two consequences:

1. Reporting solely from `genln_rpt_day` **understates the loan book by ~29%**. Back-filling
   the gap from `genlnacnts` would be worse — that table has no date dimension, so its
   balances would be undated figures presented as period-end. The implementation therefore
   reports the covered portion and **discloses the excluded remainder** in a `coverage`
   block surfaced in the API, the UI and the FilingInfo sheet.
2. It explains why Part 8A comes back empty: `nsecmsmemap` maps **product-13 accounts
   exclusively** (7,715 of its rows join to `genlnacnts`, **0** to `genln_rpt_day`), so the
   MSME set and the snapshot set are disjoint at every snapshot date.

**This is the most important open item for the client:** either `genln_rpt_day` needs
back-filling for products 1 and 13, or a second dated source is required for them.

---

## 10. What this means for the fix

1. **Repoint every query at `genln_rpt_day`** keyed on `gnlnr_report_date = <period end>`.
   It is the only table with a proper as-of dimension, and it carries PAN, provisions,
   period flows, and customer-level exposure.
2. **Use the GL (`glbbal` + `extgl`, filtered by `glbbal_year`) for Parts 1, 3, 4, 8C** —
   currently never queried. Classify on `extgl_access_code` prefix; the `extgl` flag columns
   are unusable.
3. **Delete every fallback.** Sections with no source (Annex 2, Annex 10 entity detail,
   Annex 13 addresses, and the 14 untouched sheets) must be emitted **blank** with an
   explicit "no source" note, never with plausible-looking invented numbers.
4. **Report zero NPAs honestly.** Fix the `ELSE` catch-all so SMA-2 stays Standard, and
   let Annex 11 come back empty.
5. **Constrain the period selector** to the 9 month-ends actually present
   (2025-10-31 … 2026-06-30). Requests outside that range currently produce silent
   fabrication; they should produce an explicit error.
6. **Flag the annual-only GL limitation** in the UI: monthly and quarterly Part 1/3/4
   figures cannot be produced from this warehouse.
