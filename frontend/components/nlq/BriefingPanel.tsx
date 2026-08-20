'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  Check,
  Eye,
  Info,
  Loader2,
  RefreshCw,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { nlq, type Briefing, type Persona, type QuerySpec, type Severity, type Signal } from '@/lib/api';
import AnalysisCard from './AnalysisCard';
import WorklistCard from './WorklistCard';
import { cn } from '@/lib/utils';

// The morning read. Signals lead, indicators follow, the list to work sits at the bottom.
//
// The order is the product. A panel that opens with seven KPI tiles asks the reader to work
// out what matters; one that opens with "two things need attention" has already done it, and
// the tiles are underneath for whoever wants them.
//
// Nothing here is generated at read time. The scan ran hours ago and stored its findings, so
// opening this costs one indexed query rather than eleven warehouse scans — which is also why
// the numbers are identical for two people opening it at the same moment.

const SEVERITY: Record<Severity, { icon: typeof Info; ring: string; text: string }> = {
  alert: { icon: AlertTriangle, ring: 'border-destructive/40 bg-destructive/5', text: 'text-destructive' },
  watch: { icon: Eye, ring: 'border-amber-500/40 bg-amber-500/5', text: 'text-amber-600 dark:text-amber-400' },
  info: { icon: Info, ring: 'border-border bg-muted/40', text: 'text-muted-foreground' },
};

export default function BriefingPanel({
  onDrilldown,
}: {
  onDrilldown?: (spec: QuerySpec, question: string) => void;
}) {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [personaId, setPersonaId] = useState<string>('');
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    nlq.personas()
      .then(({ personas: list }) => {
        setPersonas(list);
        setPersonaId((current) => current || list[0]?.id || '');
      })
      .catch((err) => setError(err.message ?? 'Could not load the desks.'));
  }, []);

  const load = useCallback(async (id: string) => {
    if (!id) return;
    setLoading(true);
    setError('');
    try {
      setBriefing(await nlq.briefing(id));
    } catch (err: any) {
      setError(err.message ?? 'The briefing could not be prepared.');
      setBriefing(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(personaId); }, [personaId, load]);

  return (
    <div className="w-full space-y-5">
      <header className="flex flex-wrap items-center gap-2">
        {personas.map((persona) => (
          <button
            key={persona.id}
            type="button"
            onClick={() => setPersonaId(persona.id)}
            title={persona.description}
            className={cn(
              'rounded-full border px-3 py-1 text-xs transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              persona.id === personaId
                ? 'border-primary/50 bg-primary/10 text-primary'
                : 'border-border/70 bg-muted/60 text-foreground/80 hover:bg-muted',
            )}
          >
            {persona.label}
          </button>
        ))}

        <button
          type="button"
          onClick={() => load(personaId)}
          disabled={loading}
          className="ml-auto inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50"
        >
          {loading ? (
            <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
          ) : (
            <RefreshCw className="h-3 w-3" aria-hidden />
          )}
          Refresh
        </button>
      </header>

      {error && <p className="text-sm text-muted-foreground">{error}</p>}

      {briefing && (
        <>
          <p className="text-sm leading-6 text-foreground/90">{briefing.headline}</p>

          {briefing.signals.length > 0 && (
            <ul className="space-y-2">
              {briefing.signals.map((signal) => (
                <SignalRow
                  key={signal.id}
                  signal={signal}
                  onDrilldown={onDrilldown}
                  onAcknowledged={() => load(personaId)}
                />
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
        </>
      )}
    </div>
  );
}

function SignalRow({
  signal,
  onDrilldown,
  onAcknowledged,
}: {
  signal: Signal;
  onDrilldown?: (spec: QuerySpec, question: string) => void;
  onAcknowledged?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const tone = SEVERITY[signal.severity];
  const Icon = tone.icon;
  const Arrow = signal.direction === 'up' ? TrendingUp : signal.direction === 'down' ? TrendingDown : null;
  const acknowledged = signal.status === 'acknowledged';

  const acknowledge = async () => {
    setBusy(true);
    try {
      await nlq.setSignalStatus(signal.id, 'acknowledged');
      onAcknowledged?.();
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

        {/* The evidence, one click away. A finding the reader cannot verify is one they have
            to take on faith, which is the thing this product does not ask of them. */}
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
      {!acknowledged ? (
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
