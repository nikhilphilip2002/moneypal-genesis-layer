'use client';

import { Loader2, AlertTriangle, Ban, HelpCircle, Sparkles } from 'lucide-react';
import { nlq, type AnalysisResult, type ChartSpec, type QuerySpec, type Briefing, type Worklist,
  type WorkbenchAnswer, type WorkbenchCard as CardData } from '@/lib/api';
import AnalysisCard from '@/components/nlq/AnalysisCard';
import ChartRenderer from '@/components/nlq/ChartRenderer';
import NextQuestions from '@/components/nlq/NextQuestions';
import BriefingCard from '@/components/nlq/BriefingCard';
import WorklistCard from '@/components/nlq/WorklistCard';
import LineagePanel from '@/components/nlq/LineagePanel';
import BriefRenderer from '@/components/intel/BriefRenderer';
import WorkbenchCard from './WorkbenchCard';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import StatusRow from '@/components/ui/status-row';
import { BLOCK_GAP, SOURCE_BADGE, SUGGESTION_CHIP, sourceLabel } from '@/lib/workbench-ui';

// One conversational turn: the question, the route the orchestrator chose, an optional
// merged synthesis lead, and a card per source. Cards stream in as each source returns, so
// this renders progressively — a pending source shows a spinner rather than blocking.
//
// Every non-card message here — loading, refusal, error, partial, clarification — is a
// StatusRow, so an icon never sits half a line below the text it belongs to.

export type WorkbenchTurnData = {
  id: string;
  question: string;
  stage?: string;
  route?: { sources: string[]; intent: string };
  pending: string[]; // source ids dispatched but not yet returned
  cards: CardData[];
  answer?: WorkbenchAnswer;
  synthesis?: string;
  refusal?: { reason: string; message: string };
  error?: string;
  legacyAnswerUnavailable?: boolean;
  partial?: boolean;
  done: boolean;
};

const BRIEF_TITLES: Record<string, string> = {
  macro: 'Macro brief', competitive: 'Competitive brief', regulatory: 'Regulatory brief',
  knowledge: 'Concept explained',
};

