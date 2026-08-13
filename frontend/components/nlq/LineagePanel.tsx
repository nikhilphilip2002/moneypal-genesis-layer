'use client';

import { useState } from 'react';
import type { ChartSpec } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ChevronDown, Copy, Download, ShieldAlert, TriangleAlert } from 'lucide-react';
import { cn } from '@/lib/utils';

// Every number traceable: SQL, source tables, formula, row count, as-of date.
//
// Non-negotiable per the build plan — it is the difference between a demo and a tool a CFO
// will sign off on. The collapsed state still shows the warnings, because a caveat the user
// has to click to discover is a caveat they will not see.

export default function LineagePanel({
  chart,
  sourceLabel,
}: {
  chart: ChartSpec;
  sourceLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const { lineage } = chart;

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-border bg-muted/20">
      {lineage.unverified && (
        <div className="flex items-start gap-2 border-b border-border px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
          <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            Generated query — this answer does not come from a reviewed metric definition.
            Check the SQL before relying on it.
          </span>
        </div>
      )}

      {lineage.requires_signoff.length > 0 && (
        <div className="flex items-start gap-2 border-b border-border px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
          <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>Definition pending client sign-off: {lineage.requires_signoff.join(', ')}.</span>
        </div>
      )}

      {lineage.warnings.map((warning, index) => (
        <div key={index} className="border-b border-border px-3 py-2 text-xs text-muted-foreground">
          {warning}
        </div>
      ))}

      <Button
        type="button"
        variant="ghost"
        onClick={() => setOpen((v) => !v)}
        className="h-auto w-full justify-start rounded-none px-3 py-2 text-xs font-normal text-muted-foreground hover:text-foreground"
      >
        <ChevronDown className={cn('h-3.5 w-3.5 transition-transform duration-200', open && 'rotate-180')} />
        {sourceLabel && (
          <Badge variant="secondary" className="h-5 rounded-md px-1.5 text-[10px] font-medium uppercase tracking-wide">
            {sourceLabel}
          </Badge>
        )}
        <span>{sourceLabel ? 'Source details & SQL' : 'How this was calculated'}</span>
        <span className="ml-auto tabular-nums">
          {lineage.row_count} row{lineage.row_count === 1 ? '' : 's'} · {lineage.duration_ms} ms
          {lineage.as_of ? ` · as at ${lineage.as_of}` : ''}
        </span>
      </Button>

      {open && (
        <div className="space-y-3 border-t border-border px-3 py-3 text-xs">
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
                <Badge key={table} variant="secondary" className="rounded-md font-mono text-[11px] font-normal">
                  {table}
                </Badge>
              ))}
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
                  title="Copy SQL"
                  onClick={() => navigator.clipboard?.writeText(lineage.sql)}
                  className="h-6 gap-1 px-2 text-[11px] font-normal text-muted-foreground hover:text-foreground [&_svg]:size-3"
                >
                  <Copy />
                  Copy SQL
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
              <code>{lineage.sql}</code>
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
      <div className="mb-1 flex items-center justify-between">
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
