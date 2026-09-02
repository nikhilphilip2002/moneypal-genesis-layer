'use client';

import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { nlq, type ChartSpec, type QuerySpec } from '@/lib/api';
import ChartRenderer from '@/components/nlq/ChartRenderer';
import NextQuestions from '@/components/nlq/NextQuestions';
import { formatValue } from '@/components/nlq/chartTheme';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

type Period = 'last_12_months' | 'this_fy';
type WidgetId = 'kpis' | 'trend' | 'mix' | 'branches' | 'risk';
type Widget = { id: WidgetId; title: string; description: string; spec: QuerySpec; wide?: boolean };

const query = (
  metrics: string[], dimensions: string[] = [], period = 'today',
  extra: Partial<QuerySpec> = {},
): QuerySpec => ({
  metrics, dimensions, filters: [], period: { relative: period }, compare_to: null,
  order_by: null, limit: 12, as_share: false, explain: false, ...extra,
});

function widgets(period: Period): Widget[] {
  return [
    {
      id: 'kpis', title: 'Portfolio pulse', description: 'Current book size and credit-quality indicators', wide: true,
      spec: query(['principal_outstanding', 'overdue_total', 'delinquent_account_count', 'par_30', 'npa_ratio']),
    },
    {
      id: 'trend', title: 'Portfolio trend', description: period === 'this_fy' ? 'Monthly movement this financial year' : 'Monthly movement over the last 12 months',
      spec: query(['principal_outstanding'], ['month'], period),
    },
    {
      id: 'mix', title: 'Product mix', description: 'Share of current outstanding by product',
      spec: query(['principal_outstanding'], ['product'], 'today', {
        as_share: true, order_by: { field: 'principal_outstanding', direction: 'desc' }, limit: 6,
      }),
    },
    {
      id: 'branches', title: 'Branch performance', description: 'Largest branches by current outstanding',
      spec: query(['principal_outstanding'], ['branch'], 'today', {
        order_by: { field: 'principal_outstanding', direction: 'desc' }, limit: 8,
      }),
    },
    {
      id: 'risk', title: 'Risk movement', description: period === 'this_fy' ? 'PAR 30 movement this financial year' : 'PAR 30 movement over the last 12 months',
      spec: query(['par_30'], ['month'], period),
    },
  ];
}

