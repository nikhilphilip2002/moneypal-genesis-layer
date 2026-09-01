'use client';

import { ArrowDown, ArrowLeftRight, HelpCircle, ListChecks, Sparkles } from 'lucide-react';
import type { DrillStep } from '@/lib/api';
import { cn } from '@/lib/utils';

// The chips under every answer. Each one carries a prebuilt QuerySpec, so tapping it runs
// through /nlq/execute with no model in the loop — as instant and as trustworthy as
// re-running the original question, which is what makes a chain of eight questions
// practical rather than a chain of eight round trips through a planner.
//
// The icon encodes the kind of move, because "one level deeper" and "a different axis
// entirely" feel the same in text and very different in a conversation.

const ICONS = {
  deeper: ArrowDown,
  sideways: ArrowLeftRight,
  explain: HelpCircle,
  act: ListChecks,
} as const;

export default function NextQuestions({
  steps,
  onPick,
}: {
  steps: DrillStep[];
  onPick: (step: DrillStep) => void;
}) {
  if (!steps.length) return null;

  return (
    <div className="mt-3 rounded-xl border border-border/60 bg-muted/25 px-3.5 py-3">
      <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <Sparkles className="size-3.5 text-primary" aria-hidden />
        Suggested next
        <span className="font-normal text-muted-foreground/70">· based on this result</span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {steps.map((step) => {
          const Icon = ICONS[step.kind];
          return (
            <button
              key={step.id}
              type="button"
              onClick={() => onPick(step)}
              title={step.question}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-muted/60',
                'px-3 py-1 text-xs text-foreground/80 transition-colors',
                'hover:bg-muted hover:text-foreground',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                // "Why" and "show the accounts" are the two moves that end a chain in
                // something useful, so they read as the primary offers.
                (step.kind === 'explain' || step.kind === 'act') && 'text-primary',
              )}
            >
              <Icon className="h-3 w-3" aria-hidden />
              {step.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
