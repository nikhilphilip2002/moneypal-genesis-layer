# How to Export Data from Tally — Step by Step

This is a simple walkthrough for someone who is not a developer. It explains how to open the GICC company in Tally and save out the 5-6 reports Genesis needs.

**Why this is needed:** the file you gave us (`GICC-Tally.zip`) is Tally's own internal storage — the same files Tally uses when it opens a company, not something a computer program can read directly. We need to open it *inside Tally* and use Tally's "Export" feature to turn each report into a plain file (XML) that our system can read.

---

## What you'll need

- Tally Prime installed on a Windows computer (this must be done on a machine with Tally installed — it will not work from a Mac/Linux laptop without Tally).
- The `GICC-Tally.zip` file, unzipped to a folder you can find easily, e.g. `D:\GICC-Tally\`.

---

## Step 1 — Unzip the file

Right-click `GICC-Tally.zip` → **Extract All** → choose a simple folder location like `D:\GICC-Tally\`.

You'll see 5 sub-folders with number names (like `100000`, `100001`, etc.) — these are 5 different "companies" stored in the same data file. We'll figure out which one is GICC in the next step.

---

## Step 2 — Open the company in Tally

1. Open **Tally Prime**.
2. Press **Alt+K** (or click "Company" at the top) → choose **Select Company**.
3. Browse to the folder you unzipped, e.g. `D:\GICC-Tally\`.
4. Tally will show you a list of companies found in that folder (one per numbered sub-folder).
5. Open each one and check the company name shown at the top of the screen, until you find the one named **GICC** (or similar).

**Note:** the first time you open this data, Tally may say it needs to "upgrade" the data to the current version. This is normal and safe to allow — say yes.

### Confirmed (from screenshots, 15-07-2026)

The correct company has already been located and opened. It is named:

**"GENERAL INVESTMENT & COMMERCIAL CORPORATION LTD"** — this is GICC.

There are actually **3 entries** on the company selection screen:

| Company shown | Last entry date |
|---|---|
| GENERAL INVESTEMENT & COMMERCIAL CORPORATION LTD | 30-Jun-26 |
| GENERAL INVESTMENT & COMMERCIAL CORPORATION LTD | 30-Jun-26 |
| GENERAL INVESTMENT & COMMERCIAL CORPORATION LTD, **Udupi** | 13-Jul-26 |

The one with **"Udupi"** in the name looks like a single-branch company file, not the full organization. **Export from one of the two main (non-Udupi) entries**, unless you're specifically told the client wants Udupi-branch-only data. If unsure which of the two identically-named main entries is correct, open both and check which one actually has data in it (Trial Balance not blank) before exporting.

---

## Step 3 — Set the date to 30-June-2026

Because our other system (Prosper) has data as on **30 June 2026**, we want Tally's reports to match that exact date.

1. Press **F2** (Change Period) or look for "Period" at the top.
2. Set the "to" date to **30-Jun-2026**.

(The company's financial year is currently showing as `1-Apr-26 to 31-Mar-27` — that's fine to leave as is. It's just the outer year; you only need to change the "as on"/closing date used by each individual report to 30-Jun-2026, as described in Step 4 below.)

---

## Step 4 — Export each report

Do this once for each of the 6 reports below. The steps are the same every time:

1. Go to the report using the menu path listed.
2. Press **Alt+E** (Export).
3. In the export box that appears:
   - **Format:** choose **XML (Data Interchange)**. (If XML isn't available for that particular report, choose **Excel** instead.)
   - Leave everything else as default.
4. Click **Export** — Tally will ask where to save the file. Save all 6 files into one folder, e.g. `D:\GICC-Tally-Export\`, and give each a clear name (see table).

| # | Report | Where to find it (menu path) | Save as |
|---|---|---|---|
| 1 | Chart of Accounts | Gateway of Tally → **CHart of Accounts** (visible directly on the main menu, under MASTERS) | `01_ChartOfAccounts.xml` |
| 2 | Trial Balance | Gateway of Tally → **Display More Reports** → Trial Balance | `02_TrialBalance.xml` |
| 3 | Day Book / Journal Entries | Gateway of Tally → **Day Book** (under TRANSACTIONS; set the date range from 1-Apr-2026 to 30-Jun-2026) | `03_DayBook.xml` |
| 4 | Profit & Loss Account | Gateway of Tally → **Profit & Loss A/c** (under REPORTS) | `04_ProfitAndLoss.xml` |
| 5 | Balance Sheet | Gateway of Tally → **Balance Sheet** (under REPORTS) | `05_BalanceSheet.xml` |
| 6 | All Vouchers / Financial Transactions | Gateway of Tally → **Display More Reports** → Statements of Accounts → Ledger (all ledgers, full period) | `06_AllTransactions.xml` |

All 5 of the first-level items above (Chart of Accounts, Day Book, Balance Sheet, Profit & Loss A/c, Display More Reports) are visible directly on the Gateway of Tally main menu — no need to hunt through submenus for those.

---

## Step 5 — Send us the exported folder

Once all 6 files are saved in one folder, zip that folder up (`D:\GICC-Tally-Export\` → right-click → "Send to → Compressed (zipped) folder") and share the zip with us, the same way you shared the original one.

---

## A quick sanity check before you send it

Open **02_TrialBalance.xml** or the Excel version in Excel/Notepad — the numbers should look like real account balances (not all zeros), and the total debits should equal the total credits (that's how a trial balance always balances). If it looks empty or clearly wrong, the date range or company selected in Step 2/3 is probably off — go back and check those before exporting again.

---

## If something goes wrong

- **"Company not found" / nothing shows in Step 2:** the folder path is wrong, or the zip didn't fully extract. Re-extract and try again.
- **Numbers look empty for the whole period:** double check you selected the *correct* company folder (there were 5 in the zip) and the date range covers when the business was actually operating.
- **Not sure which company is GICC:** open each of the 5 briefly, the company name is always shown at the top-left once it's loaded — don't rely on folder size alone.

If you get stuck at any step, send a screenshot of what you're seeing and we'll help from there.
