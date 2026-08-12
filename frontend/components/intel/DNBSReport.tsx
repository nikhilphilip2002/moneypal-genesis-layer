'use client';

import { useEffect, useState } from 'react';
import {
  regulatory,
  type DNBS02ReportData,
  type DNBS02Periods,
  type RegulatoryReportData,
  type RegulatoryReportDefinition,
  type RegulatoryReportPeriods,
} from '@/lib/api';
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

type ReportFrequency = 'monthly' | 'quarterly' | 'yearly';
type ReportMode = 'regulatory' | 'custom';

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
  const [selectedReport, setSelectedReport] = useState<string>('dnbs02');
  const [reportCatalog, setReportCatalog] = useState<RegulatoryReportDefinition[]>([]);
  const [genericPeriods, setGenericPeriods] = useState<RegulatoryReportPeriods | null>(null);
  const [genericReport, setGenericReport] = useState<RegulatoryReportData | null>(null);
  const [reportMode, setReportMode] = useState<ReportMode>('regulatory');
  const [frequency, setFrequency] = useState<ReportFrequency>('quarterly');
  const [period, setPeriod] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [periods, setPeriods] = useState<DNBS02Periods | null>(null);
  const [report, setReport] = useState<DNBS02ReportData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeSubTab, setActiveSubTab] = useState<string>('part1');

  useEffect(() => {
    regulatory.reports().then(setReportCatalog).catch(() => setReportCatalog([]));
  }, []);

  // Discover reportable periods first, then default to the most recent one.
  useEffect(() => {
    if (selectedReport !== 'dnbs02') return;
    let cancelled = false;
    regulatory
      .dnbsPeriods()
      .then((p) => {
        if (cancelled) return;
        setPeriods(p);
        const fixedFrequency: ReportFrequency = 'quarterly';
        setFrequency(fixedFrequency);
        const latest = p[fixedFrequency][0];
        if (latest) {
          setPeriod(latest.value);
          updateDatesForPeriod(fixedFrequency, latest.value);
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
  }, [selectedReport]);

  useEffect(() => {
    if (selectedReport === 'dnbs02') return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setReport(null);
    setGenericReport(null);
    regulatory
      .reportPeriods(selectedReport)
      .then((result) => {
        if (cancelled) return;
        setGenericPeriods(result);
        const definition = reportCatalog.find((item) => item.id === selectedReport);
        const fixedFrequency = definition?.frequency ?? (selectedReport.includes('4b') ? 'monthly' : 'quarterly');
        setFrequency(fixedFrequency);
        const options = result[fixedFrequency] ?? [];
        const latest = options[0];
        if (!latest) {
          setError('No exact period-end silver snapshot is available for this report.');
          setLoading(false);
          return;
        }
        setPeriod(latest.value);
        updateDatesForPeriod(fixedFrequency, latest.value);
      })
      .catch((err: any) => {
        if (!cancelled) {
          setError(err?.message || 'Failed to load reportable periods');
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, [selectedReport, reportCatalog]);

  const fetchReport = async () => {
    const custom = reportMode === 'custom';
    if (custom && (!startDate || !endDate || endDate < startDate)) return;
    if (!custom && !period) return;
    if (selectedReport !== 'dnbs02' && !genericPeriods) return;
    setLoading(true);
    setError(null);
    try {
      if (selectedReport === 'dnbs02') {
        const data = await regulatory.dnbsReport(
          custom ? 'custom' : frequency,
          custom ? '' : period,
          custom ? startDate : undefined,
          custom ? endDate : undefined,
        );
        setReport(data);
        setGenericReport(null);
      } else {
        const data = await regulatory.report(
          selectedReport,
          custom ? 'custom' : frequency,
          custom ? '' : period,
          custom ? startDate : undefined,
          custom ? endDate : undefined,
        );
        setGenericReport(data);
        setReport(null);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load the selected report');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Date inputs are edited one at a time, so auto-fetching a custom range can send a
    // transient invalid pair (for example Jul 1 through Jun 30). Custom reports run
    // only when the user presses Generate.
    if (reportMode === 'custom') return;
    fetchReport();
  }, [selectedReport, reportMode, frequency, period, genericPeriods]);

  const periodOptions = selectedReport !== 'dnbs02'
    ? ((frequency === 'monthly' ? genericPeriods?.monthly : genericPeriods?.quarterly) ?? [])
    : (periods?.[frequency] ?? []).map((item) => ({
        label: `${item.label} (${item.value})`,
        value: item.value,
        end_date: item.end_date,
      }));

  const latestSourceDate = selectedReport === 'dnbs02'
    ? periods?.snapshot_dates?.at(-1)
    : genericPeriods?.source_dates?.at(-1);
  const latestReportablePeriod = periodOptions[0];

  const handleModeChange = (mode: ReportMode) => {
    setReportMode(mode);
    setError(null);
    setReport(null);
    setGenericReport(null);
    if (mode === 'regulatory' && periodOptions[0]) {
      setPeriod(periodOptions[0].value);
      updateDatesForPeriod(frequency, periodOptions[0].value);
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
    updateDatesForPeriod(frequency, newPeriod);
  };

  const handleCustomStartDateChange = (val: string) => {
    setStartDate(val);
    setError(null);
  };

  const handleCustomEndDateChange = (val: string) => {
    setEndDate(val);
    setError(null);
  };

  const handleExcelDownload = () => {
    const custom = reportMode === 'custom';
    const url = selectedReport === 'dnbs02'
      ? regulatory.getDnbsExcelUrl(
          custom ? 'custom' : frequency,
          custom ? '' : period,
          custom ? startDate : undefined,
          custom ? endDate : undefined,
        )
      : regulatory.getReportExcelUrl(
          selectedReport,
          custom ? 'custom' : frequency,
          custom ? '' : period,
          custom ? startDate : undefined,
          custom ? endDate : undefined,
        );
    window.open(url, '_blank');
  };

  const customDatesValid = Boolean(startDate && endDate && startDate <= endDate);

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
                {genericReport && (
                  <Badge
                    variant="outline"
                    className={cn(
                      'gap-1 border-none text-[11px]',
                      genericReport.status === 'blocked'
                        ? 'bg-red-500/10 text-red-600 dark:text-red-400'
                        : 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
                    )}
                  >
                    <Database className="h-3 w-3" /> {genericReport.status}
                  </Badge>
                )}
                {(report?.report_mode === 'custom' || genericReport?.report_mode === 'custom') && (
                  <Badge variant="outline" className="border-none bg-blue-500/10 text-[11px] text-blue-600 dark:text-blue-400">
                    Internal custom report
                  </Badge>
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                Programmatic return mapping for Important Financial Parameters, Capital Adequacy, Asset Quality, and Top Exposure Annexures.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={fetchReport}
                disabled={loading || (reportMode === 'custom' && !customDatesValid)}
                className="h-9 rounded-xl gap-1.5 text-xs"
              >
                <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
                {reportMode === 'custom' ? 'Generate' : 'Refresh'}
              </Button>

              <Button
                onClick={handleExcelDownload}
                disabled={loading || Boolean(error) || (reportMode === 'custom' && !customDatesValid)}
                size="sm"
                className="h-9 rounded-xl gap-1.5 text-xs bg-primary text-primary-foreground"
              >
                <Download className="h-3.5 w-3.5" />
                Download Excel (.xlsx)
              </Button>
            </div>
          </div>

          {/* Date & Preset Filters Bar - Border-less Card Design Matching Monthly/Quarterly/Yearly Pills */}
          <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-border/40">
            <select
              value={selectedReport}
              onChange={(event) => {
                setSelectedReport(event.target.value);
                setGenericPeriods(null);
                setGenericReport(null);
                setReport(null);
              }}
              className="h-9 min-w-[260px] rounded-xl border border-input bg-background px-3 text-xs font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              aria-label="Select RBI report"
            >
              {(reportCatalog.length ? reportCatalog : [
                { id: 'dnbs02', name: 'DNBS02 — Important Financial Parameters' },
              ]).map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>

            {/* Filing presets and analytical custom ranges are intentionally distinct. */}
            <div className="inline-flex rounded-xl bg-accent p-1 text-xs">
              {(['regulatory', 'custom'] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => handleModeChange(mode)}
                  className={cn(
                    'rounded-lg px-3 py-1.5 font-medium transition-all capitalize',
                    reportMode === mode
                      ? 'bg-background text-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                >
                  {mode === 'regulatory' ? 'Regulatory Period' : 'Custom Range'}
                </button>
              ))}
            </div>

            {reportMode === 'regulatory' && (
              <Badge variant="outline" className="h-9 rounded-xl border-none bg-accent px-3 capitalize">
                {frequency}
              </Badge>
            )}

            {reportMode === 'regulatory' && (
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

            {reportMode === 'regulatory' && latestReportablePeriod && (
              <span className="text-[11px] text-muted-foreground">
                Latest reportable: <span className="font-semibold text-foreground">{latestReportablePeriod.label}</span>
                {latestSourceDate ? ` · source through ${latestSourceDate}` : ''}
              </span>
            )}

            {reportMode === 'custom' && <div className="inline-flex items-center gap-2 text-xs font-medium bg-accent rounded-xl p-1">
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
            </div>}
            {reportMode === 'custom' && !customDatesValid && (
              <span className="text-[11px] font-medium text-red-600 dark:text-red-400">
                Select a valid start and end date.
              </span>
            )}
            {reportMode === 'custom' && customDatesValid && (
              <span className="text-[11px] text-muted-foreground">
                Exact {endDate} source required · exported as an internal draft
              </span>
            )}
          </div>
        </div>
      </Card>

      {genericReport && !loading && (
        <div className="space-y-4">
          <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none">
            <CardHeader className="border-b border-border/50">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle className="text-base">{genericReport.name}</CardTitle>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Return {genericReport.return_code} · {genericReport.start_date} to {genericReport.end_date}
                  </p>
                </div>
                <Badge variant="outline" className="rounded-full capitalize">{genericReport.status}</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 p-5">
              <div className="grid gap-3 sm:grid-cols-3">
                {Object.entries(genericReport.summary).map(([key, value]) => (
                  <div key={key} className="rounded-xl bg-muted/40 p-3">
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                      {key.replaceAll('_', ' ')}
                    </p>
                    <p className="mt-1 text-sm font-semibold">
                      {typeof value === 'number' ? value.toLocaleString('en-IN') : value}
                    </p>
                  </div>
                ))}
              </div>
              <div className="space-y-2">
                {Object.entries(genericReport.provenance).map(([key, entry]) => (
                  <div key={key} className="flex items-start justify-between gap-4 rounded-xl border border-border/60 p-3 text-xs">
                    <div>
                      <p className="font-semibold">{key.replaceAll('_', ' ')}</p>
                      <p className="mt-1 text-muted-foreground">{entry.note || entry.error || 'PostgreSQL silver source resolved.'}</p>
                    </div>
                    <Badge variant="outline" className="shrink-0 capitalize">{entry.status.replaceAll('_', ' ')}</Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Main Content States */}
      {loading && <LoadingCard lines={10} stages={['Querying warehouse snapshot', 'Mapping RBI return sections', 'Compiling report']} />}
      {error && (
        <WidgetError
          title="DNBS Report Builder"
          message={error}
          onRetry={reportMode === 'custom' && !customDatesValid ? undefined : fetchReport}
        />
      )}

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
