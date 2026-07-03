"""Curated, high-priority regulatory alerts for the dashboard widget (no RAG)."""

ALERTS = [
    {
        "title": "Digital Lending LSP Agreements Review Due",
        "category": "digital_lending",
        "severity": "high",
        "summary": "RBI requires all NBFC-LSP agreements to include specific data-privacy and grievance clauses.",
        "action": "Review all Lending Service Provider contracts for compliance before the next board meeting.",
        "source_url": "https://rbi.org.in/Scripts/BS_ViewMasterDirections.aspx?id=12256",
        "ai_note": "From RBI Digital Lending Guidelines 2022; dates sourced from the circular.",
    },
    {
        "title": "KYC Refresh — Periodic CDD Required",
        "category": "kyc_aml",
        "severity": "high",
        "summary": "Periodic re-KYC is mandated for all customers based on risk categorisation.",
        "action": "Audit the customer KYC database and schedule re-KYC for overdue accounts.",
        "source_url": "https://rbi.org.in/",
        "ai_note": "From RBI KYC Master Directions; cadence is AI-interpreted from the circular.",
    },
    {
        "title": "Cyber Incident Reporting — 2-Hour Window",
        "category": "information_security",
        "severity": "high",
        "summary": "Major cyber-security incidents must be reported to RBI within 2-6 hours of detection.",
        "action": "Verify the incident-response procedure includes the RBI reporting step within the window.",
        "source_url": "https://rbi.org.in/",
        "ai_note": "From RBI Information Security directions; reporting window sourced from the regulation.",
    },
    {
        "title": "Key Fact Statement Mandatory for All Loans",
        "category": "digital_lending",
        "severity": "medium",
        "summary": "Every disbursement must be preceded by a KFS disclosing APR, fees and all charges.",
        "action": "Update the loan-origination workflow to generate and capture KFS acknowledgment.",
        "source_url": "https://rbi.org.in/Scripts/BS_ViewMasterDirections.aspx?id=12256",
        "ai_note": "From RBI Digital Lending Guidelines 2022.",
    },
    {
        "title": "Board Approval for IT Security Policy",
        "category": "information_security",
        "severity": "medium",
        "summary": "All NBFCs must have a board-approved Information Security policy on record.",
        "action": "Place the Information Security policy on the next board agenda for formal approval.",
        "source_url": "https://rbi.org.in/",
        "ai_note": "From RBI Information Security directions; board-approval requirement is explicit.",
    },
]
