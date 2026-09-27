'use client';

import { useState } from 'react';
import { AlertTriangle, ChevronDown, ChevronUp, Eye, Info } from 'lucide-react';
import type { AnalysisResult, ChartSpec, Finding, QuerySpec, Severity } from '@/lib/api';
import ChartRenderer from './ChartRenderer';
import NextQuestions from './NextQuestions';
import { formatValue } from './chartTheme';
import { cn } from '@/lib/utils';

// A multi-query answer: a headline, the findings that earned their place, and the charts
// behind them.
//
// The findings lead and the charts follow, deliberately. Seven charts with no ranking is
// not an answer to "how is the business doing" — it is the same pile of numbers the user
// already had, and it puts the work of deciding what matters back on them. The ranking is
// the product.

const SEVERITY: Record<Severity, { icon: typeof Info; ring: string; text: string; label: string }> = {
  alert: {
    icon: AlertTriangle,
    ring: 'border-destructive/40 bg-destructive/5',
    text: 'text-destructive',
    label: 'Alert',
  },
  watch: {
    icon: Eye,
    ring: 'border-amber-500/40 bg-amber-500/5',
    text: 'text-amber-600 dark:text-amber-400',
    label: 'Watch',
  },
  info: {
    icon: Info,
    ring: 'border-border bg-muted/40',
    text: 'text-muted-foreground',
    label: '',
  },
};

export default function AnalysisCard({
  analysis,
  onDrilldown,
  plain = false,
}: {
  analysis: AnalysisResult;
  onDrilldown?: (spec: QuerySpec, question: string) => void;
  plain?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="w-full space-y-4">
      <header className="space-y-1">
        {!plain && (
          <div className="flex items-baseline gap-2">
            <h3 className="text-sm font-semibold text-foreground">{analysis.title}</h3>
            {analysis.subtitle && (
              <span className="text-xs text-muted-foreground">{analysis.subtitle}</span>
            )}
          </div>
        )}
        {analysis.headline && (
          <p className="text-sm leading-6 text-foreground/90">{analysis.headline}</p>
        )}
      </header>

      {analysis.findings.length > 0 && (
        <ul className="space-y-2">
          {analysis.findings.map((finding) => (
            <FindingRow
              key={`${finding.step_id}-${finding.label}`}
              finding={finding}
              onDrilldown={onDrilldown}
              plain={plain}
            />
          ))}
        </ul>
      )}

      {analysis.narrative && (
        <p className="text-sm leading-6 text-muted-foreground">{analysis.narrative}</p>
      )}

      {analysis.warnings.length > 0 && (
        <ul className="space-y-1">
          {analysis.warnings.map((warning) => (
            <li key={warning} className="text-xs leading-5 text-muted-foreground">
              {warning}
            </li>
          ))}
        </ul>
      )}

      {analysis.charts.length > 0 && (
        <div className="space-y-3">
          <button
            type="button"
            onClick={() => setExpanded((open) => !open)}
            className={cn(
              'inline-flex items-center gap-1.5 py-1 text-xs text-foreground/80 transition-colors hover:text-foreground',
              !plain && 'rounded-full border border-border/70 bg-muted/60 px-3 hover:bg-muted',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            )}
            aria-expanded={expanded}
          >
            {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            {expanded ? 'Close' : 'Open'} {analysis.charts.length}-chart dashboard
          </button>

          {expanded && (
            <div className="grid gap-4 lg:grid-cols-2">
              {analysis.charts.map((chart, index) => (
                <StepChart key={`${chart.title}-${index}`} chart={chart} onDrilldown={onDrilldown} plain={plain} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function FindingRow({
  finding,
  onDrilldown,
  plain,
}: {
  finding: Finding;
  onDrilldown?: (spec: QuerySpec, question: string) => void;
  plain?: boolean;
}) {
  const tone = SEVERITY[finding.severity];
  const Icon = tone.icon;
  const clickable = Boolean(onDrilldown);

  const body = (
    <>
      <Icon className={cn('mt-0.5 h-3.5 w-3.5 shrink-0', tone.text)} aria-hidden />
      <span className="flex-1 text-sm leading-6 text-foreground/90">{finding.text}</span>
      {finding.value !== null && finding.unit !== 'text' && (
        <span className={cn('shrink-0 text-sm font-medium tabular-nums', tone.text)}>
          {formatValue(finding.value, finding.unit)}
        </span>
      )}
    </>
  );

  return (
    <li>
      {clickable ? (
        <button
          type="button"
          onClick={() => onDrilldown?.(finding.spec, finding.question || finding.label)}
          className={cn(
            'flex w-full items-start gap-2 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            plain ? 'hover:text-primary' : cn('rounded-lg border px-3 hover:bg-muted/70', tone.ring),
          )}
          title={`See the query behind "${finding.label}"`}
        >
          {body}
        </button>
      ) : (
        <div className={cn('flex items-start gap-2 py-2', !plain && cn('rounded-lg border px-3', tone.ring))}>
          {body}
        </div>
      )}
    </li>
  );
}

function StepChart({
  chart,
  onDrilldown,
  plain,
}: {
  chart: ChartSpec;
  onDrilldown?: (spec: QuerySpec, question: string) => void;
  plain?: boolean;
}) {
  return (
    <div className={cn('min-w-0', !plain && 'rounded-xl border border-border/70 bg-background/40 p-3.5')}>
      <ChartRenderer chart={chart} onDrilldown={(spec) => onDrilldown?.(spec, chart.title)} plain={plain} hideSummary={plain} />
      <NextQuestions
        steps={chart.next_steps ?? []}
        onPick={(step) => onDrilldown?.(step.spec, step.question)}
        plain={plain}
      />
    </div>
  );
}
