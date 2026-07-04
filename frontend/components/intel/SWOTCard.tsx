'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import SourceBadge from '@/components/intel/SourceBadge';
import type { SwotResponse } from '@/lib/api';
import { cn } from '@/lib/utils';

type Quadrants = {
  strengths: string[];
  weaknesses: string[];
  opportunities: string[];
  threats: string[];
  observation: string;
};

// The SWOT endpoint returns one labelled text block; split it into quadrants.
function parseSwot(text: string): Quadrants {
  const q: Quadrants = { strengths: [], weaknesses: [], opportunities: [], threats: [], observation: '' };
  const keyFor = (heading: string): keyof Quadrants | null => {
    const h = heading.toUpperCase();
    if (h.startsWith('STRENGTH')) return 'strengths';
    if (h.startsWith('WEAKNESS')) return 'weaknesses';
    if (h.startsWith('OPPORTUNIT')) return 'opportunities';
    if (h.startsWith('THREAT')) return 'threats';
    if (h.startsWith('STRATEGIC')) return 'observation';
    return null;
  };
  let current: keyof Quadrants | null = null;
  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim();
    if (!line) continue;
    const headingMatch = line.match(/^\**\s*(STRENGTHS?|WEAKNESSES?|OPPORTUNITIES?|THREATS?|STRATEGIC OBSERVATION)\s*\**:?\s*(.*)$/i);
    if (headingMatch) {
      current = keyFor(headingMatch[1]);
      const rest = headingMatch[2]?.trim();
      if (rest && current === 'observation') q.observation += rest;
      continue;
    }
    if (!current) continue;
    if (current === 'observation') {
      q.observation += (q.observation ? ' ' : '') + line;
    } else {
      const point = line.replace(/^[-*•]\s*/, '').trim();
      if (point) q[current].push(point);
    }
  }
  return q;
}

// Highlight the [FACT] / [AI INTERPRETATION] labels inside a SWOT point.
function SwotPoint({ text }: { text: string }) {
  const match = text.match(/^\[(FACT|AI INTERPRETATION)\]\s*(.*)$/i);
  if (!match) return <span>{text}</span>;
  const isFact = match[1].toUpperCase() === 'FACT';
  return (
    <span>
      <span
        className={cn(
          'mr-1.5 inline-block rounded px-1 py-px align-middle text-[9px] font-bold uppercase tracking-wide',
          isFact
            ? 'bg-foreground/10 text-foreground'
            : 'bg-primary/10 text-primary'
        )}
      >
        {isFact ? 'Fact' : 'AI Interpretation'}
      </span>
      {match[2]}
    </span>
  );
}

const QUADRANTS: Array<{ key: keyof Omit<Quadrants, 'observation'>; label: string; className: string }> = [
  { key: 'strengths', label: 'Strengths', className: 'border-emerald-300/60 bg-emerald-50/60 dark:border-emerald-900 dark:bg-emerald-950/40' },
  { key: 'weaknesses', label: 'Weaknesses', className: 'border-red-300/60 bg-red-50/60 dark:border-red-900 dark:bg-red-950/40' },
  { key: 'opportunities', label: 'Opportunities', className: 'border-blue-300/60 bg-blue-50/60 dark:border-blue-900 dark:bg-blue-950/40' },
  { key: 'threats', label: 'Threats', className: 'border-orange-300/60 bg-orange-50/60 dark:border-orange-900 dark:bg-orange-950/40' },
];

// Four-quadrant SWOT display with [FACT] vs [AI INTERPRETATION] labelling.
export default function SWOTCard({ data, className }: { data: SwotResponse; className?: string }) {
  const swot = parseSwot(data.swot_analysis);
  const parsed = QUADRANTS.some((quad) => swot[quad.key].length > 0);

  return (
    <Card className={cn('dashboard-surface rounded-[1.5rem] border-border/70 shadow-none', className)}>
      <CardHeader className="pb-3">
        <CardTitle className="font-headline text-base font-semibold">SWOT Analysis — {data.institution}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {parsed ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {QUADRANTS.map((quad) => (
              <div key={quad.key} className={cn('rounded-2xl border p-3.5', quad.className)}>
                <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-foreground/80">{quad.label}</p>
                <ul className="space-y-1.5">
                  {swot[quad.key].map((point, i) => (
                    <li key={i} className="text-xs leading-relaxed text-foreground/90">
                      <SwotPoint text={point} />
                    </li>
                  ))}
                  {swot[quad.key].length === 0 && (
                    <li className="text-xs italic text-muted-foreground">No points identified.</li>
                  )}
                </ul>
              </div>
            ))}
          </div>
        ) : (
          <p className="whitespace-pre-line text-sm text-foreground/90">{data.swot_analysis}</p>
        )}

        {swot.observation && (
          <div className="rounded-2xl border border-border/70 bg-muted/50 p-3.5">
            <p className="mb-1 text-[11px] font-bold uppercase tracking-wider text-foreground/80">Strategic Observation</p>
            <p className="text-xs leading-relaxed text-foreground/90">{swot.observation}</p>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <SourceBadge source={data.source} />
        </div>

        {data.ai_note && (
          <p className="border-t border-border/50 pt-3 text-xs italic text-muted-foreground">{data.ai_note}</p>
        )}
      </CardContent>
    </Card>
  );
}
