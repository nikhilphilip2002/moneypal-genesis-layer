'use client';

import { useState } from 'react';
import { AlertTriangle, ChevronDown, ChevronUp, Eye, Info, Scale } from 'lucide-react';
import type { Severity, Worklist, WorklistItem } from '@/lib/api';
import { formatValue } from './chartTheme';
import { cn } from '@/lib/utils';

// The end of a chain. A chart says branch 7 is worst; this says who to call, in what order,
// and why each one is on the list.
//
// The reason leads and the numbers follow, deliberately. A ranked list with no reasons gets
// worked from the top until the officer disagrees with one entry and then abandoned — the
// reason is what survives that test, because they can check it against what they know.
//
// The score is expandable rather than hidden. Every weight comes from the catalog and the
// terms add up in front of the reader, which is the only version of "priority" a collections
// team trusts twice.

const SEVERITY: Record<Severity, { icon: typeof Info; ring: string; text: string; label: string }> = {
  alert: {
    icon: AlertTriangle,
    ring: 'border-destructive/40 bg-destructive/5',
    text: 'text-destructive',
    label: 'Act now',
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

// The fields worth a column on a narrow card. The rest stay in the row payload for export
// and for the detail panel — a collections officer scanning fifty rows needs four numbers,
// not fourteen.
const SUMMARY_FIELDS = ['dpd_days', 'total_overdue', 'principal_outstanding'] as const;

export default function WorklistCard({
  worklist,
  onExport,
}: {
  worklist: Worklist;
  onExport?: () => void;
}) {
  const alerts = worklist.items.filter((i) => i.severity === 'alert').length;

  return (
    <div className="w-full space-y-4">
      <header className="space-y-1">
        <div className="flex items-baseline gap-2">
          <h3 className="text-sm font-semibold text-foreground">{worklist.title}</h3>
          {worklist.subtitle && (
            <span className="text-xs text-muted-foreground">{worklist.subtitle}</span>
          )}
        </div>
        <p className="text-sm leading-6 text-foreground/90">
          {worklist.items.length === 0
            ? 'No account triggered any of this list’s rules.'
            : `${worklist.items.length} accounts, ${alerts} needing action today.`}
        </p>
      </header>

      {worklist.warnings.length > 0 && (
        <ul className="space-y-1">
          {worklist.warnings.map((warning) => (
            <li key={warning} className="text-xs leading-5 text-muted-foreground">
              {warning}
            </li>
          ))}
        </ul>
      )}

      {worklist.items.length > 0 && (
        <ol className="space-y-2">
          {worklist.items.map((item) => (
            <Row key={item.account} item={item} columns={worklist.columns} />
          ))}
        </ol>
      )}

      <Footer worklist={worklist} onExport={onExport} />
    </div>
  );
}

function Row({ item, columns }: { item: WorklistItem; columns: Worklist['columns'] }) {
  const [open, setOpen] = useState(false);
  const tone = SEVERITY[item.severity];
  const Icon = tone.icon;
  const borrower = item.fields.borrower;
  const branch = item.fields.branch;

  return (
    <li className={cn('rounded-lg border', tone.ring)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={cn(
          'flex w-full items-start gap-3 px-3 py-2 text-left transition-colors',
          'hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        )}
      >
        <span className="mt-0.5 w-6 shrink-0 text-xs font-medium tabular-nums text-muted-foreground">
          {item.rank}
        </span>
        <Icon className={cn('mt-0.5 h-3.5 w-3.5 shrink-0', tone.text)} aria-hidden />

        <span className="min-w-0 flex-1 space-y-1">
          <span className="flex flex-wrap items-baseline gap-x-2 text-sm text-foreground">
            <span className="font-medium">{borrower || item.account}</span>
            {borrower && (
              <span className="font-mono text-xs text-muted-foreground">{item.account}</span>
            )}
            {branch && <span className="text-xs text-muted-foreground">{branch}</span>}
          </span>

          {/* The reason, not the number, is the first thing read. */}
          {item.reasons.map((reason) => (
            <span key={reason} className="block text-xs leading-5 text-muted-foreground">
              {reason}
            </span>
          ))}

          {item.action && (
            <span className={cn('block text-xs leading-5 font-medium', tone.text)}>
              {item.action}
              {item.owner && (
                <span className="font-normal text-muted-foreground"> · {item.owner}</span>
              )}
            </span>
          )}
        </span>

        <span className="shrink-0 space-y-0.5 text-right">
          {SUMMARY_FIELDS.map((name) => {
            const column = columns.find((c) => c.name === name);
            const value = item.fields[name];
            if (!column || value === null || value === undefined) return null;
            return (
              <span key={name} className="block text-xs tabular-nums text-muted-foreground">
                {formatValue(value, column.unit)}
              </span>
            );
          })}
        </span>

        {open ? (
          <ChevronUp className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronDown className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground" />
        )}
      </button>

      {open && <ScoreBreakdown item={item} columns={columns} />}
    </li>
  );
}

function ScoreBreakdown({
  item,
  columns,
}: {
  item: WorklistItem;
  columns: Worklist['columns'];
}) {
  return (
    <div className="space-y-3 border-t border-border/60 px-3 py-2">
      <div className="space-y-1">
        <p className="flex items-center gap-1.5 text-xs font-medium text-foreground/80">
          <Scale className="h-3 w-3" aria-hidden />
          Priority {item.score.toFixed(2)}
        </p>
        <table className="w-full text-xs">
          <tbody>
            {item.weights.map((weight) => (
              <tr key={weight.id} className="text-muted-foreground">
                <td className="py-0.5 pr-2">{weight.label}</td>
                <td className="py-0.5 pr-2 text-right tabular-nums">
                  {weight.weight.toFixed(2)} × {weight.value.toFixed(2)}
                </td>
                <td className="py-0.5 text-right tabular-nums text-foreground/80">
                  {weight.contribution.toFixed(3)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-3">
        {columns.map((column) => {
          const value = item.fields[column.name];
          if (value === null || value === undefined || value === '') return null;
          return (
            <div key={column.name} className="min-w-0">
              <dt className="truncate text-muted-foreground">{column.label}</dt>
              <dd className="truncate text-foreground/90">
                {column.masked ? '—' : formatValue(value, column.unit)}
              </dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}

function Footer({ worklist, onExport }: { worklist: Worklist; onExport?: () => void }) {
  const [showGaps, setShowGaps] = useState(false);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {onExport && worklist.items.length > 0 && (
          <button
            type="button"
            onClick={onExport}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-muted/60',
              'px-3 py-1 text-xs text-foreground/80 transition-colors hover:bg-muted',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            )}
          >
            Save and export as CSV
          </button>
        )}

        {worklist.unavailable.length > 0 && (
          <button
            type="button"
            onClick={() => setShowGaps((v) => !v)}
            aria-expanded={showGaps}
            className="text-xs text-muted-foreground underline-offset-2 hover:underline"
          >
            {showGaps ? 'Hide' : 'What this list cannot see'}
          </button>
        )}
      </div>

      {/* Named rather than implied. A reader who does not know a promise-to-pay signal is
          missing will read the list as complete, which is the one way it misleads. */}
      {showGaps && (
        <ul className="space-y-1 text-xs leading-5 text-muted-foreground">
          {worklist.unavailable.map((entry) => (
            <li key={entry}>{entry}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