export default function WorkbenchTurn({ turn, onAsk }: { turn: WorkbenchTurnData; onAsk: (q: string) => void }) {
  const hasFinalAnswer = Boolean(turn.answer || turn.synthesis);
  const supportingCards = hasFinalAnswer
    ? turn.cards.filter((card) => ['chart', 'analysis', 'worklist', 'briefing', 'schema'].includes(card.card_type))
    : (turn.done ? turn.cards : []);
  const answerText = turn.answer?.text || turn.synthesis;
  return (
    <section className="space-y-5">
      <div className="flex justify-end">
        <div className="max-w-[88%] rounded-2xl rounded-br-md border border-border/50 bg-muted px-4 py-2.5 text-sm leading-6 text-foreground shadow-none sm:max-w-[78%]">
          {turn.question}
        </div>
      </div>

      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1 space-y-3">
          {!turn.done && turn.stage && !turn.route && (
            <StatusRow icon={Loader2} spin className="py-1">
              <span className="capitalize">{turn.stage}…</span>
            </StatusRow>
          )}

          {answerText && (
            <div className="text-sm leading-7 text-foreground">
              <BriefRenderer content={answerText} />
            </div>
          )}

          {supportingCards.map((card, index) => (
            <CardBody key={`${card.source}-${index}`} card={card} onAsk={onAsk} />
          ))}

          {turn.answer?.status === 'partial' && turn.answer.unavailable_sources.length > 0 && (
            <StatusRow icon={AlertTriangle} tone="warning" surface className="text-muted-foreground">
              Answered with available evidence; {turn.answer.unavailable_sources.map((item) => sourceLabel(item.source)).join(', ')} could not contribute.
            </StatusRow>
          )}

          {turn.pending
            .filter((source) => !turn.cards.some((card) => card.source === source))
            .map((source) => (
              <StatusRow key={source} icon={Loader2} spin size="sm" className="py-1">
                Checking {sourceLabel(source)}…
              </StatusRow>
            ))}

          {!turn.done && turn.route && !hasFinalAnswer && turn.pending.every(
            (source) => turn.cards.some((card) => card.source === source),
          ) && (
            <StatusRow icon={Loader2} spin className="py-1">
              Combining findings…
            </StatusRow>
          )}

          {turn.refusal && !hasFinalAnswer && (
            <StatusRow icon={Ban} tone="warning" surface label="Not answerable:">
              {turn.refusal.message || 'That request cannot be handled here.'}
            </StatusRow>
          )}

          {turn.error && (
            <StatusRow icon={AlertTriangle} tone="danger" surface>
              {turn.error}
            </StatusRow>
          )}

          {turn.legacyAnswerUnavailable && !turn.error && turn.cards.length === 0 && (
            <StatusRow icon={AlertTriangle} surface>
              This question was saved before answer history was enabled. Its original answer card was not retained.
            </StatusRow>
          )}

          {turn.partial && !turn.error && (
            <StatusRow icon={AlertTriangle} tone="warning" surface className="text-muted-foreground">
              This response was interrupted. Completed answer cards were retained.
            </StatusRow>
          )}

          {turn.done && turn.route && turn.route.sources.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
              <span className="text-[11px] leading-5 text-muted-foreground">Sources</span>
              {(turn.answer?.sources.length ? turn.answer.sources : turn.route.sources).map((source) => (
                <Badge key={source} variant="outline" className={`${SOURCE_BADGE} text-muted-foreground`}>
                  {sourceLabel(source)}
                </Badge>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

// Saving is what makes the export meaningful: the CSV is the frozen list somebody is
// working, not a fresh evaluation of the rules that would drop whatever was paid overnight.
async function exportWorklist(worklist: Worklist) {
  const saved = await nlq.worklist(worklist.id, { save: true });
  const blob = await nlq.exportWorklist(saved.id);
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${worklist.id}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function CardBody({ card, onAsk }: { card: CardData; onAsk: (q: string) => void }) {
  if (card.card_type === 'chart') {
    const chart = card.payload as ChartSpec;
    return (
      <WorkbenchCard source={card.source} title={chart.title || 'Result'} subtitle={chart.subtitle ?? undefined}>
        <ChartRenderer chart={chart} hideHeader />
        {/* In the workbench a chip re-asks in words rather than executing the spec
            directly: the turn has to go through the router so it lands in history with its
            sources, exactly like any other question the user types. */}
        <NextQuestions
          steps={chart.next_steps ?? []}
          onPick={(step) => onAsk(step.question)}
        />
        <LineagePanel chart={chart} sourceLabel="Loan book" />
      </WorkbenchCard>
    );
  }

  if (card.card_type === 'analysis') {
    const analysis = card.payload as AnalysisResult;
    return (
      <WorkbenchCard
        source={card.source}
        title={analysis.title || 'Analysis'}
        subtitle={analysis.subtitle || undefined}
      >
        {/* Findings and charts both re-ask in words here rather than executing the spec:
            a workbench turn has to go through the router to land in history with its
            sources, exactly like any question the user types. */}
        <AnalysisCard
          analysis={analysis}
          onDrilldown={(_spec: QuerySpec, question: string) => onAsk(question)}
        />
      </WorkbenchCard>
    );
  }

  if (card.card_type === 'briefing') {
    const briefing = card.payload as Briefing;
    return (
      <WorkbenchCard source={card.source} title={briefing.label || 'Briefing'}>
        {/* Drilling re-asks in words, like every other card here: a workbench turn has to go
            through the router to land in history with its sources. */}
        <BriefingCard
          briefing={briefing}
          onDrilldown={(_spec: QuerySpec, question: string) => onAsk(question)}
        />
      </WorkbenchCard>
    );
  }

  if (card.card_type === 'worklist') {
    const worklist = card.payload as Worklist;
    return (
      <WorkbenchCard
        source={card.source}
        title={worklist.title || 'Worklist'}
        subtitle={worklist.subtitle || undefined}
      >
        <WorklistCard
          worklist={worklist}
          onExport={() => exportWorklist(worklist)}
        />
      </WorkbenchCard>
    );
  }

  if (card.card_type === 'brief') {
    const { summary, key_points, sources } = card.payload as {
      summary: string;
      key_points?: string[];
      sources?: { document: string; page?: number }[];
    };
    return (
      <WorkbenchCard source={card.source} title={BRIEF_TITLES[card.source] ?? 'Brief'}>
        <BriefRenderer content={summary} />
        {key_points && key_points.length > 0 && (
          <ul className={`${BLOCK_GAP} list-disc space-y-1 pl-4 text-xs leading-5 text-muted-foreground`}>
            {key_points.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        )}
        {sources && sources.length > 0 && (
          <div className={`${BLOCK_GAP} flex flex-wrap gap-1.5`}>
            {sources.map((s, i) => (
              <Badge key={i} variant="outline" className={`${SOURCE_BADGE} normal-case tracking-normal text-muted-foreground`}>
                {s.document}{s.page ? `, p.${s.page}` : ''}
              </Badge>
            ))}
          </div>
        )}
      </WorkbenchCard>
    );
  }

  if (card.card_type === 'schema') {
    const { nodes, edges, node_count, edge_count } = card.payload as {
      nodes?: { id: string; label: string }[];
      edges?: { source: string; target: string; label?: string }[];
      node_count: number;
      edge_count: number;
    };
    const labelOf = (id: string) => nodes?.find((n) => n.id === id)?.label ?? id;
    return (
      <WorkbenchCard source={card.source} title="Schema" subtitle={`${node_count} tables · ${edge_count} relationships`}>
        <div className="flex flex-wrap gap-1.5">
          {(nodes ?? []).map((n) => (
            <Badge key={n.id} variant="secondary" className={`${SOURCE_BADGE} font-mono normal-case tracking-normal`}>
              {n.label}
            </Badge>
          ))}
        </div>
        {edges && edges.length > 0 && (
          <ul className={`${BLOCK_GAP} space-y-1 text-xs leading-5 text-muted-foreground`}>
            {edges.slice(0, 12).map((e, i) => (
              <li key={i} className="font-mono">
                {labelOf(e.source)} <span className="text-foreground">→</span> {labelOf(e.target)}
                {e.label ? <span className="ml-1 opacity-70">({e.label})</span> : null}
              </li>
            ))}
          </ul>
        )}
      </WorkbenchCard>
    );
  }

  if (card.card_type === 'clarify') {
    const { question, suggestions } = card.payload as { question: string; suggestions?: string[] };
    return (
      <WorkbenchCard source={card.source} title="Clarification needed" collapsible={false}>
        <StatusRow icon={HelpCircle} tone="info" label="Clarification needed:">
          {question}
        </StatusRow>
        {suggestions && suggestions.length > 0 && (
          <div className={`${BLOCK_GAP} flex flex-wrap gap-1.5`}>
            {suggestions.map((s) => (
              <Button key={s} size="sm" variant="outline" className={SUGGESTION_CHIP} onClick={() => onAsk(s)}>
                {s}
              </Button>
            ))}
          </div>
        )}
      </WorkbenchCard>
    );
  }

  if (card.card_type === 'refusal') {
    const { message, examples } = card.payload as { message: string; examples?: string[] };
    return (
      <WorkbenchCard source={card.source} title="Not answerable" collapsible={false}>
        <StatusRow icon={Ban} tone="warning" label="Not answerable:">
          {message}
        </StatusRow>
        {examples && examples.length > 0 && (
          <div className={`${BLOCK_GAP} flex flex-wrap gap-1.5`}>
            {examples.map((s) => (
              <Button key={s} size="sm" variant="outline" className={SUGGESTION_CHIP} onClick={() => onAsk(s)}>
                {s}
              </Button>
            ))}
          </div>
        )}
      </WorkbenchCard>
    );
  }

  // error
  return (
    <WorkbenchCard source={card.source} title="Error" collapsible={false}>
      <StatusRow icon={AlertTriangle} tone="danger">
        {(card.payload as { message?: string }).message || 'Something went wrong.'}
      </StatusRow>
    </WorkbenchCard>
  );
}
