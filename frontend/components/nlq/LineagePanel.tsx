'use client';

import { useState } from 'react';
import type { ChartSpec } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import StatusRow from '@/components/ui/status-row';
import { ChevronDown, Copy, Download, Info, ShieldAlert, TriangleAlert } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SECTION_GAP, SOURCE_BADGE } from '@/lib/workbench-ui';

// Every number traceable: SQL, source tables, formula, row count, as-of date.
//
// Non-negotiable per the build plan — it is the difference between a demo and a tool a CFO
// will sign off on. The collapsed state still shows the warnings, because a caveat the user
// has to click to discover is a caveat they will not see.
//
// This is a nested panel, never a second card: a light border, no shadow of its own, and
// internal dividers a shade weaker than the parent card's. The card that contains it owns
// the outer edge.

export default function LineagePanel({
  chart,
  sourceLabel,
  className,
}: {
  chart: ChartSpec;
  sourceLabel?: string;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const { lineage } = chart;
  const displayedSql = lineage.display_sql || lineage.sql;

  return (
    <div
      className={cn(
        SECTION_GAP,
        'overflow-hidden rounded-xl border border-border/60 bg-muted/25',
        className,
      )}
    >
      {lineage.unverified && (
        <StatusRow icon={ShieldAlert} tone="warning" size="sm" className="border-b border-border/50 px-3 py-2">
          Generated query — this answer does not come from a reviewed metric definition.
          Check the SQL before relying on it.
        </StatusRow>
      )}

      {lineage.requires_signoff.length > 0 && (
        <StatusRow icon={TriangleAlert} tone="warning" size="sm" className="border-b border-border/50 px-3 py-2">
          Definition pending client sign-off: {lineage.requires_signoff.join(', ')}.
        </StatusRow>
      )}

      {lineage.warnings.map((warning, index) => (
        <StatusRow key={index} icon={Info} size="sm" className="border-b border-border/50 px-3 py-2">
          {warning}
        </StatusRow>
      ))}

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full flex-wrap items-center gap-2 px-3 py-2.5 text-left text-xs leading-5 text-muted-foreground transition-colors hover:bg-muted/45 hover:text-foreground"
      >
        <ChevronDown
          aria-hidden
          className={cn('size-3.5 shrink-0 transition-transform duration-200', open && 'rotate-180')}
        />
        {sourceLabel && (
          <Badge variant="secondary" className={SOURCE_BADGE}>
            {sourceLabel}
          </Badge>
        )}
        <span>{sourceLabel ? 'Source details & SQL' : 'How this was calculated'}</span>
        <span className="ml-auto shrink-0 tabular-nums">
          {lineage.row_count} row{lineage.row_count === 1 ? '' : 's'} · {lineage.duration_ms} ms
          {lineage.as_of ? ` · as at ${lineage.as_of}` : ''}
        </span>
      </button>

      {open && (
        <div className="space-y-3 border-t border-border/50 px-3 py-3 text-xs leading-5">
          {Object.keys(lineage.formulas).length > 0 && (
            <Section title="Formula">
              {Object.entries(lineage.formulas).map(([metric, formula]) => (
                <div key={metric} className="text-muted-foreground">
                  <span className="font-medium text-foreground">{metric}</span> = {formula}
                </div>
              ))}
            </Section>
          )}

          <Section title="Source tables">
            <div className="flex flex-wrap gap-1">
              {lineage.source_tables.map((table) => (
                <Badge key={table} variant="secondary" className="h-5 rounded-md px-1.5 font-mono text-[11px] font-normal">
                  {table}
                </Badge>
              ))}
            </div>
          </Section>

          <Section title="How the query retrieves the result">
            <div className="space-y-2 text-muted-foreground">
              <p>
                The service runs a read-only SELECT against the source tables above. PostgreSQL
                applies the dates and filters below before calculating the formula, then returns
                at most the row limit shown.
              </p>
              {Object.keys(lineage.parameters).length > 0 && (
                <dl className="grid gap-1 rounded-lg bg-muted/40 p-2 sm:grid-cols-[minmax(9rem,auto)_1fr]">
                  {Object.entries(lineage.parameters).map(([name, value]) => (
                    <div key={name} className="contents">
                      <dt className="font-mono text-foreground">{name.replaceAll('_', ' ')}</dt>
                      <dd className="font-mono">{value}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
          </Section>

          <Section
            title="SQL"
            action={
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  title="Copy runnable SQL"
                  onClick={() => navigator.clipboard?.writeText(displayedSql)}
                  className="h-6 gap-1 px-2 text-[11px] font-normal text-muted-foreground hover:text-foreground [&_svg]:size-3"
                >
                  <Copy />
                  Copy runnable SQL
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  title="Export CSV"
                  onClick={() => downloadCsv(chart)}
                  className="h-6 gap-1 px-2 text-[11px] font-normal text-muted-foreground hover:text-foreground [&_svg]:size-3"
                >
                  <Download />
                  Export CSV
                </Button>
              </div>
            }
          >
            <pre className="max-h-64 overflow-auto rounded-lg bg-muted/60 p-2 text-[11px] leading-relaxed text-foreground">
              <code>{displayedSql}</code>
            </pre>
          </Section>
        </div>
      )}
    </div>
  );
}

function Section({
  title, children, action,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-1 flex min-h-6 flex-wrap items-center justify-between gap-2">
        <div className="font-medium uppercase tracking-wide text-muted-foreground">{title}</div>
        {action}
      </div>
      {children}
    </div>
  );
}

// Exports what the user is actually looking at — the decoded labels, not the raw codes.
function downloadCsv(chart: ChartSpec) {
  const header = chart.columns.map((c) => escapeCsv(c.label)).join(',');
  const body = chart.rows
    .map((row) => chart.columns.map((c) => escapeCsv(row[c.name])).join(','))
    .join('\n');
  const blob = new Blob([`${header}\n${body}`], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${chart.title.replace(/[^a-z0-9]+/gi, '_').toLowerCase() || 'nlq'}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function escapeCsv(value: unknown): string {
  if (value === null || value === undefined) return '';
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}
