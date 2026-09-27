'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Bot,
  ChevronRight,
  CircleAlert,
  Loader2,
  Wrench,
} from 'lucide-react';
import type { WorkbenchTraceStep } from '@/lib/api';
import { cn } from '@/lib/utils';
import { visibleTraceSteps } from '@/lib/workbench-cancellation';

function formatDuration(ms: number) {
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)} s`;
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
  const [open, setOpen] = useState(active);
  const [now, setNow] = useState(() => Date.now());
  const steps = useMemo(() => visibleTraceSteps(updates, active), [updates, active]);

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
    <div>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex min-h-8 max-w-full items-center gap-2 py-1 text-left text-muted-foreground transition-colors hover:text-foreground"
      >
        <ChevronRight className={cn(
          'size-4 shrink-0 transition-transform',
          open && 'rotate-90',
          active ? 'text-primary' : failures ? 'text-amber-500' : 'text-emerald-500',
        )} aria-hidden />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-xs font-medium">
            <span>{active ? 'Working…' : 'How this answer was prepared'}</span>
            <span className="font-mono text-[10px] font-normal tabular-nums text-muted-foreground">
              {formatDuration(elapsed)}
            </span>
          </div>
          <p className="truncate text-[11px] text-muted-foreground">
            {running?.label || `${steps.length} model and tool step${steps.length === 1 ? '' : 's'}`}
          </p>
        </div>
      </button>

      {open && (
        <div className="ml-2 space-y-3 border-l-2 border-border/70 py-2 pl-4">
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
                  {step.reasoning && (
                    <div className="mt-1.5">
                      <p className="whitespace-pre-wrap break-words text-xs leading-5 text-muted-foreground">
                        {step.reasoning}
                      </p>
                    </div>
                  )}
                  {step.tool_calls && step.tool_calls.length > 0 && (
                    <div className="mt-1.5 space-y-1">
                      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                        Model tool calls
                      </p>
                      {step.tool_calls.map((call) => (
                        <div key={`${call.index}-${call.id ?? ''}`} className="flex items-center gap-1.5 font-mono text-[10px] text-foreground">
                          <Wrench className="size-3 shrink-0 text-muted-foreground" />
                          <span>{call.name || 'Receiving tool call…'}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {step.arguments && Object.keys(step.arguments).length > 0 && (
                    <details className="mt-1.5">
                      <summary className="cursor-pointer select-none text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                        Arguments
                      </summary>
                      <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap break-all font-mono text-[10px] leading-4 text-foreground">
                        {JSON.stringify(step.arguments, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
