'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Bot,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  Loader2,
  Wrench,
} from 'lucide-react';
import type { WorkbenchTraceStep } from '@/lib/api';
import { cn } from '@/lib/utils';

function formatDuration(ms: number) {
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)} s`;
}

function latestSteps(updates: WorkbenchTraceStep[]) {
  const byId = new Map<string, WorkbenchTraceStep>();
  for (const update of updates) {
    const previous = byId.get(update.id);
    byId.set(update.id, { ...previous, ...update });
  }
  return [...byId.values()];
}

export default function ExecutionTrace({
  updates,
  active,
  startedAt,
  totalMs,
}: {
  updates: WorkbenchTraceStep[];
  active: boolean;
  startedAt?: number;
  totalMs?: number;
}) {
  const [open, setOpen] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const steps = useMemo(() => latestSteps(updates), [updates]);

  useEffect(() => {
    if (!active || !startedAt) return;
    const timer = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(timer);
  }, [active, startedAt]);

  const streamedElapsed = Math.max(0, ...updates.map((step) => step.elapsed_ms || 0));
  const elapsed = totalMs ?? (active && startedAt ? now - startedAt : streamedElapsed);
  const running = [...steps].reverse().find((step) => step.status === 'running');
  const failures = steps.filter((step) => step.status === 'error').length;

  return (
    <div className="overflow-hidden rounded-xl border border-border/60 bg-muted/15">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex min-h-11 w-full items-center gap-2.5 px-3 py-2 text-left transition-colors hover:bg-muted/25"
      >
        {active ? (
          <Loader2 className="size-4 shrink-0 animate-spin text-primary" />
        ) : failures ? (
          <CircleAlert className="size-4 shrink-0 text-amber-500" />
        ) : (
          <CheckCircle2 className="size-4 shrink-0 text-emerald-500" />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-xs font-medium text-foreground">
            <span>{active ? 'Working' : 'Execution trace'}</span>
            <span className="font-mono text-[10px] font-normal tabular-nums text-muted-foreground">
              {formatDuration(elapsed)}
            </span>
          </div>
          <p className="truncate text-[11px] text-muted-foreground">
            {running?.label || `${steps.length} model and tool step${steps.length === 1 ? '' : 's'}`}
          </p>
        </div>
        <ChevronDown className={cn(
          'size-4 shrink-0 text-muted-foreground transition-transform', open && 'rotate-180',
        )} />
      </button>

      {open && (
        <div className="space-y-3 border-t border-border/60 px-3 py-3">
          {steps.length === 0 ? (
            <p className="text-xs text-muted-foreground">Waiting for the first model step…</p>
          ) : steps.map((step) => {
            const Icon = step.kind === 'tool' ? Wrench : Bot;
            return (
              <div key={step.id} className="flex gap-2.5">
                <div className="pt-0.5">
                  {step.status === 'running' ? (
                    <Loader2 className="size-3.5 animate-spin text-primary" />
                  ) : step.status === 'error' ? (
                    <CircleAlert className="size-3.5 text-amber-500" />
                  ) : (
                    <Icon className="size-3.5 text-muted-foreground" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                    <span className="font-mono text-[11px] font-medium text-foreground">
                      {step.label}
                    </span>
                    <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
                      {step.duration_ms !== undefined
                        ? formatDuration(step.duration_ms)
                        : `at ${formatDuration(step.elapsed_ms)}`}
                    </span>
                  </div>
                  {step.detail && (
                    <p className="mt-0.5 break-words text-[11px] leading-4 text-muted-foreground">
                      {step.detail}
                    </p>
                  )}
                  {step.arguments && Object.keys(step.arguments).length > 0 && (
                    <details className="mt-1.5">
                      <summary className="cursor-pointer select-none text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                        Arguments
                      </summary>
                      <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-muted/40 p-2 font-mono text-[10px] leading-4 text-foreground">
                        {JSON.stringify(step.arguments, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              </div>
            );
          })}
          <p className="border-t border-border/50 pt-2 text-[10px] leading-4 text-muted-foreground">
            Shows model actions and sanitized tool activity. Private chain-of-thought is not exposed.
          </p>
        </div>
      )}
    </div>
  );
}
