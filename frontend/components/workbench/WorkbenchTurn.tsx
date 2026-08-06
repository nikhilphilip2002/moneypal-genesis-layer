'use client';

import { Loader2, AlertTriangle, Ban, HelpCircle } from 'lucide-react';
import type { ChartSpec, WorkbenchCard as CardData } from '@/lib/api';
import ChartRenderer from '@/components/nlq/ChartRenderer';
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
  done: boolean;
};

const SOURCE_LABELS: Record<string, string> = {
  db: 'Loan book', macro: 'Macro', competitive: 'Competitive', regulatory: 'Regulatory', schema: 'Schema',
};

const BRIEF_TITLES: Record<string, string> = {
  macro: 'Macro brief', competitive: 'Competitive brief', regulatory: 'Regulatory brief',
};

export default function WorkbenchTurn({ turn, onAsk }: { turn: WorkbenchTurnData; onAsk: (q: string) => void }) {
  return (
    <div className="space-y-2.5">
      {/* The question, right-aligned like a chat bubble but compact. */}
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-lg bg-primary px-3 py-1.5 text-sm text-primary-foreground">
          {turn.question}
        </div>
      </div>

      {/* Route pills + stage. */}
      {(turn.route || turn.stage) && !turn.done && !turn.route && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" />
          <span className="capitalize">{turn.stage ?? 'working'}…</span>
        </div>
      )}
      {turn.route && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-muted-foreground">Routed to</span>
          {turn.route.sources.map((s) => (
            <Badge key={s} variant="outline" className="text-[10px]">
              {SOURCE_LABELS[s] ?? s}
            </Badge>
          ))}
        </div>
      )}

      {/* Merged lead for multi-source answers. */}
      {turn.synthesis && (
        <div className="rounded-lg border bg-muted/40 px-3 py-2 text-sm leading-relaxed">
          {turn.synthesis}
        </div>
      )}

      {/* One card per source. */}
      {turn.cards.map((card, i) => (
        <CardBody key={`${card.source}-${i}`} card={card} onAsk={onAsk} />
      ))}

      {/* Sources still in flight. */}
      {turn.pending
        .filter((s) => !turn.cards.some((c) => c.source === s))
        .map((s) => (
          <div key={s} className="flex items-center gap-2 rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground">
            <Loader2 className="size-3.5 animate-spin" />
            Querying {SOURCE_LABELS[s] ?? s}…
          </div>
        ))}

      {/* Top-level refusal from the router (no source applied). */}
      {turn.refusal && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-sm">
          <Ban className="mt-0.5 size-4 shrink-0 text-amber-500" />
          <span>{turn.refusal.message || 'That request cannot be handled here.'}</span>
        </div>
      )}

      {turn.error && (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
          <span>{turn.error}</span>
        </div>
      )}
    </div>
  );
}

function CardBody({ card, onAsk }: { card: CardData; onAsk: (q: string) => void }) {
  if (card.card_type === 'chart') {
    const chart = card.payload as ChartSpec;
    return (
      <WorkbenchCard source={card.source} title={chart.title || 'Result'} subtitle={chart.subtitle ?? undefined}>
        <ChartRenderer chart={chart} />
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
