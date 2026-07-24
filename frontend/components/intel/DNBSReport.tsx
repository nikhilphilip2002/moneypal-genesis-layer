'use client';

import { useEffect, useState } from 'react';
import { regulatory, type DNBS02ReportData } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
} from 'lucide-react';
import { cn } from '@/lib/utils';

const PERIOD_OPTIONS = {
  monthly: [
    { label: 'May 2026 (2026-05)', value: '2026-05' },
    { label: 'April 2026 (2026-04)', value: '2026-04' },
    { label: 'March 2026 (2026-03)', value: '2026-03' },
    { label: 'February 2026 (2026-02)', value: '2026-02' },
    { label: 'January 2026 (2026-01)', value: '2026-01' },
    { label: 'December 2025 (2025-12)', value: '2025-12' },
  ],
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

export default function DNBSReport() {
  const [frequency, setFrequency] = useState<'monthly' | 'quarterly' | 'yearly' | 'custom'>('monthly');
  const [period, setPeriod] = useState<string>('2026-05');
  const [startDate, setStartDate] = useState<string>('2026-05-01');
  const [endDate, setEndDate] = useState<string>('2026-05-31');
  const [report, setReport] = useState<DNBS02ReportData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeSubTab, setActiveSubTab] = useState<string>('part1');

  const fetchReport = async () => {
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

  const handleFrequencyChange = (newFreq: 'monthly' | 'quarterly' | 'yearly') => {
    setFrequency(newFreq);
    const p = PERIOD_OPTIONS[newFreq][0].value;
    setPeriod(p);
    updateDatesForPeriod(newFreq, p);
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
                {report?.is_live_pg ? (
                  <Badge variant="outline" className="gap-1 bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400 border-none text-[11px]">
                    <Database className="h-3 w-3" /> Live PG Database
                  </Badge>
                ) : (
                  <Badge variant="outline" className="gap-1 bg-blue-500/10 text-blue-600 dark:bg-blue-500/20 dark:text-blue-400 border-none text-[11px]">
                    <Database className="h-3 w-3" /> GICC Staged Ledger
                  </Badge>
                )}
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

          {/* Date & Preset Filters Bar */}
          <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-border/40">
            {/* Frequency Selection */}
            <div className="inline-flex rounded-xl bg-accent p-1 text-xs">
              {(['monthly', 'quarterly', 'yearly'] as const).map((f) => (
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
                  {f}
                </button>
              ))}
            </div>

            {/* Period Dropdown */}
            {frequency !== 'custom' && (
              <select
                value={period}
                onChange={(e) => handlePeriodChange(e.target.value)}
                className="h-9 rounded-xl border border-input bg-background px-3 text-xs font-medium focus:outline-none focus:ring-1 focus:ring-primary"
              >
                {PERIOD_OPTIONS[frequency as 'monthly' | 'quarterly' | 'yearly']?.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            )}

            {/* Custom Date Pickers */}
            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground bg-accent/40 rounded-xl px-3 py-1 border border-border/50">
              <span className="text-[11px] font-semibold text-foreground uppercase">Date Range:</span>
              <div className="flex items-center gap-1.5">
                <span className="text-[11px]">From</span>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => handleCustomStartDateChange(e.target.value)}
                  className="h-7 rounded-lg border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-[11px]">To</span>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => handleCustomEndDateChange(e.target.value)}
                  className="h-7 rounded-lg border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
            </div>
          </div>
        </div>
      </Card>


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
                  <p className="text-xs text-muted-foreground">Net Owned Funds (NOF)</p>
                  <p className="text-xl font-bold tracking-tight">₹{report.summary.net_owned_funds.toLocaleString('en-IN')} Lakhs</p>
                  <p className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">Compliant with RBI Limit</p>
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
                  <p className="text-xl font-bold tracking-tight">{report.summary.crar_pct}%</p>
                  <p className="text-[11px] text-muted-foreground">Min RBI threshold: 15%</p>
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
                  <p className="text-xl font-bold tracking-tight text-emerald-600 dark:text-emerald-400">{report.summary.npa_ratio_pct}%</p>
                  <p className="text-[11px] text-muted-foreground">Sub-standard & Doubtful</p>
                </div>
                <div className="rounded-xl bg-amber-500/10 p-2 text-amber-600 dark:text-amber-400">
                  <AlertCircle className="h-5 w-5" />
                </div>
              </div>
            </Card>
          </div>

          {/* Sub-tabs for Report Details */}
          <Tabs value={activeSubTab} onValueChange={setActiveSubTab} className="w-full">
            <div className="overflow-x-auto pb-1">
              <TabsList className="mb-4 inline-flex w-auto shrink-0 min-w-full justify-start gap-1">
                <TabsTrigger value="part1">Part 1: Capital & NOF</TabsTrigger>
                <TabsTrigger value="part2">Part 2: Loan Assets</TabsTrigger>
                <TabsTrigger value="part3">Part 3: Revenue & PnL</TabsTrigger>
                <TabsTrigger value="part6">Part 6: Sensitive Sectors</TabsTrigger>
                <TabsTrigger value="part8">Part 8C: Asset Quality</TabsTrigger>
                <TabsTrigger value="part8a">Part 8A: MSME Profile</TabsTrigger>
                <TabsTrigger value="annex2">Annex 2: Shareholders</TabsTrigger>
                <TabsTrigger value="annex9">Annex 9: Top Borrowers</TabsTrigger>
                <TabsTrigger value="annex10">Annex 10: Top Investments</TabsTrigger>
                <TabsTrigger value="annex13">Annex 13: Branch Network</TabsTrigger>
              </TabsList>
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
                        <th className="px-4 py-3">Code</th>
                        <th className="px-4 py-3">Particulars</th>
                        <th className="px-4 py-3 text-right">Amount (₹ in Lakhs)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {report.part1_capital.map((row, idx) => (
                        <tr key={idx} className={cn('hover:bg-accent/40', row.code === '1.6' && 'bg-primary/5 font-semibold')}>
                          <td className="px-4 py-3 font-mono">{row.code}</td>
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
                        <th className="px-4 py-3">Sensitive Sector Description</th>
                        <th className="px-4 py-3 text-right">Total Exposure (₹ Lakhs)</th>
                        <th className="px-4 py-3 text-right">RBI Risk Weight (%)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {report.part6_sensitive.map((row, idx) => (
                        <tr key={idx} className="hover:bg-accent/40">
                          <td className="px-4 py-3 font-medium">{row.sector}</td>
                          <td className="px-4 py-3 text-right font-mono">₹{row.exposure_lakhs.toLocaleString('en-IN')}</td>
                          <td className="px-4 py-3 text-right font-mono font-semibold">{row.risk_weight_pct}%</td>
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
                        <th className="px-4 py-3 text-right">Weighted Avg Interest Rate (%)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {report.part8a_msme.map((row, idx) => (
                        <tr key={idx} className="hover:bg-accent/40">
                          <td className="px-4 py-3 font-medium">{row.category}</td>
                          <td className="px-4 py-3 text-right font-mono">{row.account_count.toLocaleString()}</td>
                          <td className="px-4 py-3 text-right font-mono">₹{row.amount_lakhs.toLocaleString('en-IN')}</td>
                          <td className="px-4 py-3 text-right font-mono font-semibold">{row.avg_interest_rate}%</td>
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
                <CardHeader className="border-b border-border/50 bg-muted/30">
                  <CardTitle className="text-sm font-semibold">Annexure 10: Top Investments Portfolio</CardTitle>
                </CardHeader>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-muted/50 text-muted-foreground uppercase font-semibold text-[10px]">
                      <tr>
                        <th className="px-4 py-3">Entity Name</th>
                        <th className="px-4 py-3">Investment Type</th>
                        <th className="px-4 py-3 text-right">Book Value (₹ Lakhs)</th>
                        <th className="px-4 py-3 text-right">Amount Outstanding (₹ Lakhs)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {report.annex10_top_investments.map((inv, idx) => (
                        <tr key={idx} className="hover:bg-accent/40">
                          <td className="px-4 py-3 font-semibold">{inv.entity_name}</td>
                          <td className="px-4 py-3 text-muted-foreground">{inv.investment_type}</td>
                          <td className="px-4 py-3 text-right font-mono">₹{inv.book_value.toLocaleString('en-IN')}</td>
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
                        <th className="px-4 py-3">Code</th>
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
