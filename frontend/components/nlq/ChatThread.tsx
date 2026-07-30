'use client';

import { useCallback, useEffect, useRef } from 'react';
import {
  nlq,
  type ChartSpec,
  type NlqClarification,
  type NlqRefusal,
  type NlqStage,
  type QuerySpec,
} from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import ChartRenderer from './ChartRenderer';
import LineagePanel from './LineagePanel';
import StickyFilters from './StickyFilters';
import { ThumbsDown, ThumbsUp } from 'lucide-react';
import { cn } from '@/lib/utils';

// The conversation. Refusals and clarifications are first-class answers here, not error
// toasts — a refusal that looks like a failure teaches users the product is broken, when in
// fact it is doing the most valuable thing it does.

type Turn = {
  id: string;
  question: string;
  resolvedQuestion?: string;
  stage?: NlqStage;
  chart?: ChartSpec;
  clarification?: NlqClarification;
  refusal?: NlqRefusal;
  error?: string;
  turnId?: string;
  feedback?: 'up' | 'down';
  done: boolean;
};

const STAGE_LABEL: Record<NlqStage, string> = {
  understanding: 'Understanding the question',
  planning: 'Planning the query',
  writing_sql: 'Writing SQL',
  querying: 'Querying the warehouse',
  charting: 'Building the chart',
};

export default function ChatThread({
  turns, setTurns, conversationId, onAsk,
}: {
  turns: Turn[];
  setTurns: React.Dispatch<React.SetStateAction<Turn[]>>;
  conversationId: string | null;
  onAsk: (question: string) => void;
}) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [turns]);

  const drilldown = useCallback(
    async (spec: QuerySpec, sourceTurn: Turn) => {
      // No LLM: a drill-down re-runs the spec directly, so it is instant and cannot be
      // misunderstood.
      const id = `${sourceTurn.id}-drill-${Date.now()}`;
      setTurns((prev) => [
        ...prev,
        { id, question: 'Drill-down', stage: 'querying', done: false },
      ]);
      try {
        const chart = await nlq.execute(spec);
        setTurns((prev) =>
          prev.map((t) => (t.id === id ? { ...t, chart, done: true, stage: undefined } : t)),
        );
      } catch (err: any) {
        setTurns((prev) =>
          prev.map((t) =>
            t.id === id ? { ...t, error: err.message ?? 'Drill-down failed', done: true } : t,
          ),
        );
      }
    },
    [setTurns],
  );

  const rate = async (turn: Turn, verdict: 'up' | 'down') => {
    if (!turn.turnId) return;
    setTurns((prev) => prev.map((t) => (t.id === turn.id ? { ...t, feedback: verdict } : t)));
    try {
      await nlq.feedback(turn.turnId, verdict);
    } catch {
      /* the rating is advisory; a failed write must not disturb the thread */
    }
  };

  return (
    <div className="space-y-6">
      {conversationId && <StickyFilters conversationId={conversationId} />}

      {turns.map((turn) => (
        <div key={turn.id} className="space-y-2">
          <div className="flex justify-end">
            <div
              className={cn(
                'max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2 text-sm text-primary-foreground',
                'shadow-[0_4px_16px_rgba(0,93,170,0.30),0_1px_0_rgba(255,255,255,0.20)_inset]',
                'dark:shadow-[0_4px_16px_rgba(0,0,0,0.40),0_1px_0_rgba(255,255,255,0.10)_inset]',
              )}
            >
              {turn.question}
            </div>
          </div>

          {turn.resolvedQuestion && turn.resolvedQuestion !== turn.question && (
            <p className="text-right text-xs text-muted-foreground">
              interpreted as “{turn.resolvedQuestion}”
            </p>
          )}

          <Card className="rounded-bl-md">
            <CardContent className="p-4">
              {!turn.done && turn.stage && <StageIndicator stage={turn.stage} />}

              {turn.chart && (
                <>
                  <ChartRenderer
                    chart={turn.chart}
                    onDrilldown={(spec) => drilldown(spec, turn)}
                  />
                  <LineagePanel chart={turn.chart} />
                  <Feedback turn={turn} onRate={rate} />
                </>
              )}

              {turn.clarification && (
                <Clarification clarification={turn.clarification} onPick={onAsk} />
              )}

              {turn.refusal && <Refusal refusal={turn.refusal} />}

              {turn.error && <p className="text-sm text-muted-foreground">{turn.error}</p>}
            </CardContent>
          </Card>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}

function StageIndicator({ stage }: { stage: NlqStage }) {
  const order: NlqStage[] = ['understanding', 'planning', 'querying', 'charting'];
  const index = order.indexOf(stage);
  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <span className="flex gap-1">
        {order.map((s, i) => (
          <span
            key={s}
            className={cn(
              'h-1.5 w-6 rounded-full transition-colors duration-200',
              i <= index ? 'bg-primary' : 'bg-muted',
            )}
          />
        ))}
      </span>
      {STAGE_LABEL[stage] ?? stage}…
    </div>
  );
}

// A clarification offers tappable options. Asking a question and then making the user
// retype their whole request is the worst of both worlds.
function Clarification({
  clarification, onPick,
}: { clarification: NlqClarification; onPick: (question: string) => void }) {
  return (
    <div>
      <p className="text-sm text-foreground">{clarification.question}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {clarification.suggestions.map((suggestion) => (
          <Button
            key={suggestion}
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onPick(suggestion)}
            className="h-7 rounded-full text-xs font-normal"
          >
            {suggestion}
          </Button>
        ))}
      </div>
    </div>
  );
}

const REFUSAL_HEADING: Record<NlqRefusal['reason'], string> = {
  predictive: 'I report what the loan book shows, and do not forecast.',
  advice: 'I do not make recommendations.',
  not_in_data: 'That is not answerable from the loan book.',
  out_of_scope: 'That is outside what I cover.',
  unsafe: 'I cannot do that.',
};

function Refusal({ refusal }: { refusal: NlqRefusal }) {
  return (
    <div>
      <p className="text-sm font-medium text-foreground">{REFUSAL_HEADING[refusal.reason]}</p>
      {refusal.message && (
        <p className="mt-1 text-sm text-muted-foreground">{refusal.message}</p>
      )}
      {refusal.examples.length > 0 && (
        <>
          <p className="mt-3 text-xs uppercase tracking-wide text-muted-foreground">
            Try instead
          </p>
          <ul className="mt-1 space-y-1">
            {refusal.examples.map((example) => (
              <li key={example} className="text-sm text-foreground/80">
                • {example}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function Feedback({
  turn, onRate,
}: { turn: Turn; onRate: (turn: Turn, verdict: 'up' | 'down') => void }) {
  if (!turn.turnId) return null;
  return (
    <div className="mt-2 flex items-center gap-1">
      <span className="mr-1 text-xs text-muted-foreground">Was this right?</span>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label="Helpful"
        onClick={() => onRate(turn, 'up')}
        className={cn('h-7 w-7', turn.feedback === 'up' && 'text-emerald-600 dark:text-emerald-400')}
      >
        <ThumbsUp className="h-3.5 w-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label="Not helpful"
        onClick={() => onRate(turn, 'down')}
        className={cn('h-7 w-7', turn.feedback === 'down' && 'text-red-600 dark:text-red-400')}
      >
        <ThumbsDown className="h-3.5 w-3.5" />
      </Button>
    </div>
  );
}

export type { Turn };
