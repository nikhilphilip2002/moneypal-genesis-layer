# Tally Prime Programmatic Data Export Guide (XML, JSON, CSV)

This guide outlines how to programmatically and automatically export the entire Tally database (extracted from `GICC-Tally.zip` into TallyPrime) into structured XML, JSON, or CSV formats. 

These steps directly support **Module 1 (Economic Intelligence dashboards)** of the [GENESIS_SPRINT1_BUILD_PLAN.md](file:///home/null/Projects/moneypal/docs/GENESIS_SPRINT1_BUILD_PLAN.md) where the Ingestion Lead (DE1) must parse Tally data and import it into a PostgreSQL database.

---

## Background & Context

In `docs/GENESIS_SPRINT1_BUILD_PLAN.md`, we established that:
* Tally data consists of 5-6 core exports (Chart of Accounts, Trial Balance, Day Book/Journal Entries, Profit & Loss, Balance Sheet, and Vouchers).
* The ingestion pipeline targets **JSON** (or alternatively XML/CSV) for programmatic parsing.
* Standard manual exporting (using Alt+E in the Tally GUI) works but is time-consuming and prone to human error.

To automate this, Tally offers three programmatic access vectors:
1. **XML API via HTTP POST** (Most reliable and doesn't require modifying local configuration)
2. **TDL (Tally Definition Language) Customization Script** (For adding an export button directly to the Tally GUI)
3. **ODBC Database Interface** (For executing SQL queries like `SELECT * FROM Ledger` directly against Tally)

---

## Method 1: Tally XML API (Recommended Programmatic Route)

Tally Prime acts as an HTTP server that listens on a local port (default is `9000`). By sending XML POST requests containing inline TDL definitions, external scripts can query and retrieve any data collection (Ledgers, Vouchers, Groups, etc.) in raw XML or JSON.

### Step 1: Enable the HTTP Server in Tally Prime
1. Open **Tally Prime** and load the company: **GENERAL INVESTMENT & COMMERCIAL CORPORATION LTD**.
2. Go to **F1: Help** → **Settings** → **Connectivity**.
3. Under **Client/Server Configuration**, verify:
   * **TallyPrime acting as:** `Both` (or `Server`)
   * **Enable Services:** `Yes`
   * **Port:** `9000` (make note if it is different, e.g., `9000`)
4. Save the configuration and restart Tally Prime if prompted.

### Step 2: Formulate the XML API Requests
Here are the standard XML payloads to query and fetch all Ledgers (Masters) and Vouchers (Transactions) using inline TDL Collections.

#### A. Fetch All Ledgers (Masters)
Save the following as `fetch_ledgers.xml`:
```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>COLLECTION</TYPE>
    <ID>AllLedgers</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
      <TDL>
        <TDLOBJECTS>
          <COLLECTION NAME="AllLedgers">
            <TYPE>Ledger</TYPE>
            <!-- Fetch all native properties -->
            <FETCH>*</FETCH> 
          </COLLECTION>
        </TDLOBJECTS>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

#### B. Fetch All Vouchers (Transactions) for 30-Jun-2026 Snapshot
Save the following as `fetch_vouchers.xml`. Note the date range variables (`SVFROMDATE` and `SVTODATE`) formatted as `YYYYMMDD`:
```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>COLLECTION</TYPE>
    <ID>AllVouchers</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        <!-- Period range matching the 30-Jun-2026 snapshot -->
        <SVFROMDATE>20260401</SVFROMDATE>
        <SVTODATE>20260630</SVTODATE>
      </STATICVARIABLES>
      <TDL>
        <TDLOBJECTS>
          <COLLECTION NAME="AllVouchers">
            <TYPE>Voucher</TYPE>
            <!-- Fetch all voucher details and internal ledger entries -->
            <FETCH>*</FETCH>
          </COLLECTION>
        </TDLOBJECTS>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

### Step 3: Run the Python Extraction Script
Use the following Python script to communicate with Tally, fetch the XML data, and output JSON or XML files.

Ensure you install requirements: `pip install requests xmltodict`

```python
import os
import json
import requests
import xmltodict

TALLY_URL = "http://localhost:9000"
HEADERS = {"Content-Type": "text/xml;charset=utf-16"}

def query_tally(xml_payload_path, output_filename, convert_to_json=True):
    if not os.path.exists(xml_payload_path):
        print(f"Error: Payload file '{xml_payload_path}' not found.")
        return

    with open(xml_payload_path, "r", encoding="utf-8") as f:
        xml_data = f.read()

    print(f"Sending request to Tally for {output_filename}...")
    try:
        response = requests.post(TALLY_URL, data=xml_data, headers=HEADERS)
        if response.status_code == 200:
            raw_xml = response.text
            
            # Save raw XML
            xml_out = output_filename + ".xml"
            with open(xml_out, "w", encoding="utf-8") as x_file:
                x_file.write(raw_xml)
            print(f"Successfully saved XML to: {xml_out}")

            # Save converted JSON (for Genesis parser ingest)
            if convert_to_json:
                json_out = output_filename + ".json"
                try:
                    # Parse XML to dictionary
                    data_dict = xmltodict.parse(raw_xml)
                    with open(json_out, "w", encoding="utf-8") as j_file:
                        json.dump(data_dict, j_file, indent=2)
                    print(f"Successfully saved converted JSON to: {json_out}")
                except Exception as ex:
                    print(f"Failed to convert XML to JSON: {ex}")
        else:
            print(f"Server Error: HTTP {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"Failed to connect to Tally Prime at {TALLY_URL}. Is Tally running and server enabled?")

if __name__ == "__main__":
    # Fetch Ledgers
    query_tally("fetch_ledgers.xml", "01_Ledgers_Export")
    
    # Fetch Vouchers
    query_tally("fetch_vouchers.xml", "03_Vouchers_Export")
```

---

## Method 2: Custom TDL Script (Gateway of Tally Integration)

If you prefer a button inside Tally Prime that exports data to a CSV/XML file on the local disk without running scripts, you can load a custom TDL.

### Step 1: Write the TDL script
Create a file named `export_button.txt` and copy this TDL structure:

```tdl
[#Menu: Gateway of Tally]
    Add: Key Item: @@LocExportText : E : Call: GenesisBulkExportReport

[Report: GenesisBulkExportReport]
    Form: GenesisBulkExportForm

[Form: GenesisBulkExportForm]
    Parts: GenesisBulkExportPart
    Button: GenesisExportCSVBtn

[Part: GenesisBulkExportPart]
    Lines: GenesisBulkExportLine

[Line: GenesisBulkExportLine]
    Fields: GenesisBulkExportTitle

[Field: GenesisBulkExportTitle]
    Set as: "Genesis intelligence Bulk Export Panel"
    Info: "Press Alt+E to trigger batch export or click the button."

;; Export configuration
[Button: GenesisExportCSVBtn]
    Key: Alt + C
    Action: Export Report: Day Book
    Title: "Export Daybook to CSV"
    ;; Define static export format variables
    Set: SVEXPORTFORMAT: $$SysName:ASCIIChar
    Set: SVFILENAME: "D:\GICC-Tally-Export\03_DayBook.csv"
```

### Step 2: Load the TDL into Tally Prime
1. Go to **F1: Help** → **TDLs & Add-Ons**.
2. Press **F4: Manage Local TDLs**.
3. Set **Load selected TDL files on startup** to `Yes`.
4. In the file selection, browse to or paste the absolute path of `export_button.txt`.
5. Press **Ctrl+A** to save.
6. A new menu item "GenesisBulkExportReport" will appear on the **Gateway of Tally**.

---

## Method 3: ODBC Database Interface (Query Tally like SQL)

Tally Prime acts as an ODBC (Open Database Connectivity) server. You can query the database directly using Python to extract data directly to CSV.

### Step 1: Verify ODBC configuration
In **Tally Prime**, verify under **Help** → **Settings** → **Connectivity** that ODBC is enabled. By default, Tally listens on port `9000` via ODBC.

### Step 2: Python ODBC script to CSV
Ensure you have the Python package `pyodbc` installed and have the Tally ODBC driver installed on your machine (usually bundled with Tally installation).

```python
import pyodbc
import csv

# Connect to Tally ODBC (Port 9000)
conn_str = (
    "Driver={Tally ODBC Driver};"
    "Server=localhost;"
    "Port=9000;"
)

try:
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    # Query Ledger Master Table
    cursor.execute("SELECT $Name, $Parent, $OpeningBalance, $ClosingBalance FROM Ledger")
    rows = cursor.fetchall()
    
    # Write to CSV
    with open("01_ChartOfAccounts.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # Headers
        writer.writerow(["Ledger Name", "Parent Group", "Opening Balance", "Closing Balance"])
        # Data
        for row in rows:
            writer.writerow(row)
            
    print("Exported Ledgers to 01_ChartOfAccounts.csv successfully!")
    
except Exception as e:
    print(f"Error querying Tally ODBC: {e}")
```

---

## Verification & Sanity Checks

1. **Verify Company Selection:** Ensure Tally has loaded **GENERAL INVESTMENT & COMMERCIAL CORPORATION LTD** (and not the Udupi branch or blank companies) prior to running the queries/scripts.
2. **Check Date Ranges:** If the data is empty or returns zeros, double-check that the `SVFROMDATE` and `SVTODATE` cover the correct operating dates (typically `1-Apr-2026` to `30-Jun-2026` for this sprint).
3. **Verify Balance Equation:** Summing up the debits and credits of your export should balance.
