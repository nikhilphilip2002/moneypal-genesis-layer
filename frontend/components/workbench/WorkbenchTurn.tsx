'use client';

import { Loader2, AlertTriangle, Ban, HelpCircle, Sparkles } from 'lucide-react';
import type { ChartSpec, WorkbenchCard as CardData } from '@/lib/api';
import ChartRenderer from '@/components/nlq/ChartRenderer';
import LineagePanel from '@/components/nlq/LineagePanel';
import BriefRenderer from '@/components/intel/BriefRenderer';
import WorkbenchCard from './WorkbenchCard';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

// One conversational turn: the question, the route the orchestrator chose, an optional
// merged synthesis lead, and a card per source. Cards stream in as each source returns, so
// this renders progressively — a pending source shows a spinner rather than blocking.

export type WorkbenchTurnData = {
  id: string;
  question: string;
  stage?: string;
  route?: { sources: string[]; intent: string };
  pending: string[]; // source ids dispatched but not yet returned
  cards: CardData[];
  synthesis?: string;
  refusal?: { reason: string; message: string };
  error?: string;
  legacyAnswerUnavailable?: boolean;
  partial?: boolean;
  done: boolean;
};

const SOURCE_LABELS: Record<string, string> = {
  db: 'Loan book', macro: 'Macro', competitive: 'Competitive', regulatory: 'Regulatory',
  knowledge: 'Banking concepts', schema: 'Schema',
};

const BRIEF_TITLES: Record<string, string> = {
  macro: 'Macro brief', competitive: 'Competitive brief', regulatory: 'Regulatory brief',
  knowledge: 'Concept explained',
};

export default function WorkbenchTurn({ turn, onAsk }: { turn: WorkbenchTurnData; onAsk: (q: string) => void }) {
  return (
    <section className="space-y-5">
      <div className="flex justify-end">
        <div className="max-w-[88%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm leading-6 text-primary-foreground sm:max-w-[78%]">
          {turn.question}
        </div>
      </div>

      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-xl bg-accent text-primary">
          <Sparkles className="size-4" />
        </div>
        <div className="min-w-0 flex-1 space-y-3">
          {!turn.done && turn.stage && !turn.route && (
            <div className="flex items-center gap-2 py-1 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              <span className="capitalize">{turn.stage}…</span>
            </div>
          )}

          {turn.synthesis && (
            <p className="whitespace-pre-wrap text-sm leading-7 text-foreground">{turn.synthesis}</p>
          )}

          {turn.cards.map((card, index) => (
            <CardBody key={`${card.source}-${index}`} card={card} onAsk={onAsk} />
          ))}

          {turn.pending
            .filter((source) => !turn.cards.some((card) => card.source === source))
            .map((source) => (
              <div key={source} className="flex items-center gap-2 py-1 text-xs text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" />
                Checking {SOURCE_LABELS[source] ?? source}…
              </div>
            ))}

          {turn.refusal && (
            <div className="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/5 px-3 py-2.5 text-sm">
              <Ban className="mt-0.5 size-4 shrink-0 text-amber-600" />
              <span>{turn.refusal.message || 'That request cannot be handled here.'}</span>
            </div>
          )}

          {turn.error && (
            <div className="flex items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-sm">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
              <span>{turn.error}</span>
            </div>
          )}

          {turn.legacyAnswerUnavailable && !turn.error && turn.cards.length === 0 && (
            <div className="flex items-start gap-2 rounded-xl border border-border bg-muted/40 px-3 py-2.5 text-sm text-muted-foreground">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" />
              <span>
                This question was saved before answer history was enabled. Its original answer card was not retained.
              </span>
            </div>
          )}

          {turn.partial && !turn.error && (
            <div className="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/5 px-3 py-2.5 text-sm text-muted-foreground">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600" />
              <span>This response was interrupted. Completed answer cards were retained.</span>
            </div>
          )}

          {turn.done && turn.route && turn.route.sources.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
              <span className="text-[11px] text-muted-foreground">Sources</span>
              {turn.route.sources.map((source) => (
                <Badge key={source} variant="outline" className="h-5 rounded-md px-1.5 text-[10px] font-medium text-muted-foreground">
                  {SOURCE_LABELS[source] ?? source}
                </Badge>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function CardBody({ card, onAsk }: { card: CardData; onAsk: (q: string) => void }) {
  if (card.card_type === 'chart') {
    const chart = card.payload as ChartSpec;
    return (
      <WorkbenchCard source={card.source} title={chart.title || 'Result'} subtitle={chart.subtitle ?? undefined}>
        <ChartRenderer chart={chart} hideHeader />
        <LineagePanel chart={chart} sourceLabel="Loan book" />
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
          <ul className="mt-2 list-disc space-y-0.5 pl-4 text-xs text-muted-foreground">
            {key_points.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        )}
        {sources && sources.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {sources.map((s, i) => (
              <Badge key={i} variant="outline" className="text-[10px]">
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
            <Badge key={n.id} variant="secondary" className="font-mono text-[10px]">{n.label}</Badge>
          ))}
        </div>
        {edges && edges.length > 0 && (
          <ul className="mt-2 space-y-0.5 text-xs text-muted-foreground">
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
        <div className="flex items-start gap-2 text-sm">
          <HelpCircle className="mt-0.5 size-4 shrink-0 text-sky-500" />
          <span>{question}</span>
        </div>
        {suggestions && suggestions.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {suggestions.map((s) => (
              <Button key={s} size="sm" variant="outline" className="h-7 text-xs" onClick={() => onAsk(s)}>
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
        <div className="flex items-start gap-2 text-sm">
          <Ban className="mt-0.5 size-4 shrink-0 text-amber-500" />
          <span>{message}</span>
        </div>
        {examples && examples.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {examples.map((s) => (
              <Button key={s} size="sm" variant="outline" className="h-7 text-xs" onClick={() => onAsk(s)}>
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
      <div className="flex items-start gap-2 text-sm">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
        <span>{(card.payload as { message?: string }).message || 'Something went wrong.'}</span>
      </div>
    </WorkbenchCard>
  );
}
