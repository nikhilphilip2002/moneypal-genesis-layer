'use client';

import { CheckCircle2, XCircle, ArrowRight } from 'lucide-react';
import { INTEL_GOOD_EXAMPLES, INTEL_OUT_OF_SCOPE, INTENT_TABLE } from '@/lib/guide-content';
import { QueryExampleChip } from './QueryExampleChip';

export function IntelQueryGuide() {
  return (
    <div className="space-y-6 pb-6">
      {/* Intro */}
      <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 text-sm leading-relaxed text-foreground">
        <p>
          Company Intel understands <strong>natural-language questions</strong> about Aroha's client
          portfolio. It classifies your query into an intent, extracts the company name, and fetches
          the right data — no special syntax needed.
        </p>
      </div>

      {/* Pattern table */}
      <div>
        <h3 className="mb-2 text-sm font-semibold text-foreground">How to phrase queries</h3>
        <div className="overflow-hidden rounded-lg border border-border text-xs">
          <div className="grid grid-cols-2 gap-0 divide-x divide-border bg-muted/50">
            <div className="px-3 py-2 font-semibold text-muted-foreground">Pattern</div>
            <div className="px-3 py-2 font-semibold text-muted-foreground">Example</div>
          </div>
          {INTENT_TABLE.map((row, i) => (
            <div
              key={i}
              className="grid grid-cols-2 gap-0 divide-x divide-border border-t border-border"
            >
              <div className="flex items-center gap-1.5 px-3 py-2 text-muted-foreground">
                <ArrowRight className="h-3 w-3 shrink-0 text-primary" />
                {row.pattern}
              </div>
              <div className="px-3 py-2 font-medium text-foreground">{row.example}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Good examples */}
      <div>
        <div className="mb-2 flex items-center gap-1.5">
          <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          <h3 className="text-sm font-semibold text-foreground">Questions it answers well</h3>
        </div>
        <p className="mb-3 text-xs text-muted-foreground">
          Click the copy icon on any example to copy it, then paste it into the Intel chat.
        </p>
        <div className="space-y-2">
          {INTEL_GOOD_EXAMPLES.map((ex, i) => (
            <QueryExampleChip
              key={i}
              query={ex.query}
              intent={ex.intent}
              note={ex.note}
              variant="good"
            />
          ))}
        </div>
      </div>

      {/* Out of scope */}
      <div>
        <div className="mb-2 flex items-center gap-1.5">
          <XCircle className="h-4 w-4 text-destructive" />
          <h3 className="text-sm font-semibold text-foreground">Out-of-scope questions</h3>
        </div>
        <p className="mb-3 text-xs text-muted-foreground">
          These will return a "couldn't understand" response — try General Intel for open-ended tasks.
        </p>
        <div className="space-y-2">
          {INTEL_OUT_OF_SCOPE.map((ex, i) => (
            <QueryExampleChip
              key={i}
              query={ex.query}
              variant="bad"
              reason={ex.reason}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
