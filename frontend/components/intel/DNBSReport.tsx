'use client';

import { useEffect, useState } from 'react';
import { regulatory, type DNBS02ReportData, type DNBS02Periods } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent } from '@/components/ui/tabs';
import LoadingCard from '@/components/intel/LoadingCard';
import WidgetError from '@/components/intel/WidgetError';
import {
  Download,
  FileSpreadsheet,
  RefreshCw,
  Landmark,
  ShieldCheck,
  TrendingUp,
  AlertCircle,
  Database,
  Building2,
  Users,
  ChevronDown,
  Calendar,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// Monthly options are loaded from the API so the picker can only offer periods the
// warehouse actually holds a snapshot for. Quarterly and yearly remain static because
// they additionally depend on a period-end snapshot landing on the quarter/year end.
const PERIOD_OPTIONS = {
  monthly: [] as { label: string; value: string }[],
  quarterly: [
    { label: 'Q1 FY26 (Apr - Jun 2026)', value: '2026-Q1' },
    { label: 'Q4 FY25 (Jan - Mar 2026)', value: '2025-Q4' },
    { label: 'Q3 FY25 (Oct - Dec 2025)', value: '2025-Q3' },
    { label: 'Q2 FY25 (Jul - Sep 2025)', value: '2025-Q2' },
    { label: 'Q1 FY25 (Apr - Jun 2025)', value: '2025-Q1' },
  ],
  yearly: [
    { label: 'FY 2025-2026 (Annual Return)', value: '2025-2026' },
    { label: 'FY 2024-2025 (Annual Return)', value: '2024-2025' },
  ],
};

const REPORT_SECTION_OPTIONS = [
  { value: 'part1', label: 'Part 1: Capital Structure & Net Owned Funds (NOF)' },
  { value: 'part2', label: 'Part 2: Loan Assets & Receivables Maturity Profile' },
  { value: 'part3', label: 'Part 3: Revenue & Operating Profitability' },
  { value: 'part6', label: 'Part 6: Sensitive Sector Exposures & Risk Weights' },
  { value: 'part8', label: 'Part 8C: Asset Classification & Provisioning' },
  { value: 'part8a', label: 'Part 8A: MSME Credit Profile Breakdown' },
  { value: 'annex2', label: 'Annexure 2: Shareholding Pattern & Ownership' },
  { value: 'annex9', label: 'Annexure 9: Top 25 Borrowers Exposure' },
  { value: 'annex10', label: 'Annexure 10: Top 25 Investments Portfolio' },
  { value: 'annex13', label: 'Annexure 13: District Branch Network Operations' },
];

export default function DNBSReport() {
  const [frequency, setFrequency] = useState<'monthly' | 'quarterly' | 'yearly' | 'custom'>('monthly');
  const [period, setPeriod] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [periods, setPeriods] = useState<DNBS02Periods | null>(null);
  const [report, setReport] = useState<DNBS02ReportData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeSubTab, setActiveSubTab] = useState<string>('part1');

  // Discover reportable periods first, then default to the most recent one.
  useEffect(() => {
    let cancelled = false;
    regulatory
      .dnbsPeriods()
      .then((p) => {
        if (cancelled) return;
        setPeriods(p);
        const latest = p.monthly[0];
        if (latest) {
          setPeriod(latest.value);
          setStartDate(`${latest.value}-01`);
          setEndDate(latest.end_date);
        } else {
          setError('The warehouse holds no portfolio snapshots to report on.');
          setLoading(false);
        }
      })
      .catch((err: any) => {
        if (!cancelled) {
          setError(err?.message || 'Failed to load reportable periods');
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const fetchReport = async () => {
    if (!period && !(startDate && endDate)) return;
    setLoading(true);
    setError(null);
    try {
      const data = await regulatory.dnbsReport(frequency, period, startDate, endDate);
      setReport(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to load DNBS-02 report');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReport();
  }, [frequency, period, startDate, endDate]);

  const periodOptions =
    frequency === 'monthly'
      ? (periods?.monthly ?? []).map((m) => ({ label: `${m.label} (${m.value})`, value: m.value }))
      : frequency === 'custom'
        ? []
        : PERIOD_OPTIONS[frequency];

  const handleFrequencyChange = (newFreq: 'monthly' | 'quarterly' | 'yearly' | 'custom') => {
    setFrequency(newFreq);
    if (newFreq !== 'custom') {
      const opts = newFreq === 'monthly' ? (periods?.monthly ?? []) : PERIOD_OPTIONS[newFreq];
      const p = opts[0]?.value;
      if (p) {
        setPeriod(p);
        updateDatesForPeriod(newFreq, p);
      }
    }
  };

  const updateDatesForPeriod = (freq: string, p: string) => {
    if (freq === 'monthly') {
      const [y, m] = p.split('-');
      const lastDay = new Date(parseInt(y), parseInt(m), 0).getDate();
      setStartDate(`${y}-${m.padStart(2, '0')}-01`);
      setEndDate(`${y}-${m.padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`);
    } else if (freq === 'quarterly') {
      const [yStr, q] = p.split('-');
      const y = parseInt(yStr);
      if (q === 'Q1') { setStartDate(`${y}-04-01`); setEndDate(`${y}-06-30`); }
      else if (q === 'Q2') { setStartDate(`${y}-07-01`); setEndDate(`${y}-09-30`); }
      else if (q === 'Q3') { setStartDate(`${y}-10-01`); setEndDate(`${y}-12-31`); }
      else if (q === 'Q4') { setStartDate(`${y + 1}-01-01`); setEndDate(`${y + 1}-03-31`); }
    } else if (freq === 'yearly') {
      const [y1, y2] = p.split('-');
      setStartDate(`${y1}-04-01`);
      setEndDate(`${y2}-03-31`);
    }
  };

  const handlePeriodChange = (newPeriod: string) => {
    setPeriod(newPeriod);
    if (frequency !== 'custom') {
      updateDatesForPeriod(frequency, newPeriod);
    }
  };

  const handleCustomStartDateChange = (val: string) => {
    setStartDate(val);
    setFrequency('custom');
  };

  const handleCustomEndDateChange = (val: string) => {
    setEndDate(val);
    setFrequency('custom');
  };

  const handleExcelDownload = () => {
    const url = regulatory.getDnbsExcelUrl(frequency, period, startDate, endDate);
    window.open(url, '_blank');
  };

  return (
    <div className="space-y-6">
      {/* Controls Bar */}
      <Card className="dashboard-surface rounded-[1.5rem] border-border/70 p-4 md:p-6 shadow-none">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="h-5 w-5 text-primary" />
                <h2 className="text-lg font-semibold tracking-tight">RBI DNBS Report Generator</h2>
                {/* Reflects per-section provenance, not merely whether a connection opened. */}
                {report && (report.is_live_pg ? (
                  <Badge variant="outline" className="gap-1 bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400 border-none text-[11px]">
                    <Database className="h-3 w-3" /> All sections live
                  </Badge>
                ) : (
                  <Badge variant="outline" className="gap-1 bg-amber-500/10 text-amber-600 dark:bg-amber-500/20 dark:text-amber-400 border-none text-[11px]">
                    <AlertCircle className="h-3 w-3" />
                    {report.live_sections.length} live / {report.degraded_sections.length} unavailable
                  </Badge>
                ))}
                {report && (
                  <Badge variant="outline" className="gap-1 text-[11px] bg-primary/10 text-primary border-none">
                    📅 {report.start_date} to {report.end_date} ({report.duration_days ?? 31} Days)
                  </Badge>
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                Programmatic return mapping for Important Financial Parameters, Capital Adequacy, Asset Quality, and Top Exposure Annexures.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Button variant="outline" size="sm" onClick={fetchReport} className="h-9 rounded-xl gap-1.5 text-xs">
                <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
                Refresh
              </Button>

              <Button onClick={handleExcelDownload} size="sm" className="h-9 rounded-xl gap-1.5 text-xs bg-primary text-primary-foreground">
                <Download className="h-3.5 w-3.5" />
                Download Excel (.xlsx)
              </Button>
            </div>
          </div>

          {/* Date & Preset Filters Bar - Border-less Card Design Matching Monthly/Quarterly/Yearly Pills */}
          <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-border/40">
            {/* Frequency Selection Group */}
            <div className="inline-flex rounded-xl bg-accent p-1 text-xs">
              {(['monthly', 'quarterly', 'yearly', 'custom'] as const).map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => handleFrequencyChange(f)}
                  className={cn(
                    'rounded-lg px-3 py-1.5 font-medium transition-all capitalize',
                    frequency === f
                      ? 'bg-background text-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                >
                  {f === 'custom' ? 'Custom Range' : f}
                </button>
              ))}
            </div>

            {/* Period Dropdown for Monthly/Quarterly/Yearly */}
            {frequency !== 'custom' && (
              <select
                value={period}
                onChange={(e) => handlePeriodChange(e.target.value)}
                className="h-9 rounded-xl border-0 bg-accent text-foreground px-3 text-xs font-medium focus:outline-none focus:ring-1 focus:ring-primary shadow-none"
              >
                {periodOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            )}

            {/* Custom Date Pickers - Border-less bg-accent design matching toggle pills */}
            <div className="inline-flex items-center gap-2 text-xs font-medium bg-accent rounded-xl p-1">
              <span className="text-[11px] font-semibold text-foreground px-2 flex items-center gap-1">
                <Calendar className="h-3.5 w-3.5 text-primary" /> Date Range:
              </span>
              <div className="flex items-center gap-1.5 bg-background rounded-lg px-2.5 py-1 shadow-sm">
                <span className="text-[11px] text-muted-foreground">From</span>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => handleCustomStartDateChange(e.target.value)}
                  className="h-6 bg-transparent text-xs text-foreground font-mono focus:outline-none"
                />
              </div>
              <div className="flex items-center gap-1.5 bg-background rounded-lg px-2.5 py-1 shadow-sm">
                <span className="text-[11px] text-muted-foreground">To</span>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => handleCustomEndDateChange(e.target.value)}
                  className="h-6 bg-transparent text-xs text-foreground font-mono focus:outline-none"
                />
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Data-quality disclosure. A regulatory return must state what is behind each
          figure and what has no source, rather than presenting gaps as numbers. */}
      {report && (report.degraded_sections.length > 0 || report.coverage?.uncovered_accounts > 0) && (
        <Card className="dashboard-surface rounded-[1.5rem] border-amber-500/40 p-4 md:p-5 shadow-none">
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
            <div className="space-y-3 text-xs">
              <p className="font-semibold text-amber-700 dark:text-amber-400">
                Data limitations for this period
              </p>

              {report.coverage?.uncovered_accounts > 0 && (
                <p className="text-muted-foreground">
                  Point-in-time figures cover{' '}
                  <span className="font-semibold text-foreground">
                    {report.coverage.covered_accounts.toLocaleString('en-IN')} accounts
                    (₹{report.coverage.covered_lakhs.toLocaleString('en-IN')} Lakhs,{' '}
                    {report.coverage.covered_pct}% of the open book)
                  </span>
                  . A further{' '}
                  {report.coverage.uncovered_accounts.toLocaleString('en-IN')} open accounts
                  (₹{report.coverage.uncovered_lakhs.toLocaleString('en-IN')} Lakhs) have no
                  dated snapshot on {report.snapshot_date} and are excluded.
                </p>
              )}

              {/* Sections that did resolve but come with a caveat. */}
              {Object.entries(report.provenance).some(([, v]) => v.note) && (
                <div className="space-y-1">
                  <p className="text-muted-foreground">Sourcing caveats:</p>
                  <ul className="space-y-1">
                    {Object.entries(report.provenance)
                      .filter(([, v]) => v.note)
                      .map(([name, v]) => (
                        <li key={name} className="flex flex-col gap-0.5 sm:flex-row sm:gap-2">
                          <span className="font-mono font-medium shrink-0">{name}</span>
                          <span className="text-muted-foreground">{v.note}</span>
                        </li>
                      ))}
                  </ul>
                </div>
              )}

              {report.degraded_sections.length > 0 && (
                <div className="space-y-1">
                  <p className="text-muted-foreground">
                    These sections have no data behind them and are rendered blank:
                  </p>
                  <ul className="space-y-1">
                    {report.degraded_sections.map((name) => (
                      <li key={name} className="flex flex-col gap-0.5 sm:flex-row sm:gap-2">
                        <span className="font-mono font-medium shrink-0">{name}</span>
                        <span className="text-muted-foreground">
                          {report.provenance[name]?.error || report.provenance[name]?.status}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Main Content States */}
      {loading && <LoadingCard lines={10} />}
      {error && <WidgetError title="DNBS-02 Report Builder" onRetry={fetchReport} />}

      {report && !loading && (
        <div className="space-y-6">
          {/* Executive Summary Cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card className="dashboard-surface rounded-[1.25rem] border-border/70 p-4 shadow-none">
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Total Loan Portfolio</p>
                  <p className="text-xl font-bold tracking-tight">₹{report.summary.total_loan_book.toLocaleString('en-IN')} Lakhs</p>
                  <p className="text-[11px] text-muted-foreground">₹{(report.summary.total_loan_book / 100).toFixed(2)} Crore</p>
                </div>
                <div className="rounded-xl bg-primary/10 p-2 text-primary">
                  <Landmark className="h-5 w-5" />
                </div>
              </div>
            </Card>

            <Card className="dashboard-surface rounded-[1.25rem] border-border/70 p-4 shadow-none">
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Owned Funds</p>
                  <p className="text-xl font-bold tracking-tight">₹{report.summary.owned_funds.toLocaleString('en-IN')} Lakhs</p>
                  <p className="text-[11px] text-muted-foreground">GL trial balance, FY {report.gl_year}</p>
                </div>
                <div className="rounded-xl bg-emerald-500/10 p-2 text-emerald-600 dark:text-emerald-400">
                  <ShieldCheck className="h-5 w-5" />
                </div>
              </div>
            </Card>

            <Card className="dashboard-surface rounded-[1.25rem] border-border/70 p-4 shadow-none">
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Capital Adequacy (CRAR)</p>
                  <p className="text-xl font-bold tracking-tight">
                    {report.summary.crar_pct === null ? '—' : `${report.summary.crar_pct}%`}
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    {report.summary.crar_pct === null
                      ? 'Not derivable: no risk-weighted assets source'
                      : 'Min RBI threshold: 15%'}
                  </p>
                </div>
                <div className="rounded-xl bg-blue-500/10 p-2 text-blue-600 dark:text-blue-400">
                  <TrendingUp className="h-5 w-5" />
                </div>
              </div>
            </Card>

            <Card className="dashboard-surface rounded-[1.25rem] border-border/70 p-4 shadow-none">
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Gross NPA Ratio</p>
                  <p className="text-xl font-bold tracking-tight text-emerald-600 dark:text-emerald-400">{report.summary.gross_npa_pct}%</p>
                  <p className="text-[11px] text-muted-foreground">
                    ₹{report.summary.gross_npa_amount.toLocaleString('en-IN')} Lakhs sub-standard, doubtful &amp; loss
                  </p>
                </div>
                <div className="rounded-xl bg-amber-500/10 p-2 text-amber-600 dark:text-amber-400">
                  <AlertCircle className="h-5 w-5" />
                </div>
              </div>
            </Card>
          </div>

          {/* Clean Dropdown Selection List for Report Sections (Replaces Sliding Tabs Bar) */}
          <Tabs value={activeSubTab} onValueChange={setActiveSubTab} className="w-full">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6 bg-card border border-border/70 rounded-[1.25rem] p-4 shadow-none">
              <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
                <FileSpreadsheet className="h-4.5 w-4.5 text-primary" />
                <span>Select Report Return Section:</span>
              </div>
              <div className="relative flex-1 max-w-lg">
                <select
                  value={activeSubTab}
                  onChange={(e) => setActiveSubTab(e.target.value)}
                  className="w-full h-10 rounded-xl border border-input bg-background pl-3 pr-8 text-xs font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-primary shadow-sm appearance-none cursor-pointer"
                >
                  {REPORT_SECTION_OPTIONS.map((sec) => (
                    <option key={sec.value} value={sec.value}>
                      {sec.label}
                    </option>
                  ))}
                </select>
                <ChevronDown className="h-4 w-4 absolute right-3 top-3 text-muted-foreground pointer-events-none" />
              </div>
            </div>

            {/* Part 1: Capital & Reserves */}
            <TabsContent value="part1">
              <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none overflow-hidden">
                <CardHeader className="border-b border-border/50 bg-muted/30">
                  <CardTitle className="text-sm font-semibold">Part 1: Capital Structure & Net Owned Funds</CardTitle>
                </CardHeader>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-muted/50 text-muted-foreground uppercase font-semibold text-[10px]">
                      <tr>
                        <th className="px-4 py-3">GL Group</th>
                        <th className="px-4 py-3">Particulars</th>
                        <th className="px-4 py-3 text-right">Amount (₹ in Lakhs)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {report.part1_capital.map((row, idx) => (
                        <tr key={idx} className={cn('hover:bg-accent/40', row.gl_group === 'TOTAL' && 'bg-primary/5 font-semibold')}>
                          <td className="px-4 py-3 font-mono">{row.gl_group}</td>
                          <td className="px-4 py-3">{row.particulars}</td>
                          <td className="px-4 py-3 text-right font-mono font-medium">₹{row.amount_lakhs.toLocaleString('en-IN')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </TabsContent>

            {/* Part 2: Loan Assets & Receivables */}
            <TabsContent value="part2">
              <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none overflow-hidden">
                <CardHeader className="border-b border-border/50 bg-muted/30">
                  <CardTitle className="text-sm font-semibold">Part 2: Loan Assets & Receivables Maturity Profile</CardTitle>
                </CardHeader>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-muted/50 text-muted-foreground uppercase font-semibold text-[10px]">
                      <tr>
                        <th className="px-4 py-3">Asset Category / Maturity Bucket</th>
                        <th className="px-4 py-3 text-right">Amount (₹ Lakhs)</th>
                        <th className="px-4 py-3 text-right">Portfolio Share (%)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {report.part2_loans.map((row, idx) => (
                        <tr key={idx} className="hover:bg-accent/40">
                          <td className="px-4 py-3 font-medium">{row.category}</td>
                          <td className="px-4 py-3 text-right font-mono">₹{row.amount_lakhs.toLocaleString('en-IN')}</td>
                          <td className="px-4 py-3 text-right font-mono font-semibold">{row.share_pct}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </TabsContent>

            {/* Part 3: Revenue & PnL */}
            <TabsContent value="part3">
              <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none overflow-hidden">
                <CardHeader className="border-b border-border/50 bg-muted/30">
                  <CardTitle className="text-sm font-semibold">Part 3: Revenue & Operating Profitability</CardTitle>
                </CardHeader>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-muted/50 text-muted-foreground uppercase font-semibold text-[10px]">
                      <tr>
                        <th className="px-4 py-3">Financial Head / Line Item</th>
                        <th className="px-4 py-3 text-right">Amount (₹ in Lakhs)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {report.part3_income.map((row, idx) => (
                        <tr key={idx} className={cn('hover:bg-accent/40', row.head.includes('Net Profit') && 'bg-emerald-500/10 font-semibold text-emerald-700 dark:text-emerald-300')}>
                          <td className="px-4 py-3 font-medium">{row.head}</td>
                          <td className="px-4 py-3 text-right font-mono font-semibold">₹{row.amount_lakhs.toLocaleString('en-IN')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </TabsContent>

            {/* Part 6: Sensitive Sectors */}
            <TabsContent value="part6">
              <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none overflow-hidden">
                <CardHeader className="border-b border-border/50 bg-muted/30">
                  <CardTitle className="text-sm font-semibold">Part 6: Sensitive Sector Exposures & Risk Weights</CardTitle>
                </CardHeader>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-muted/50 text-muted-foreground uppercase font-semibold text-[10px]">
                      <tr>
                        <th className="px-4 py-3">Sector</th>
                        <th className="px-4 py-3">GL Head</th>
                        <th className="px-4 py-3 text-right">Total Exposure (₹ Lakhs)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {report.part6_sensitive.map((row, idx) => (
                        <tr key={idx} className="hover:bg-accent/40">
                          <td className="px-4 py-3 font-medium">{row.sector}</td>
                          <td className="px-4 py-3 text-muted-foreground">{row.particulars}</td>
                          <td className="px-4 py-3 text-right font-mono">₹{row.exposure_lakhs.toLocaleString('en-IN')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </TabsContent>

            {/* Part 8: Asset Quality */}
            <TabsContent value="part8">
              <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none overflow-hidden">
                <CardHeader className="border-b border-border/50 bg-muted/30">
                  <CardTitle className="text-sm font-semibold">Part 8C: Asset Classification & Provisioning</CardTitle>
                </CardHeader>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-muted/50 text-muted-foreground uppercase font-semibold text-[10px]">
                      <tr>
                        <th className="px-4 py-3">Asset Classification Status</th>
                        <th className="px-4 py-3 text-right">Account Count</th>
                        <th className="px-4 py-3 text-right">Outstanding Principal (₹ Lakhs)</th>
                        <th className="px-4 py-3 text-right">Provisions Held (₹ Lakhs)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {report.part8_asset_quality.map((row, idx) => (
                        <tr key={idx} className="hover:bg-accent/40">
                          <td className="px-4 py-3 font-medium">{row.status}</td>
                          <td className="px-4 py-3 text-right font-mono">{row.count.toLocaleString()}</td>
                          <td className="px-4 py-3 text-right font-mono">₹{row.amount_lakhs.toLocaleString('en-IN')}</td>
                          <td className="px-4 py-3 text-right font-mono">₹{row.provision_lakhs.toLocaleString('en-IN')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </TabsContent>

            {/* Part 8A: MSME Credit Profile */}
            <TabsContent value="part8a">
              <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none overflow-hidden">
                <CardHeader className="border-b border-border/50 bg-muted/30">
                  <CardTitle className="text-sm font-semibold">Part 8A: MSME Credit Profile Breakdown</CardTitle>
                </CardHeader>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-muted/50 text-muted-foreground uppercase font-semibold text-[10px]">
                      <tr>
                        <th className="px-4 py-3">MSME Enterprise Category</th>
                        <th className="px-4 py-3 text-right">Account Count</th>
                        <th className="px-4 py-3 text-right">Total Outstanding (₹ Lakhs)</th>
                        <th className="px-4 py-3 text-right">Min / Max Rate (%)</th>
                        <th className="px-4 py-3 text-right">Weighted Avg Rate (%)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {report.part8a_msme.map((row, idx) => (
                        <tr key={idx} className="hover:bg-accent/40">
                          <td className="px-4 py-3 font-medium">{row.category}</td>
                          <td className="px-4 py-3 text-right font-mono">{row.account_count.toLocaleString()}</td>
                          <td className="px-4 py-3 text-right font-mono">₹{row.amount_lakhs.toLocaleString('en-IN')}</td>
                          <td className="px-4 py-3 text-right font-mono">{row.min_interest_rate}% / {row.max_interest_rate}%</td>
                          <td className="px-4 py-3 text-right font-mono font-semibold">{row.weighted_avg_interest_rate}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </TabsContent>

            {/* Annex 2: Shareholders Pattern */}
            <TabsContent value="annex2">
              <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none overflow-hidden">
                <CardHeader className="border-b border-border/50 bg-muted/30">
                  <CardTitle className="text-sm font-semibold">Annexure 2: Shareholding Pattern & Ownership Structure</CardTitle>
                </CardHeader>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-muted/50 text-muted-foreground uppercase font-semibold text-[10px]">
                      <tr>
                        <th className="px-4 py-3">Shareholder Name</th>
                        <th className="px-4 py-3">Type of Capital</th>
                        <th className="px-4 py-3 text-right">Number of Shares</th>
                        <th className="px-4 py-3 text-right">Face Value (₹)</th>
                        <th className="px-4 py-3 text-right">Shareholding (%)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {report.annex2_shareholders.map((row, idx) => (
                        <tr key={idx} className="hover:bg-accent/40">
                          <td className="px-4 py-3 font-semibold">{row.name}</td>
                          <td className="px-4 py-3 text-muted-foreground">{row.type_of_capital}</td>
                          <td className="px-4 py-3 text-right font-mono">{row.num_shares.toLocaleString()}</td>
                          <td className="px-4 py-3 text-right font-mono">₹{row.face_value}</td>
                          <td className="px-4 py-3 text-right font-mono font-semibold">{row.shareholding_pct}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </TabsContent>

            {/* Annex 9: Top 25 Borrowers */}
            <TabsContent value="annex9">
              <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none overflow-hidden">
                <CardHeader className="border-b border-border/50 bg-muted/30 flex flex-row items-center justify-between">
                  <CardTitle className="text-sm font-semibold">Annexure 9: Top 25 Borrowers Exposure</CardTitle>
                  <Badge variant="outline" className="text-[10px] rounded-full">Top 25 Accounts</Badge>
                </CardHeader>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-muted/50 text-muted-foreground uppercase font-semibold text-[10px]">
                      <tr>
                        <th className="px-4 py-3">#</th>
                        <th className="px-4 py-3">Borrower Name</th>
                        <th className="px-4 py-3">PAN</th>
                        <th className="px-4 py-3">Type</th>
                        <th className="px-4 py-3 text-right">Sanctioned (₹ L)</th>
                        <th className="px-4 py-3 text-right">Disbursed (₹ L)</th>
                        <th className="px-4 py-3 text-right">Outstanding (₹ L)</th>
                        <th className="px-4 py-3">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {report.annex9_top_borrowers.map((b, idx) => (
                        <tr key={idx} className="hover:bg-accent/40">
                          <td className="px-4 py-3 text-muted-foreground font-mono">{idx + 1}</td>
                          <td className="px-4 py-3 font-semibold">{b.borrower_name}</td>
                          <td className="px-4 py-3 font-mono text-muted-foreground">{b.pan}</td>
                          <td className="px-4 py-3"><Badge variant="outline" className="text-[10px] uppercase">{b.borrower_type}</Badge></td>
                          <td className="px-4 py-3 text-right font-mono">₹{b.sanctioned_amt.toLocaleString('en-IN')}</td>
                          <td className="px-4 py-3 text-right font-mono">₹{b.disbursed_amt.toLocaleString('en-IN')}</td>
                          <td className="px-4 py-3 text-right font-mono font-semibold">₹{b.total_outstanding.toLocaleString('en-IN')}</td>
                          <td className="px-4 py-3">
                            <Badge className="bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400 border-none text-[10px]">
                              {b.account_status}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </TabsContent>

            {/* Annex 10: Top Investments */}
            <TabsContent value="annex10">
              <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none overflow-hidden">
                <CardHeader className="border-b border-border/50 bg-muted/30 flex flex-row items-center justify-between">
                  <CardTitle className="text-sm font-semibold">Annexure 10: Top 25 Investments Portfolio</CardTitle>
                  <Badge variant="outline" className="text-[10px] rounded-full">{report.annex10_top_investments.length} Items</Badge>
                </CardHeader>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-muted/50 text-muted-foreground uppercase font-semibold text-[10px]">
                      <tr>
                        <th className="px-4 py-3">Entity Name</th>
                        <th className="px-4 py-3">Nature</th>
                        <th className="px-4 py-3">Investment Type</th>
                        <th className="px-4 py-3 font-mono">PAN</th>
                        <th className="px-4 py-3 text-right">Book Value (₹ L)</th>
                        <th className="px-4 py-3 text-center">Group Co?</th>
                        <th className="px-4 py-3 text-right">Outstanding (₹ L)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {report.annex10_top_investments.map((inv, idx) => (
                        <tr key={idx} className="hover:bg-accent/40">
                          <td className="px-4 py-3 font-semibold">{inv.entity_name}</td>
                          <td className="px-4 py-3"><Badge variant="outline" className="text-[10px] uppercase">{inv.nature || 'CURRENT'}</Badge></td>
                          <td className="px-4 py-3 text-muted-foreground">{inv.investment_type}</td>
                          <td className="px-4 py-3 font-mono text-muted-foreground">{inv.pan || 'NA'}</td>
                          <td className="px-4 py-3 text-right font-mono">₹{inv.book_value.toLocaleString('en-IN')}</td>
                          <td className="px-4 py-3 text-center font-mono text-muted-foreground">{inv.is_group_company || 'false'}</td>
                          <td className="px-4 py-3 text-right font-mono font-semibold">₹{inv.amt_outstanding.toLocaleString('en-IN')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </TabsContent>

            {/* Annex 13: Branch Operations */}
            <TabsContent value="annex13">
              <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none overflow-hidden">
                <CardHeader className="border-b border-border/50 bg-muted/30">
                  <CardTitle className="text-sm font-semibold">Annexure 13: District Branch Network Operations</CardTitle>
                </CardHeader>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-muted/50 text-muted-foreground uppercase font-semibold text-[10px]">
                      <tr>
                        <th className="px-4 py-3">GL Group</th>
                        <th className="px-4 py-3">District Branch Name</th>
                        <th className="px-4 py-3 text-right">Borrowers</th>
                        <th className="px-4 py-3 text-right">Active Accounts</th>
                        <th className="px-4 py-3 text-right">Total Outstanding (₹ Lakhs)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {report.annex13_branches.map((br, idx) => (
                        <tr key={idx} className="hover:bg-accent/40">
                          <td className="px-4 py-3 font-mono text-muted-foreground">#{br.branch_code}</td>
                          <td className="px-4 py-3 font-semibold">{br.branch_name}</td>
                          <td className="px-4 py-3 text-right font-mono">{br.customer_count.toLocaleString()}</td>
                          <td className="px-4 py-3 text-right font-mono">{br.account_count.toLocaleString()}</td>
                          <td className="px-4 py-3 text-right font-mono font-semibold">₹{br.total_outstanding.toLocaleString('en-IN')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </TabsContent>
          </Tabs>

        </div>
      )}
    </div>
  );
}
