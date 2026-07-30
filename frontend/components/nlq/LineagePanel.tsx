'use client';

import { useState } from 'react';
import type { ChartSpec } from '@/lib/api';
import { ChevronDown, Copy, Download, ShieldAlert, TriangleAlert } from 'lucide-react';
import { cn } from '@/lib/utils';

// Every number traceable: SQL, source tables, formula, row count, as-of date.
//
// Non-negotiable per the build plan — it is the difference between a demo and a tool a CFO
// will sign off on. The collapsed state still shows the warnings, because a caveat the user
// has to click to discover is a caveat they will not see.

export default function LineagePanel({ chart }: { chart: ChartSpec }) {
  const [open, setOpen] = useState(false);
  const { lineage } = chart;

  return (
    <div className="mt-3 rounded-lg border border-border/70 bg-muted/20">
      {lineage.unverified && (
        <div className="flex items-start gap-2 border-b border-border/70 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
          <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            Generated query — this answer does not come from a reviewed metric definition.
            Check the SQL before relying on it.
          </span>
        </div>
      )}

      {lineage.requires_signoff.length > 0 && (
        <div className="flex items-start gap-2 border-b border-border/70 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
          <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>Definition pending client sign-off: {lineage.requires_signoff.join(', ')}.</span>
        </div>
      )}

      {lineage.warnings.map((warning, index) => (
        <div
          key={index}
          className="border-b border-border/70 px-3 py-2 text-xs text-muted-foreground"
        >
          {warning}
        </div>
      ))}

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-xs text-muted-foreground hover:text-foreground"
      >
        <ChevronDown className={cn('h-3.5 w-3.5 transition-transform', open && 'rotate-180')} />
        <span>How this was calculated</span>
        <span className="ml-auto tabular-nums">
          {lineage.row_count} row{lineage.row_count === 1 ? '' : 's'} · {lineage.duration_ms} ms
          {lineage.as_of ? ` · as at ${lineage.as_of}` : ''}
        </span>
      </button>

      {open && (
        <div className="space-y-3 border-t border-border/70 px-3 py-3 text-xs">
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
                <code
                  key={table}
                  className="rounded bg-muted px-1.5 py-0.5 text-[11px] text-foreground"
                >
                  {table}
                </code>
              ))}
            </div>
          </Section>

          <Section
            title="SQL"
            action={
              <div className="flex gap-2">
                <IconButton
                  label="Copy SQL"
                  onClick={() => navigator.clipboard?.writeText(lineage.sql)}
                  icon={<Copy className="h-3 w-3" />}
                />
                <IconButton
                  label="Export CSV"
                  onClick={() => downloadCsv(chart)}
                  icon={<Download className="h-3 w-3" />}
                />
              </div>
            }
          >
            <pre className="max-h-64 overflow-auto rounded bg-muted/60 p-2 text-[11px] leading-relaxed text-foreground">
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

function IconButton({
  label, onClick, icon,
}: { label: string; onClick: () => void; icon: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      className="flex items-center gap-1 rounded border border-border px-1.5 py-0.5 text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground"
    >
      {icon}
      {label}
    </button>
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
