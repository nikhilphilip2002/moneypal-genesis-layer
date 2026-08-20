'use client';

import { useState } from 'react';
import { AlertTriangle, Check, Eye, Info, Loader2, TrendingDown, TrendingUp } from 'lucide-react';
import { nlq, type Briefing, type QuerySpec, type Severity, type Signal } from '@/lib/api';
import AnalysisCard from './AnalysisCard';
import WorklistCard from './WorklistCard';
import { cn } from '@/lib/utils';

// "What do I need to know?" answered in the thread, like every other question.
//
// Signals lead, indicators follow, the list to work sits at the bottom. The order is the
// product: an answer that opens with seven KPI tiles asks the reader to work out what
// matters, while one that opens with "two things need attention" has already done it.
//
// Nothing here is computed at read time. The scan ran hours ago and stored its findings, so
// this costs one indexed read rather than eleven warehouse scans — which is also why two
// people asking at the same moment get identical numbers.

const SEVERITY: Record<Severity, { icon: typeof Info; ring: string; text: string }> = {
  alert: { icon: AlertTriangle, ring: 'border-destructive/40 bg-destructive/5', text: 'text-destructive' },
  watch: { icon: Eye, ring: 'border-amber-500/40 bg-amber-500/5', text: 'text-amber-600 dark:text-amber-400' },
  info: { icon: Info, ring: 'border-border bg-muted/40', text: 'text-muted-foreground' },
};

export default function BriefingCard({
  briefing,
  onDrilldown,
}: {
  briefing: Briefing;
  onDrilldown?: (spec: QuerySpec, question: string) => void;
}) {
  return (
    <div className="w-full space-y-4">
      <header className="space-y-1">
        <span className="text-xs text-muted-foreground">{briefing.label}</span>
        {briefing.headline && (
          <p className="text-sm leading-6 text-foreground/90">{briefing.headline}</p>
        )}
      </header>

      {briefing.signals.length > 0 && (
        <ul className="space-y-2">
          {briefing.signals.map((signal) => (
            <SignalRow key={signal.id} signal={signal} onDrilldown={onDrilldown} />
          ))}
        </ul>
      )}

      {briefing.warnings.length > 0 && (
        <ul className="space-y-1">
          {briefing.warnings.map((warning) => (
            <li key={warning} className="text-xs leading-5 text-muted-foreground">
              {warning}
            </li>
          ))}
        </ul>
      )}

      {briefing.analyses.map((analysis) => (
        <div key={analysis.id} className="rounded-lg border border-border/70 p-3">
          <AnalysisCard analysis={analysis} onDrilldown={onDrilldown} />
        </div>
      ))}

      {briefing.worklists.map((worklist) => (
        <div key={worklist.id} className="rounded-lg border border-border/70 p-3">
          <WorklistCard worklist={worklist} />
        </div>
      ))}
    </div>
  );
}

function SignalRow({
  signal,
  onDrilldown,
}: {
  signal: Signal;
  onDrilldown?: (spec: QuerySpec, question: string) => void;
}) {
  const [status, setStatus] = useState(signal.status);
  const [busy, setBusy] = useState(false);
  const tone = SEVERITY[signal.severity];
  const Icon = tone.icon;
  const Arrow =
    signal.direction === 'up' ? TrendingUp : signal.direction === 'down' ? TrendingDown : null;

  const acknowledge = async () => {
    setBusy(true);
    try {
      await nlq.setSignalStatus(signal.id, 'acknowledged');
      setStatus('acknowledged');
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className={cn('flex items-start gap-2 rounded-lg border px-3 py-2', tone.ring)}>
      <Icon className={cn('mt-0.5 h-3.5 w-3.5 shrink-0', tone.text)} aria-hidden />

      <span className="min-w-0 flex-1 space-y-1">
        <span className="flex items-start gap-1.5 text-sm leading-6 text-foreground/90">
          {Arrow && <Arrow className={cn('mt-1 h-3 w-3 shrink-0', tone.text)} aria-hidden />}
          <span>{signal.text}</span>
        </span>

        {/* The evidence, one click away — and it re-asks in the thread rather than opening a
            panel, so the chain stays a conversation. A finding the reader cannot verify is
            one they have to take on faith, which is the thing this product does not ask. */}
        {signal.spec && onDrilldown && (
          <button
            type="button"
            onClick={() => onDrilldown(signal.spec as QuerySpec, signal.label)}
            className="text-xs text-primary underline-offset-2 hover:underline"
          >
            Show me
          </button>
        )}
      </span>

      {/* Acknowledging says "I have seen this", not "this is fixed": the signal stays in the
          feed so a standing deterioration cannot disappear by being read. */}
      {status !== 'acknowledged' ? (
        <button
          type="button"
          onClick={acknowledge}
          disabled={busy}
          title="I have seen this"
          className="shrink-0 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50"
        >
          {busy ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden /> : 'Seen'}
        </button>
      ) : (
        <Check className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground" aria-hidden />
      )}
    </li>
  );
}
