'use client';

import { useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Props {
  query: string;
  intent?: string;
  note?: string;
  variant: 'good' | 'bad';
  reason?: string;
}

const INTENT_COLORS: Record<string, string> = {
  resources:       'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  requirements:    'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300',
  interviews:      'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
  email:           'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300',
  'company overview': 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
  'list clients':  'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300',
  'cross-company': 'bg-pink-100 text-pink-700 dark:bg-pink-900/40 dark:text-pink-300',
};

export function QueryExampleChip({ query, intent, note, variant, reason }: Props) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(query).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  };

  const intentColor = intent ? (INTENT_COLORS[intent] ?? 'bg-muted text-muted-foreground') : '';

  return (
    <div
      className={cn(
        'group rounded-lg border p-3 text-sm transition-colors',
        variant === 'good'
          ? 'border-border bg-card hover:border-primary/40 hover:bg-primary/5'
          : 'border-destructive/20 bg-destructive/5'
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className={cn('font-medium leading-snug', variant === 'bad' && 'text-muted-foreground line-through')}>
          "{query}"
        </p>

        {variant === 'good' && (
          <button
            onClick={handleCopy}
            title="Copy query"
            className="shrink-0 rounded p-1 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 hover:text-foreground"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
          </button>
        )}
      </div>

      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
        {variant === 'good' && intent && (
          <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', intentColor)}>
            {intent}
          </span>
        )}
        {variant === 'good' && note && (
          <span className="text-xs text-muted-foreground">{note}</span>
        )}
        {variant === 'bad' && reason && (
          <span className="text-xs text-destructive/80">{reason}</span>
        )}
      </div>
    </div>
  );
}
