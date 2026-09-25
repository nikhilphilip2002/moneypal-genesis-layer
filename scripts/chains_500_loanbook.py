"""Corpus of 500 Governed Loan Book Questions organized into 100 5-Turn Chains.

All queries are 100% focused on the Gold Semantic Layer:
- Agents, Branches, Schemes, Products, Customers, KYC, Balances, Disbursements, Collections,
  Repayments, Delinquencies, DPD Buckets, and Asset Classifications/NPA.
Every chain is 5 sequential turns without prompt hints.
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Chain:
    id: int
    category: str
    title: str
    questions: tuple[str, str, str, str, str]


CHAINS: tuple[Chain, ...] = (
    # =========================================================================
    # Domain 1: Agent & Staff Operations (Chains 1 - 10)
    # =========================================================================
    Chain(
        1,
        "Agent Operations",
        "Top Agents by Customer Volume",
        (
            "Show the top 10 agents with the highest customer count.",
            "Show me customers under Vanitha.",
            "Add tenure and sanctioned amount to the above table.",
            "What is the total sanctioned amount for Vanitha?",
            "Show the linked loan account numbers.",
        ),
    ),
    Chain(
        2,
        "Agent Operations",
        "Agent Origination Ranking",
        (
            "Rank the top 10 agents by sanctioned loan count.",
            "Now rank them by total disbursed amount.",
            "Add distinct borrower count to that list.",
            "Which agent has the highest average ticket size?",
            "For that top agent, list their linked loan accounts.",
        ),
    ),
    Chain(
        3,
        "Agent Operations",
        "Agent Sourcing Quality and Exposure",
        (
            "Which agents have the highest principal outstanding?",
            "Break that down by account status.",
            "How much of that principal is currently overdue?",
            "Show the accounts in NPA under those agents.",
            "What is the overall NPA percentage for these agents?",
        ),
    ),
    Chain(
        4,
        "Agent Operations",
        "Agent Collection Performance",
        (
            "Show total repayments collected by agent.",
            "Split that into principal repaid and interest collected.",
            "Which agent collected the most interest this financial year?",
            "What is the collection efficiency for that agent?",
            "List the borrowers who made those repayments.",
        ),
    ),
    Chain(
        5,
        "Agent Operations",
        "Recently Joined Field Agents",
        (
            "List all agents joined in the last 12 months.",
            "How many customers has each new agent onboarded?",
            "Add total sanctioned loan volume for each.",
            "Filter for agents with more than 50 customers.",
            "Show their branch affiliations.",
        ),
    ),
    Chain(
        6,
        "Agent Operations",
        "Field Agent Sanctions vs Disbursements",
        (
            "Show agents with the largest gap between sanctioned and disbursed amounts.",
            "What is the conversion rate for each of these agents?",
            "Filter for agents with conversion rates below 80%.",
            "Which branches do these agents operate in?",
            "List the un-disbursed loan accounts for these agents.",
        ),
    ),
    Chain(
        7,
        "Agent Operations",
        "Agent Tenure and Productivity",
        (
            "What is the average loan tenure sourced by each agent?",
            "Which agents source the longest-term loans?",
            "For those agents, show total principal outstanding.",
            "Add average interest rate to the table.",
            "How many of their loans have tenures exceeding 36 months?",
        ),
    ),
    Chain(
        8,
        "Agent Operations",
        "Sales Hierarchy and Reporting Lines",
        (
            "Show sales hierarchy managers and their reporting team members.",
            "Which sales manager oversees the highest number of field agents?",
            "What is the total disbursed portfolio under that sales manager?",
            "Break down that portfolio by scheme.",
            "Show the top 5 performing agents under that manager.",
        ),
    ),
    Chain(
        9,
        "Agent Operations",
        "Collections Hierarchy and Arrears",
        (
            "Show the collections hierarchy and assigned recovery teams.",
            "Which collections manager has the highest overdue principal?",
            "Show the DPD bucket distribution for that manager's accounts.",
            "Filter for accounts in the 61-90 DPD bucket.",
            "List the linked customer names and outstanding balances.",
        ),
    ),
    Chain(
        10,
        "Agent Operations",
        "Agent Portfolio At Risk",
        (
            "Which agents have loan accounts in PAR 30?",
            "Show total overdue amount for each of these agents.",
            "Add total active borrower count to the table.",
            "What is the PAR 30 ratio for the leading agent?",
            "List the delinquent borrower names under that agent.",
        ),
    ),
    # =========================================================================
    # Domain 2: Branch Network & Geographic Origination (Chains 11 - 22)
    # =========================================================================
    Chain(
        11,
        "Branch Network",
        "Branch Directory & Office Status",
        (
            "List all currently active branches with branch code and name.",
            "Add IFSC code and opened date to the list.",
            "How many active branches are there in total?",
            "Which branch was opened most recently?",
            "Show the total sanctioned loan volume for that newest branch.",
        ),
    ),
    Chain(
        12,
        "Branch Network",
        "Branch Disbursement Leaders",
        (
            "Rank application branches by total disbursed amount this financial year.",
            "Add sanctioned loan count for each branch.",
            "Now add distinct borrower count.",
            "Which branch has the highest average ticket size?",
            "For the top branch, show the monthly disbursement trend.",
        ),
    ),
    Chain(
        13,
        "Branch Network",
        "Branch Customer Franchise (Ujire)",
        (
            "List customers in Ujire.",
            "Add scheme name and tenure.",
            "Also include disbursed amount.",
            "How many distinct customers are in that branch?",
            "What is total principal outstanding for that branch?",
        ),
    ),
    Chain(
        14,
        "Branch Network",
        "Branch Portfolio Concentration",
        (
            "What is total principal outstanding across each branch?",
            "What percentage of the total portfolio does the top branch hold?",
            "Break down that branch's portfolio by loan product.",
            "Show the top 10 borrowers in that branch.",
            "What is the overdue principal amount in that branch?",
        ),
    ),
    Chain(
        15,
        "Branch Network",
        "Branch Collections & Repayments",
        (
            "Show total repayment collections by branch this financial year.",
            "Separate principal collections from interest collections.",
            "Which branches had collections drop in the last month?",
            "What is the collection efficiency for the lowest collecting branch?",
            "List the top delinquent accounts in that branch.",
        ),
    ),
    Chain(
        16,
        "Branch Network",
        "Branch Delinquency & PAR 30",
        (
            "What is the current PAR 30 ratio by branch?",
            "Which branches have PAR 30 exceeding 5%?",
            "For those high-risk branches, show total overdue balance.",
            "Break down that overdue amount by DPD bucket.",
            "Show the top 5 overdue borrowers in the most delinquent branch.",
        ),
    ),
    Chain(
        17,
        "Branch Network",
        "Coastal vs Hinterland Performance",
        (
            "Compare total loan sanctions in Mangalore with Belthangady.",
            "Add total disbursed amount for both branches.",
            "Show average interest rate for both locations.",
            "Which of the two has a higher customer count?",
            "Compare the NPA ratios between these two branches.",
        ),
    ),
    Chain(
        18,
        "Branch Network",
        "Branch Sanction-to-Disbursement Pipeline",
        (
            "Show total sanctioned amount versus disbursed amount by branch.",
            "Calculate the undisbursed sanction pipeline for each branch.",
            "Which branch has the largest undisbursed pipeline?",
            "List the loan accounts awaiting disbursement in that branch.",
            "What is the average sanction amount of these pending loans?",
        ),
    ),
    Chain(
        19,
        "Branch Network",
        "Branch Growth & Monthly Trajectory",
        (
            "Show monthly disbursements for the top 3 branches over the last 6 months.",
            "Which of these branches had the fastest growth?",
            "Add loan sanction count for each month.",
            "What was the highest monthly disbursement recorded by any branch?",
            "Which branch achieved that peak?",
        ),
    ),
    Chain(
        20,
        "Branch Network",
        "Branch Ticket Size Dynamics",
        (
            "What is the average sanctioned loan ticket size across all branches?",
            "Rank branches by average ticket size descending.",
            "For the branch with the highest ticket size, show its product mix.",
            "How many loans in that branch exceed 5 lakhs?",
            "List the borrower names and sanction amounts for those large loans.",
        ),
    ),
    Chain(
        21,
        "Branch Network",
        "Branch Asset Classification Profile",
        (
            "Show distribution of loan accounts across asset classifications by branch.",
            "How many accounts are classified as Sub-Standard in each branch?",
            "Filter for branches with more than 10 Sub-Standard accounts.",
            "Show the total principal outstanding of these Sub-Standard accounts.",
            "List the borrower names and overdue days for these accounts.",
        ),
    ),
    Chain(
        22,
        "Branch Network",
        "Branch Loan Closure Trends",
        (
            "How many loan accounts have been closed in each branch?",
            "Add total principal repaid on closed loans.",
            "What was the average duration to closure for these accounts?",
            "Compare closed loan counts with currently active loan counts.",
            "Which branch has the highest closure-to-active ratio?",
        ),
    ),
    # =========================================================================
    # Domain 3: Lending Schemes & Products (Chains 23 - 34)
    # =========================================================================
    Chain(
        23,
        "Schemes & Products",
        "Scheme Portfolio & Outstanding Balance",
        (
            "Which schemes have the largest principal outstanding?",
            "For those schemes, show total disbursed amount.",
            "Also show their sanctioned loan count.",
            "Which schemes have the highest average ticket size?",
            "What is the weighted average interest rate for these schemes?",
        ),
    ),
    Chain(
        24,
        "Schemes & Products",
        "Product Scheme Pricing & Term Bounds",
        (
            "List product schemes with minimum and maximum interest rates and tenor months.",
            "Show every lending scheme, its product, rate bounds, and tenor bounds.",
            "Which schemes offer the lowest minimum interest rate?",
            "How many active loans are currently booked under that lowest-rate scheme?",
            "What is the total outstanding balance in that scheme?",
        ),
    ),
    Chain(
        25,
        "Schemes & Products",
        "Gold Loan Performance",
        (
            "How many gold loans are currently active?",
            "What is the total principal outstanding in gold loans?",
            "Show the monthly gold loan disbursement trend this financial year.",
            "What is the average ticket size of our gold loans?",
            "What is the PAR 30 delinquency ratio for gold loans?",
        ),
    ),
    Chain(
        26,
        "Schemes & Products",
        "Business & MSME Lending Schemes",
        (
            "List all business and MSME loan schemes.",
            "Show active loan count and principal outstanding for each.",
            "Add average interest rate and average tenure.",
            "Which MSME scheme has the highest default rate?",
            "Show the top 10 borrowers in that MSME scheme.",
        ),
    ),
    Chain(
        27,
        "Schemes & Products",
        "Personal Loan Portfolio",
        (
            "What is the total sanctioned amount in personal loan schemes?",
            "How much has been disbursed to date?",
            "What is the collection efficiency for personal loans this month?",
            "Break personal loans down by DPD bucket.",
            "How many personal loan accounts are currently in NPA?",
        ),
    ),
    Chain(
        28,
        "Schemes & Products",
        "Scheme Sanction-to-Disbursement Conversion",
        (
            "Compare sanctioned amount with disbursed amount across all schemes.",
            "Show the difference by scheme.",
            "What is the sanction-to-disbursement conversion rate for each scheme?",
            "Which scheme has the lowest conversion rate?",
            "List the open loans in that scheme with zero disbursements.",
        ),
    ),
    Chain(
        29,
        "Schemes & Products",
        "Scheme Repayment Cash Flows",
        (
            "How much principal has been repaid by scheme this financial year?",
            "Compare principal repaid with total disbursed amount for each scheme.",
            "Which schemes have the lowest principal repayment percentage?",
            "Add total interest collected for each scheme.",
            "What is the total cash inflow from the leading scheme?",
        ),
    ),
    Chain(
        30,
        "Schemes & Products",
        "Scheme Interest Rate Spread & Yield",
        (
            "Show the average interest rate charged by scheme.",
            "Compare that with the minimum and maximum contractual rates.",
            "Which schemes have the widest interest rate spread?",
            "What is the total interest income generated by each scheme?",
            "List loans with interest rates above 18% in those schemes.",
        ),
    ),
    Chain(
        31,
        "Schemes & Products",
        "Scheme Delinquency & Overdue Balances",
        (
            "Which schemes have the highest overdue principal?",
            "Add overdue interest amount for each scheme.",
            "What is the total overdue amount across all schemes?",
            "What percentage of total outstanding is overdue in the highest-risk scheme?",
            "Show the top 10 delinquent accounts in that scheme.",
        ),
    ),
    Chain(
        32,
        "Schemes & Products",
        "Scheme Origination Vintage Growth",
        (
            "Show loan count sanctioned by scheme in FY26 compared to FY25.",
            "Which scheme showed the highest year-over-year volume growth?",
            "What was the growth in total sanctioned amount for that scheme?",
            "Show the monthly sanction trend for that scheme.",
            "Break down borrowers in that scheme by gender.",
        ),
    ),
    Chain(
        33,
        "Schemes & Products",
        "Scheme Product Reporting Mappings",
        (
            "Show schemes whose reporting-product mapping is still provisional.",
            "List product and scheme mappings with mapping status and reporting product name.",
            "Which lending schemes have unapproved reporting mappings?",
            "How many active loans are impacted by provisional mappings?",
            "What is the total portfolio value under provisional mappings?",
        ),
    ),
    Chain(
        34,
        "Schemes & Products",
        "High-Yield vs Low-Risk Scheme Mix",
        (
            "Group schemes into high-yield (rate > 14%) and standard yield (rate <= 14%).",
            "Show total principal outstanding in both groups.",
            "Compare PAR 30 delinquency between the two groups.",
            "What is the average tenure for each group?",
            "Which group has higher collection efficiency?",
        ),
    ),
    # =========================================================================
    # Domain 4: Customer Demographics, Identity & KYC (Chains 35 - 44)
    # =========================================================================
    Chain(
        35,
        "Customer & KYC",
        "Gender Participation & Demographics",
        (
            "How many borrowers are female and how many are male?",
            "Show total disbursed amount by gender.",
            "Now show average sanctioned ticket size by gender.",
            "Break female borrower count down by scheme.",
            "Which application branches serve the most female borrowers?",
        ),
    ),
    Chain(
        36,
        "Customer & KYC",
        "Borrower Occupation Profiles",
        (
            "Count customer profiles by gender and occupation.",
            "Show the borrower profile distribution across occupation types.",
            "Which occupation group has received the highest sanctioned amount?",
            "What is the average loan size for agricultural borrowers vs salaried borrowers?",
            "Which occupation category has the lowest delinquency rate?",
        ),
    ),
    Chain(
        37,
        "Customer & KYC",
        "KYC Verification Status",
        (
            "List customers whose KYC is not verified with name and home branch.",
            "How many total unverified customer profiles are in the database?",
            "Break unverified customers down by home branch.",
            "Do any unverified customers have active sanctioned loans?",
            "List the loan account numbers and sanctioned amounts for unverified customers.",
        ),
    ),
    Chain(
        38,
        "Customer & KYC",
        "KYC Document Inventory & Types",
        (
            "Count KYC documents by document type and address-proof flag.",
            "Show document inventory totals split by document type and identity proof status.",
            "How many customer documents qualify as both address and identity proof?",
            "Which document type is most commonly submitted?",
            "How many customers have only a single document on file?",
        ),
    ),
    Chain(
        39,
        "Customer & KYC",
        "KYC Document Expiry Pipeline",
        (
            "List customer documents expiring in the next 90 days with customer ID and document type.",
            "How many identity documents expire between today and 90 days from now?",
            "Break down expiring documents by home branch.",
            "Do these customers have active outstanding loan balances?",
            "Show the total principal outstanding linked to expiring documents.",
        ),
    ),
    Chain(
        40,
        "Customer & KYC",
        "Customer Age & Vintage Demographics",
        (
            "Group borrowers by age brackets: under 30, 30-50, and above 50.",
            "Show total active loan count in each age bracket.",
            "What is the total principal outstanding by age bracket?",
            "Which age bracket has the highest average ticket size?",
            "Compare collection efficiency across age brackets.",
        ),
    ),
    Chain(
        41,
        "Customer & KYC",
        "Top Borrower Concentration Risk",
        (
            "Show the top 10 borrowers with the largest principal outstanding.",
            "Add their home branch and linked loan count.",
            "What is the total combined outstanding of these top 10 borrowers?",
            "What percentage of the overall loan book does this represent?",
            "List the individual loan account numbers for the single largest borrower.",
        ),
    ),
    Chain(
        42,
        "Customer & KYC",
        "Repeat Borrowers & Multi-Loan Customers",
        (
            "How many customers have more than one sanctioned loan account?",
            "What is the maximum number of loans held by any single customer?",
            "Who is that customer and which branch are they associated with?",
            "Show all loan accounts, sanction dates, and amounts for that customer.",
            "What is the current repayment status of those loans?",
        ),
    ),
    Chain(
        43,
        "Customer & KYC",
        "Customer Relationship Vintage",
        (
            "Group customers by years of relationship with the institution.",
            "What is the average sanction amount for long-standing customers (> 3 years)?",
            "Compare their delinquency rate against newly onboarded customers (< 1 year).",
            "Which branch has the highest proportion of long-tenured customers?",
            "Show the total outstanding balance of these vintage customers.",
        ),
    ),
    Chain(
        44,
        "Customer & KYC",
        "PII & Profile Data Completeness",
        (
            "Show customer profile counts with masked contact numbers.",
            "Are any customer email addresses missing in the profile table?",
            "How many customer profiles have complete address records?",
            "Break down customer count by state and district.",
            "List branches with the highest number of incomplete customer profiles.",
        ),
    ),
    # =========================================================================
    # Domain 5: Portfolio Balances & Loan Accounts (Chains 45 - 54)
    # =========================================================================
    Chain(
        45,
        "Portfolio Balances",
        "Overall Loan Book Scale & Status Mix",
        (
            "How many sanctioned loan accounts are in the loan book?",
            "Break that down by account status.",
            "Now show it by scheme.",
            "What is the total sanctioned amount across all active accounts?",
            "What is the current total principal outstanding?",
        ),
    ),
    Chain(
        46,
        "Portfolio Balances",
        "Portfolio Outstanding Concentration",
        (
            "What is the current principal outstanding across the loan book?",
            "Break it down by scheme.",
            "Now show it by application branch.",
            "Split it by account status.",
            "Which ten borrowers have the largest principal outstanding?",
        ),
    ),
    Chain(
        47,
        "Portfolio Balances",
        "Active Loan Account Details",
        (
            "List open loan accounts with borrower name, sanction amount and interest rate.",
            "Which active loans have the highest interest rates? Include customer and sanctioned value.",
            "Show current account numbers, customer names, sanctioned amounts and ROI.",
            "Filter for active loans with interest rates greater than 16%.",
            "What is the total principal outstanding of these high-rate loans?",
        ),
    ),
    Chain(
        48,
        "Portfolio Balances",
        "High-Ticket Loan Exposure",
        (
            "How many active loan accounts have sanctioned amounts above 10 lakhs?",
            "What is the total principal outstanding of these high-ticket loans?",
            "Break down these high-ticket loans by branch.",
            "Which schemes do these high-ticket loans belong to?",
            "List the borrower names and current DPD status for each.",
        ),
    ),
    Chain(
        49,
        "Portfolio Balances",
        "Loan Tenure & Amortization Mix",
        (
            "What is the distribution of active loans by sanctioned tenure in months?",
            "How many loans have tenures exceeding 60 months?",
            "What is the total outstanding balance of loans with tenures above 5 years?",
            "What is the weighted average interest rate for long-tenure loans?",
            "Compare default rates between short-term (< 12 months) and long-term loans.",
        ),
    ),
    Chain(
        50,
        "Portfolio Balances",
        "Interest Rate Slabs Portfolio Breakdown",
        (
            "Group active loans into interest rate slabs: under 10%, 10-14%, 14-18%, above 18%.",
            "Show account count and total principal outstanding in each slab.",
            "Which slab contributes the highest monthly interest income?",
            "Show the average loan ticket size within each interest slab.",
            "Break down the highest rate slab by scheme.",
        ),
    ),
    Chain(
        51,
        "Portfolio Balances",
        "Loan Vintage & Sanction Year Distribution",
        (
            "Break down total loan accounts by year of sanction.",
            "What is the outstanding principal for loans sanctioned before 2024?",
            "How many of those older vintage loans are still active?",
            "What is their delinquency profile compared to FY26 sanctions?",
            "List any pre-2023 loans with overdue principal.",
        ),
    ),
    Chain(
        52,
        "Portfolio Balances",
        "Fully Disbursed vs Staged Accounts",
        (
            "How many loans have total disbursed amount equal to sanctioned amount?",
            "How many loans are partially disbursed?",
            "What is the total undisbursed sanction commitment across active accounts?",
            "Break down undisbursed amounts by scheme.",
            "Which branches hold the largest undisbursed commitments?",
        ),
    ),
    Chain(
        53,
        "Portfolio Balances",
        "Loan Repayment Frequency Mix",
        (
            "Break down active loan accounts by repayment frequency.",
            "What is the total principal outstanding in monthly EMI loans?",
            "What is the average ticket size for bullet repayment loans?",
            "Compare PAR 30 delinquency between monthly and bullet loans.",
            "Which branches disburse the most bullet loans?",
        ),
    ),
    Chain(
        54,
        "Portfolio Balances",
        "Closed and Settled Accounts History",
        (
            "How many loan accounts have been closed or settled all-time?",
            "What was the total principal amount recovered on closed loans?",
            "How much total interest was collected across closed accounts?",
            "What was the average active life in months of closed accounts?",
            "Were any closed accounts ever classified as NPA prior to closure?",
        ),
    ),
    # =========================================================================
    # Domain 6: Disbursements & Loan Flows (Chains 55 - 64)
    # =========================================================================
    Chain(
        55,
        "Disbursements",
        "FYTD Disbursement Trajectory",
        (
            "What is our total disbursed amount this financial year?",
            "Show the monthly trend.",
            "Compare it with the previous financial year.",
            "Break the current financial year down by application branch.",
            "Which five schemes disbursed the most?",
        ),
    ),
    Chain(
        56,
        "Disbursements",
        "Disbursement Event Volumes & Ticket Size",
        (
            "How many disbursement events occurred this financial year?",
            "What is the average disbursement amount per event?",
            "Show the distribution of disbursement events by day of week.",
            "Which day of the week sees the highest disbursement volumes?",
            "What was the single largest disbursement event recorded this year?",
        ),
    ),
    Chain(
        57,
        "Disbursements",
        "Quarterly Disbursement Momentum",
        (
            "Compare total disbursements in Q1 versus Q2 of this financial year.",
            "What was the percentage growth between the two quarters?",
            "Which schemes drove that quarterly growth?",
            "Which branches saw declining disbursements between Q1 and Q2?",
            "What was the change in average ticket size between quarters?",
        ),
    ),
    Chain(
        58,
        "Disbursements",
        "Multiple Drawdown Loans",
        (
            "How many loan accounts have more than one disbursement event?",
            "What is the maximum number of disbursements for a single loan account?",
            "Show the disbursement dates and amounts for that account.",
            "What is the total sanctioned amount for that multi-drawdown loan?",
            "Is that loan currently performing or overdue?",
        ),
    ),
    Chain(
        59,
        "Disbursements",
        "Branch Monthly Disbursement Consistency",
        (
            "Show monthly disbursements for Ujire branch across the last 6 months.",
            "What was the highest disbursement month for Ujire?",
            "Add distinct borrower count for each month.",
            "What was the average disbursement ticket size in Ujire's peak month?",
            "Which schemes accounted for most of Ujire's disbursements?",
        ),
    ),
    Chain(
        60,
        "Disbursements",
        "Disbursement vs Sanction Lag",
        (
            "What is the average number of days between sanction date and first disbursement?",
            "Which schemes have the shortest sanction-to-disbursement turnaround?",
            "Which branch has the longest turnaround time?",
            "List accounts where first disbursement occurred more than 30 days after sanction.",
            "What was the total sanctioned amount of these delayed disbursements?",
        ),
    ),
    Chain(
        61,
        "Disbursements",
        "Recent Disbursement Inflow (Last 30 Days)",
        (
            "What was our total disbursement in the last 30 days?",
            "How many distinct loans were disbursed in this 30-day period?",
            "Break this 30-day volume down by branch.",
            "Which scheme had the highest 30-day disbursement?",
            "What is the current outstanding balance on these freshly disbursed loans?",
        ),
    ),
    Chain(
        62,
        "Disbursements",
        "First Disbursement vs Subsequent Releases",
        (
            "Compare total first-disbursement amounts with subsequent tranche amounts.",
            "What percentage of total disbursement is released on day one?",
            "Which product category utilizes staged tranches the most?",
            "Show average time elapsed between tranche 1 and tranche 2.",
            "What is the current collection status of staged disbursement loans?",
        ),
    ),
    Chain(
        63,
        "Disbursements",
        "High-Growth Disbursement Branches",
        (
            "Which 5 branches have the highest disbursement growth this quarter?",
            "What are their total disbursed amounts?",
            "Add sanctioned loan count for each growing branch.",
            "How do their average ticket sizes compare?",
            "What are their PAR 30 delinquency ratios?",
        ),
    ),
    Chain(
        64,
        "Disbursements",
        "Seasonal Disbursement Trends",
        (
            "Show monthly disbursements aggregated across calendar months to identify seasonality.",
            "Which calendar month historically records the highest lending activity?",
            "Which month records the lowest disbursements?",
            "Does loan sanction count follow the exact same seasonal pattern?",
            "Compare festival-quarter disbursements with Q1 disbursements.",
        ),
    ),
    # =========================================================================
    # Domain 7: Collections, Cash Flow & Efficiency (Chains 65 - 76)
    # =========================================================================
    Chain(
        65,
        "Collections & Cash Flow",
        "Collection Efficiency Overview",
        (
            "What is our collection efficiency this month?",
            "Show total amount due and total amount collected behind that result.",
            "Break collection efficiency down by scheme.",
            "Now show it by application branch.",
            "Compare this month with last month.",
        ),
    ),
    Chain(
        66,
        "Collections & Cash Flow",
        "Principal vs Interest Recovery Cash Flows",
        (
            "How much total cash was collected in the last 30 days?",
            "Break that cash collection into principal repaid and interest collected.",
            "Show the monthly trend of interest collected this financial year.",
            "What is the ratio of interest income to principal recovered?",
            "Which branch collected the most interest this year?",
        ),
    ),
    Chain(
        67,
        "Collections & Cash Flow",
        "Disbursement and Collection Net Cash Flow",
        (
            "Show monthly disbursements and total collections for this financial year.",
            "Which months had collections below disbursements?",
            "What was the largest monthly cash-flow gap?",
            "Break the current total collection amount down by scheme.",
            "Which branches collected the most this financial year?",
        ),
    ),
    Chain(
        68,
        "Collections & Cash Flow",
        "Scheduled Dues vs Actual Collections",
        (
            "What was the total contractual amount due this month across all accounts?",
            "How much was actually paid against those dues?",
            "How much principal remains overdue from this month's billing?",
            "Break down overdue dues by scheme.",
            "List the top 10 accounts with unpaid scheduled dues this month.",
        ),
    ),
    Chain(
        69,
        "Collections & Cash Flow",
        "Advance & Pre-closure Collections",
        (
            "How much principal has been collected ahead of scheduled due dates?",
            "How many loan accounts have prepaid their principal in full this year?",
            "What is the total value of pre-closed loans?",
            "Which schemes experience the highest rate of prepayment?",
            "Which branch has the highest volume of early repayments?",
        ),
    ),
    Chain(
        70,
        "Collections & Cash Flow",
        "Repayment Event Counts & Frequency",
        (
            "How many repayment events have been recorded this financial year?",
            "What is the average repayment collection amount per event?",
            "Show the distribution of repayments across days of the month.",
            "What percentage of repayments are collected in the first 10 days of the month?",
            "Which branch records the highest daily repayment event count?",
        ),
    ),
    Chain(
        71,
        "Collections & Cash Flow",
        "Branch Collection Efficiency Rankings",
        (
            "Rank all branches by collection efficiency this month.",
            "Which branches achieved collection efficiency above 95%?",
            "Which branches fell below 85% collection efficiency?",
            "For the lowest branch, what was the total shortfall in rupees?",
            "Show the top 5 overdue borrowers in that underperforming branch.",
        ),
    ),
    Chain(
        72,
        "Collections & Cash Flow",
        "Scheme Collection Efficiency Dynamics",
        (
            "Compare collection efficiency across all active schemes this month.",
            "Which scheme has the highest collection efficiency?",
            "Which scheme has the lowest collection efficiency?",
            "What is the total overdue amount in that lowest-efficiency scheme?",
            "How has that scheme's efficiency trended over the last 3 months?",
        ),
    ),
    Chain(
        73,
        "Collections & Cash Flow",
        "Overdue Interest Recovery",
        (
            "What is the total overdue interest amount currently outstanding?",
            "Break down overdue interest by branch.",
            "Which 10 borrowers have the highest overdue interest amounts?",
            "How many months have these borrowers failed to pay interest?",
            "What is their total principal outstanding?",
        ),
    ),
    Chain(
        74,
        "Collections & Cash Flow",
        "Recovery on Written-Off or NPA Loans",
        (
            "How much money has been recovered on NPA accounts this year?",
            "Break down NPA recovery into principal and charges.",
            "Which branch led in NPA recoveries?",
            "How many NPA accounts made at least one repayment this quarter?",
            "What is the remaining principal balance on those recovering accounts?",
        ),
    ),
    Chain(
        75,
        "Collections & Cash Flow",
        "EMI Bounce & Arrears Inflow",
        (
            "How many scheduled instalments were unpaid on their due date this month?",
            "What is the total value of these missed instalments?",
            "Break down missed instalments by scheme.",
            "Which branch had the highest count of unpaid instalments?",
            "How many of these accounts have missed two consecutive instalments?",
        ),
    ),
    Chain(
        76,
        "Collections & Cash Flow",
        "Weighted Average Repayment Tenure",
        (
            "What is the weighted average repayment tenure of the active loan book?",
            "How does average repayment tenure vary across branches?",
            "Which schemes have the fastest capital turnover?",
            "What is the monthly principal amortization run rate?",
            "At the current repayment rate, how many months will it take to recover 50% of the portfolio?",
        ),
    ),
    # =========================================================================
    # Domain 8: Delinquency, DPD Buckets & Portfolio at Risk (Chains 77 - 88)
    # =========================================================================
    Chain(
        77,
        "Delinquency & PAR",
        "PAR 30 & Overdue Portfolio Scale",
        (
            "What is our current PAR 30 ratio?",
            "Break PAR 30 down by scheme.",
            "Now show PAR 30 by application branch.",
            "What is our current PAR 90 ratio?",
            "Which schemes have the highest overdue principal?",
        ),
    ),
    Chain(
        78,
        "Delinquency & PAR",
        "Complete DPD Bucket Distribution",
        (
            "Break down the outstanding portfolio by DPD bucket.",
            "Show account count in each DPD bucket: Current, 1-30, 31-60, 61-90, 90+.",
            "What is the total principal outstanding in the 90+ DPD bucket?",
            "What percentage of the overall loan book is in the 90+ DPD bucket?",
            "Which branch holds the largest share of 90+ DPD accounts?",
        ),
    ),
    Chain(
        79,
        "Delinquency & PAR",
        "Early Warning Signals (1-30 DPD)",
        (
            "How many accounts are currently in the 1-30 DPD bucket?",
            "What is the total principal balance of these early delinquency loans?",
            "Break down 1-30 DPD accounts by scheme.",
            "Which branch has the highest count of 1-30 DPD borrowers?",
            "List the top 10 largest principal balances in the 1-30 DPD bucket.",
        ),
    ),
    Chain(
        80,
        "Delinquency & PAR",
        "Mid-Stage Delinquency (31-60 DPD)",
        (
            "What is the total overdue amount in the 31-60 DPD bucket?",
            "How many distinct borrowers are in this bucket?",
            "Compare 31-60 DPD principal balance between gold loans and business loans.",
            "Which branches have more than 5 accounts in 31-60 DPD?",
            "Show the borrower names and overdue days for those accounts.",
        ),
    ),
    Chain(
        81,
        "Delinquency & PAR",
        "Late-Stage Pre-NPA Stress (61-90 DPD)",
        (
            "How many accounts are in the 61-90 DPD bucket right now?",
            "What is their total principal outstanding?",
            "What is their total overdue principal amount?",
            "Break down 61-90 DPD loans by scheme.",
            "List the borrower names, account numbers, and branches for these accounts.",
        ),
    ),
    Chain(
        82,
        "Delinquency & PAR",
        "DPD Migration & Roll-Forward Rates",
        (
            "How many accounts moved from 1-30 DPD to 31-60 DPD this month?",
            "What was the dollar value of loans rolling into higher delinquency?",
            "Did any accounts cure from 31-60 DPD back to Current status?",
            "What was the net flow into delinquent buckets this month?",
            "Which scheme had the worst delinquency roll rate?",
        ),
    ),
    Chain(
        83,
        "Delinquency & PAR",
        "Overdue Principal by Branch",
        (
            "Break down overdue principal amount across all branches.",
            "Rank branches by total overdue principal descending.",
            "What is the overdue ratio for each branch?",
            "Which branch has the worst overdue ratio?",
            "Show the top 5 overdue borrowers in that branch.",
        ),
    ),
    Chain(
        84,
        "Delinquency & PAR",
        "Overdue Principal by Lending Scheme",
        (
            "Show total overdue principal amount for each lending scheme.",
            "Which 3 schemes account for the majority of overdue debt?",
            "What is the total sanctioned amount of those 3 delinquent schemes?",
            "What is their average interest rate?",
            "Show the distribution of accounts across DPD buckets for these schemes.",
        ),
    ),
    Chain(
        85,
        "Delinquency & PAR",
        "Borrower Delinquency Concentration",
        (
            "Who are the top 10 borrowers with the highest overdue amounts?",
            "Show their loan account numbers, branches, and days past due.",
            "What is their combined total overdue amount?",
            "What is their total sanctioned loan amount?",
            "Are all their linked accounts delinquent or only specific ones?",
        ),
    ),
    Chain(
        86,
        "Delinquency & PAR",
        "30-Day Trend in PAR 30",
        (
            "How has PAR 30 moved over the last three months?",
            "Show the month-by-month PAR 30 percentage.",
            "In which month was PAR 30 at its lowest?",
            "Did the absolute dollar value of PAR 30 increase or decrease?",
            "Which branch drove the largest change in PAR 30?",
        ),
    ),
    Chain(
        87,
        "Delinquency & PAR",
        "High-Risk Vintage Analysis",
        (
            "What is the PAR 30 ratio for loans sanctioned in FY25 versus FY26?",
            "Which sanction quarter has the highest delinquency today?",
            "What is the total outstanding balance of that stressed cohort?",
            "Which schemes were predominantly disbursed in that cohort?",
            "How many accounts from that cohort have reached 90+ DPD?",
        ),
    ),
    Chain(
        88,
        "Delinquency & PAR",
        "Secured vs Unsecured Delinquency",
        (
            "Compare delinquency rates between secured gold loans and business loans.",
            "What is the total overdue principal in gold loans?",
            "What is the total overdue principal in business loans?",
            "Which category has more accounts exceeding 60 DPD?",
            "What is the average overdue ticket size in each category?",
        ),
    ),
    # =========================================================================
    # Domain 9: Asset Quality, Sub-Standard & NPA Profiling (Chains 89 - 96)
    # =========================================================================
    Chain(
        89,
        "Asset Quality & NPA",
        "Overall NPA Ratio & Scale",
        (
            "What is our current NPA ratio?",
            "Break it down by scheme.",
            "Now show it by application branch.",
            "Which borrowers have the highest NPA principal outstanding?",
            "How many accounts are currently classified as NPA?",
        ),
    ),
    Chain(
        90,
        "Asset Quality & NPA",
        "Asset Classification Distribution",
        (
            "Show the distribution of active loan accounts by asset classification.",
            "How many accounts are Standard, Sub-Standard, Doubtful, or Loss?",
            "What is the total principal outstanding in Standard accounts?",
            "What is the total principal outstanding in Sub-Standard accounts?",
            "What percentage of the overall loan book is non-standard?",
        ),
    ),
    Chain(
        91,
        "Asset Quality & NPA",
        "Sub-Standard Accounts Deep Dive",
        (
            "List all accounts currently classified as Sub-Standard.",
            "Include borrower name, branch, sanctioned amount, and principal outstanding.",
            "What is the total outstanding balance across Sub-Standard accounts?",
            "Which branch has the highest concentration of Sub-Standard debt?",
            "What is the average DPD of these Sub-Standard loans?",
        ),
    ),
    Chain(
        92,
        "Asset Quality & NPA",
        "NPA Movement & Slippages",
        (
            "How many accounts slipped into NPA this financial year?",
            "What was the total principal balance of new NPA slippages?",
            "Which month recorded the highest number of NPA slippages?",
            "Which scheme experienced the most NPA slippages?",
            "What was the average ticket size of accounts that slipped into NPA?",
        ),
    ),
    Chain(
        93,
        "Asset Quality & NPA",
        "NPA Resolution & Upgrades",
        (
            "Have any NPA accounts been upgraded back to Standard this year?",
            "How much principal was recovered from upgraded accounts?",
            "What is the net change in NPA principal balance this financial year?",
            "Break down net NPA change by branch.",
            "Which branch achieved the largest reduction in NPA accounts?",
        ),
    ),
    Chain(
        94,
        "Asset Quality & NPA",
        "Top NPA Borrowers Analysis",
        (
            "Rank the top 10 NPA borrowers by principal outstanding.",
            "Show their loan account numbers, home branches, and sanction dates.",
            "What is their total combined principal outstanding?",
            "How much interest is overdue on these 10 accounts?",
            "When was the last payment recorded for each of these borrowers?",
        ),
    ),
    Chain(
        95,
        "Asset Quality & NPA",
        "Branch NPA League Table",
        (
            "Rank branches by NPA ratio descending.",
            "Which branch has the highest NPA ratio?",
            "What is that branch's total principal outstanding?",
            "How many individual accounts are in NPA in that branch?",
            "List the borrower names for those NPA accounts.",
        ),
    ),
    Chain(
        96,
        "Asset Quality & NPA",
        "Scheme NPA Vulnerability",
        (
            "Which lending scheme has the highest NPA ratio?",
            "What is the total NPA principal amount in that scheme?",
            "What was the original sanctioned amount for those NPA loans?",
            "What was the average interest rate charged on those NPA loans?",
            "Compare that scheme's NPA ratio with the overall loan book average.",
        ),
    ),
    # =========================================================================
    # Domain 10: Executive Cross-Functional & Audit Worklists (Chains 97 - 100)
    # =========================================================================
    Chain(
        97,
        "Audit & Worklists",
        "High-Exposure Borrower Portfolio Review",
        (
            "Find borrowers with total sanctioned amount greater than 25 lakhs across all loans.",
            "How many such high-exposure borrowers exist?",
            "What is their total combined principal outstanding?",
            "Show their home branches and linked agent names.",
            "Are any of these high-exposure borrowers currently in arrears?",
        ),
    ),
    Chain(
        98,
        "Audit & Worklists",
        "Zero-Disbursement Sanction Audit",
        (
            "List all sanctioned loan accounts where disbursed amount is zero.",
            "How many such zero-disbursement accounts exist in the system?",
            "What is the total sanctioned amount locked in these accounts?",
            "Break down zero-disbursement accounts by branch.",
            "How many of these sanctions are older than 90 days?",
        ),
    ),
    Chain(
        99,
        "Audit & Worklists",
        "High-Interest Short-Tenure Stress Review",
        (
            "Find active loans with interest rate above 16% and tenure under 24 months.",
            "What is the total principal outstanding of these loans?",
            "What is their current collection efficiency?",
            "How many of these loans are currently in 30+ DPD?",
            "Show the borrower names and overdue balances.",
        ),
    ),
    Chain(
        100,
        "Audit & Worklists",
        "Executive Loan Book Master Health Check",
        (
            "Summarize total sanctioned amount, total disbursed amount, and total principal outstanding.",
            "What is the overall sanction-to-disbursement conversion rate?",
            "What is the current collection efficiency for the loan book?",
            "What is our current PAR 30 and NPA ratio?",
            "Rank the top 5 branches by overall portfolio quality.",
        ),
    ),
)