export default function PortfolioDashboard({
  onAsk,
  execute = nlq.execute,
}: {
  onAsk: (question: string) => void;
  execute?: (spec: QuerySpec) => Promise<ChartSpec>;
}) {
  const [period, setPeriod] = useState<Period>('last_12_months');
  const [charts, setCharts] = useState<Partial<Record<WidgetId, ChartSpec>>>({});
  const [errors, setErrors] = useState<Partial<Record<WidgetId, string>>>({});
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const definitions = widgets(period);
    setLoading(true);
    setErrors({});
    const results = await Promise.allSettled(definitions.map((widget) => execute(widget.spec)));
    const nextCharts: Partial<Record<WidgetId, ChartSpec>> = {};
    const nextErrors: Partial<Record<WidgetId, string>> = {};
    results.forEach((result, index) => {
      const id = definitions[index].id;
      if (result.status === 'fulfilled') nextCharts[id] = result.value;
      else nextErrors[id] = result.reason?.message ?? 'This widget could not be loaded.';
    });
    setCharts(nextCharts);
    setErrors(nextErrors);
    setLoading(false);
  }, [period, execute]);

  useEffect(() => { void load(); }, [load]);

  const definitions = widgets(period);
  const loaded = Object.keys(charts).length;
  const highlights = dashboardHighlights(charts);

  return (
    <div className="mx-auto w-full max-w-[1500px] p-4 sm:p-6">
      <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-primary">Executive portfolio</div>
          <h2 className="mt-1 font-headline text-2xl font-semibold tracking-tight">Portfolio dashboard</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            One coordinated view of scale, growth, mix, distribution, and credit quality.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-border/70 bg-muted/40 p-0.5">
            {([
              ['last_12_months', '12 months'], ['this_fy', 'This FY'],
            ] as const).map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setPeriod(value)}
                className={cn(
                  'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                  period === value ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
                )}
              >
                {label}
              </button>
            ))}
          </div>
          <Button type="button" variant="outline" size="sm" onClick={() => void load()} disabled={loading} className="gap-1.5 rounded-lg">
            <RefreshCw className={cn('size-3.5', loading && 'animate-spin')} /> Refresh
          </Button>
        </div>
      </div>

      {!loading && loaded > 0 && (
        <div className="mb-3 text-xs text-muted-foreground">{loaded} of {definitions.length} widgets loaded</div>
      )}

      {highlights.length > 0 && (
        <section className="mb-4 rounded-2xl border border-primary/15 bg-primary/[0.035] px-4 py-3.5">
          <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-primary">What stands out</div>
          <ul className="mt-2 grid gap-2 text-sm text-foreground/90 md:grid-cols-2 xl:grid-cols-4">
            {highlights.map((item) => <li key={item} className="leading-5">{item}</li>)}
          </ul>
        </section>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {definitions.map((widget) => {
          const chart = charts[widget.id];
          const error = errors[widget.id];
          return (
            <section
              key={widget.id}
              className={cn(
                'min-w-0 overflow-hidden rounded-2xl border border-border/70 bg-card shadow-sm shadow-black/[0.025]',
                widget.wide && 'xl:col-span-2',
              )}
            >
              <header className="border-b border-border/60 bg-muted/20 px-4 py-3.5">
                <h3 className="text-sm font-semibold text-foreground">{widget.title}</h3>
                <p className="mt-0.5 text-xs text-muted-foreground">{widget.description}</p>
              </header>
              <div className="p-4">
                {loading && !chart ? <WidgetSkeleton wide={widget.wide} /> : null}
                {error ? <WidgetError message={error} onRetry={() => void load()} /> : null}
                {chart ? (
                  <>
                    <ChartRenderer chart={chart} hideHeader hideSummary />
                    <NextQuestions steps={chart.next_steps ?? []} onPick={(step) => onAsk(step.question)} />
                  </>
                ) : null}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

function dashboardHighlights(charts: Partial<Record<WidgetId, ChartSpec>>): string[] {
  const result: string[] = [];
  const trend = charts.trend;
  const trendSeries = trend?.series[0];
  if (trend && trendSeries && trend.rows.length > 1) {
    const previous = trend.rows.at(-2)?.[trendSeries.field];
    const latest = trend.rows.at(-1)?.[trendSeries.field];
    if (typeof previous === 'number' && typeof latest === 'number') {
      const delta = latest - previous;
      result.push(`Portfolio ${delta >= 0 ? 'grew' : 'fell'} ${formatValue(Math.abs(delta), trendSeries.unit)} in the latest period.`);
    }
  }
  for (const [id, prefix] of [['mix', 'Largest product'], ['branches', 'Largest branch']] as const) {
    const chart = charts[id];
    const row = chart?.rows[0];
    const xField = chart?.x?.field;
    const series = chart?.series[0];
    if (row && xField && series && typeof row[series.field] === 'number') {
      result.push(`${prefix}: ${String(row[xField] ?? '—')} at ${formatValue(row[series.field], series.unit)}.`);
    }
  }
  const risk = charts.risk;
  const riskSeries = risk?.series[0];
  const latestRisk = risk && riskSeries ? risk.rows.at(-1)?.[riskSeries.field] : null;
  if (typeof latestRisk === 'number' && riskSeries) {
    result.push(`Latest PAR 30: ${formatValue(latestRisk, riskSeries.unit)}.`);
  }
  return result.slice(0, 4);
}

function WidgetSkeleton({ wide }: { wide?: boolean }) {
  return (
    <div className={cn('animate-pulse space-y-3', wide && 'grid gap-3 space-y-0 sm:grid-cols-3')}>
      {[0, 1, 2].map((item) => <div key={item} className="h-24 rounded-xl bg-muted/70" />)}
    </div>
  );
}

function WidgetError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex min-h-40 flex-col items-center justify-center rounded-xl border border-dashed border-border p-5 text-center">
      <AlertTriangle className="size-5 text-amber-500" />
      <p className="mt-2 text-sm font-medium">Widget unavailable</p>
      <p className="mt-1 max-w-sm text-xs leading-5 text-muted-foreground">{message}</p>
      <Button type="button" variant="ghost" size="sm" onClick={onRetry} className="mt-2">Try again</Button>
    </div>
  );
}
