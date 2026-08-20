import { useCallback, useEffect, useRef, useState } from 'react';
import {
  nlq,
  type AnalysisResult,
  type ChartSpec,
  type DrillStep,
  type NlqClarification,
  type NlqRefusal,
  type NlqStage,
  type QuerySpec,
} from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import AnalysisCard from './AnalysisCard';
import ChartRenderer from './ChartRenderer';
import LineagePanel from './LineagePanel';
import NextQuestions from './NextQuestions';
import StickyFilters from './StickyFilters';
import {
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Loader2,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// The conversation. Refusals and clarifications are first-class answers here, not error
// toasts — a refusal that looks like a failure teaches users the product is broken, when in
// fact it is doing the most valuable thing it does.

type Turn = {
  id: string;
  question: string;
  resolvedQuestion?: string;
  stage?: NlqStage;
  planRoute?: string;
  planModel?: string;
  planSummary?: string;
  chart?: ChartSpec;
  analysis?: AnalysisResult;
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
    async (spec: QuerySpec, sourceTurn: Turn, label = 'Drill-down') => {
      // No LLM: a drill-down re-runs the spec directly, so it is instant and cannot be
      // misunderstood. A chip passes its own phrasing as the label, so a chain of them
      // reads back as the conversation it was rather than eight rows of "Drill-down".
      const id = `${sourceTurn.id}-drill-${Date.now()}`;
      setTurns((prev) => [
        ...prev,
        { id, question: label, stage: 'querying', done: false },
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

          <Card className="rounded-bl-md overflow-hidden">
            <CardContent className="p-4">
              <ThoughtProcessPanel turn={turn} />

              {turn.chart && (
                <>
                  <ChartRenderer
                    chart={turn.chart}
                    onDrilldown={(spec) => drilldown(spec, turn)}
                  />
                  <NextQuestions
                    steps={turn.chart.next_steps ?? []}
                    onPick={(step: DrillStep) => drilldown(step.spec, turn, step.question)}
                  />
                  <LineagePanel chart={turn.chart} />
                  <Feedback turn={turn} onRate={rate} />
                </>
              )}

              {turn.analysis && (
                <>
                  <AnalysisCard
                    analysis={turn.analysis}
                    onDrilldown={(spec, question) => drilldown(spec, turn, question)}
                  />
                  <Feedback turn={turn} onRate={rate} />
                </>
              )}

              {turn.clarification && (
                <Clarification clarification={turn.clarification} onPick={onAsk} />
              )}

              {turn.refusal && <Refusal refusal={turn.refusal} onPick={onAsk} />}

              {turn.error && <p className="text-sm text-muted-foreground">{turn.error}</p>}
            </CardContent>
          </Card>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}

function ThoughtProcessPanel({ turn }: { turn: Turn }) {
  const [isOpen, setIsOpen] = useState(!turn.done);

  // Keep panel open during streaming, auto-collapse when done unless user toggled
  useEffect(() => {
    if (!turn.done) {
      setIsOpen(true);
    }
  }, [turn.done]);

  const stages: { key: NlqStage; label: string }[] = [
    { key: 'understanding', label: 'Understanding question' },
    { key: 'planning', label: 'Planning query' },
    { key: 'writing_sql', label: 'Writing & validating SQL' },
    { key: 'querying', label: 'Querying warehouse' },
    { key: 'charting', label: 'Building visualization' },
  ];

  const currentStageIndex = turn.stage ? stages.findIndex((s) => s.key === turn.stage) : (turn.done ? stages.length : 0);

  return (
    <div className="mb-3 rounded-lg border border-border/60 bg-muted/20 text-xs overflow-hidden transition-all">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between px-3 py-2 text-muted-foreground hover:bg-accent/40 hover:text-foreground transition-colors"
      >
        <div className="flex items-center gap-2">
          {!turn.done ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-primary shrink-0" />
          ) : (
            <BrainCircuit className="h-3.5 w-3.5 text-primary shrink-0" />
          )}
          <span className="font-medium text-foreground">
            {!turn.done
              ? (turn.stage ? `Thinking: ${STAGE_LABEL[turn.stage]}...` : 'Thinking...')
              : 'Thought process & LLM reasoning'}
          </span>
          {turn.planRoute && (
            <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-mono font-medium text-primary uppercase">
              {turn.planRoute}
            </span>
          )}
          {turn.planModel && (
            <span className="hidden sm:inline rounded bg-muted px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
              {turn.planModel}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
          <span>{isOpen ? 'Collapse' : 'Expand'}</span>
          {isOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </div>
      </button>

      {isOpen && (
        <div className="border-t border-border/40 bg-background/50 p-3 space-y-3">
          {turn.resolvedQuestion && turn.resolvedQuestion !== turn.question && (
            <div className="flex items-start gap-1.5 rounded-md bg-accent/40 p-2 text-foreground/90">
              <Sparkles className="h-3.5 w-3.5 text-primary shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-xs">Interpreted query: </span>
                <span className="italic">“{turn.resolvedQuestion}”</span>
              </div>
            </div>
          )}

          <div className="space-y-1.5">
            <span className="text-[10px] uppercase font-semibold tracking-wider text-muted-foreground/80">Execution Steps</span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              {stages.map((stg, i) => {
                const isFinished = turn.done || (currentStageIndex >= 0 && i < currentStageIndex);
                const isCurrent = !turn.done && i === currentStageIndex;
                return (
                  <div key={stg.key} className="flex items-center gap-1.5">
                    {isFinished ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                    ) : isCurrent ? (
                      <Loader2 className="h-3.5 w-3.5 text-primary animate-spin shrink-0" />
                    ) : (
                      <span className="h-3.5 w-3.5 rounded-full border border-muted-foreground/30 shrink-0" />
                    )}
                    <span className={cn(isFinished ? 'text-foreground/90 font-medium' : isCurrent ? 'text-primary font-semibold' : 'text-muted-foreground/50')}>
                      {stg.label}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {turn.planSummary && (
            <div className="space-y-1 pt-1.5 border-t border-border/40">
              <span className="text-[10px] uppercase font-semibold tracking-wider text-muted-foreground/80">LLM Planning Rationale</span>
              <p className="text-xs text-foreground/90 leading-relaxed font-mono bg-muted/40 p-2 rounded-md border border-border/30">
                {turn.planSummary}
              </p>
            </div>
          )}
        </div>
      )}
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

function Refusal({
  refusal, onPick,
}: {
  refusal: NlqRefusal;
  onPick: (question: string) => void;
}) {
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
          <div className="mt-2 flex flex-wrap gap-2">
            {refusal.examples.map((example) => (
              <Button
                key={example}
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onPick(example)}
                className="h-auto min-h-7 whitespace-normal rounded-full px-3 py-1 text-left text-xs font-normal"
              >
                {example}
              </Button>
            ))}
          </div>
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
