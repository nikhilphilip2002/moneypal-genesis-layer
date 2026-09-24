import type { WorkbenchTurnData } from '@/components/workbench/WorkbenchTurn';
import type { WorkbenchTraceStep } from '@/lib/api';

export function visibleTraceSteps(
  updates: WorkbenchTraceStep[], active: boolean,
): WorkbenchTraceStep[] {
  const byId = new Map<string, WorkbenchTraceStep>();
  for (const update of updates) {
    const previous = byId.get(update.id);
    byId.set(update.id, { ...previous, ...update });
  }
  const steps = [...byId.values()];
  if (active) return steps;
  return steps.map((step) => {
    if (step.status !== 'running') return step;
    return { ...step, status: 'error', detail: 'Interrupted' };
  });
}

export function finishInterruptedTurn(
  turn: WorkbenchTurnData,
  aborted: boolean,
  message: string,
): WorkbenchTurnData {
  return {
    ...turn,
    executionTrace: (turn.executionTrace ?? []).map((step) => {
      if (step.status !== 'running') return step;
      return {
        ...step,
        status: 'error' as const,
        detail: aborted ? 'Stopped by user' : 'Stream interrupted',
      };
    }),
    queryRegistry: (turn.queryRegistry ?? []).map((query) => {
      if (query.status !== 'running' && query.status !== 'pending') return query;
      const status = aborted ? 'cancelled' : 'error';
      const errorCode = aborted ? 'CANCELLED' : 'STREAM_INTERRUPTED';
      return {
        ...query,
        status,
        error_code: errorCode,
        has_data: false,
        visual_available: false,
      };
    }),
    error: { message },
    stage: undefined,
    pending: [],
    done: true,
  };
}
