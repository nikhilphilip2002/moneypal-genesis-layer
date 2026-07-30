'use client';

import { useEffect, useState } from 'react';
import { nlq } from '@/lib/api';
import { X } from 'lucide-react';

// Carried-over conversation state, always visible and always dismissible.
//
// Invisible sticky state is the single largest source of confusion in conversational
// analytics: the user asks about gold loans, then asks a general question, and quietly gets
// a gold-only answer with no indication why. Showing the filters costs a strip of chips;
// hiding them costs trust in every number below.

type Chip = { field: string; label: string; value: string; display: string };

export default function StickyFilters({ conversationId }: { conversationId: string }) {
  const [chips, setChips] = useState<Chip[]>([]);

  useEffect(() => {
    let cancelled = false;
    nlq
      .conversation(conversationId)
      .then((state: any) => {
        if (!cancelled) setChips(state.sticky_filters ?? []);
      })
      .catch(() => setChips([]));
    return () => {
      cancelled = true;
    };
  }, [conversationId]);

  if (chips.length === 0) return null;

  const clearAll = async () => {
    await nlq.clearConversation(conversationId).catch(() => undefined);
    setChips([]);
  };

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border/60 bg-muted/30 px-3 py-2">
      <span className="text-xs text-muted-foreground">Applied to follow-ups:</span>
      {chips.map((chip) => (
        <span
          key={chip.field}
          className="inline-flex items-center gap-1 rounded-full border border-border bg-background px-2 py-0.5 text-xs"
        >
          <span className="text-muted-foreground">{chip.label}:</span>
          <span className="font-medium text-foreground">{chip.display}</span>
        </span>
      ))}
      <button
        type="button"
        onClick={clearAll}
        className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
      >
        <X className="h-3 w-3" />
        Clear context
      </button>
    </div>
  );
}
