'use client';

import { useEffect, useRef, useState } from 'react';
import { nlq, type NlqCatalog, type NlqHealth } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loader2, Search, X } from 'lucide-react';
import { cn } from '@/lib/utils';

// The ask input. Two states matter beyond the obvious one:
//
//  - When the assistant is offline the bar disables itself with a clear message, and says
//    what still works. Saved questions and dashboards run through /nlq/execute, which has
//    no LLM dependency at all.
//  - Empty state shows example questions rather than a blank box. Users of a query product
//    do not know what it can answer until they see the shape of a good question.

type Props = {
  onAsk: (question: string) => void;
  busy?: boolean;
  onCancel?: () => void;
  compact?: boolean;
};

export default function AskBar({ onAsk, busy, onCancel, compact }: Props) {
  const [value, setValue] = useState('');
  const [catalog, setCatalog] = useState<NlqCatalog | null>(null);
  const [health, setHealth] = useState<NlqHealth | null>(null);
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    nlq.catalog().then(setCatalog).catch(() => setCatalog(null));
    nlq.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  const offline = health !== null && !health.capabilities.ask;
  const suggestions = matchSuggestions(value, catalog);

  const submit = (question: string) => {
    const trimmed = question.trim();
    if (!trimmed || busy || offline) return;
    setValue('');
    setFocused(false);
    onAsk(trimmed);
  };

  return (
    <div className="w-full">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(value);
        }}
        className="relative"
      >
        <Search className="pointer-events-none absolute left-3 top-1/2 z-10 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          ref={inputRef}
          value={value}
          disabled={offline}
          onChange={(e) => setValue(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setTimeout(() => setFocused(false), 120)}
          placeholder={
            offline
              ? 'Assistant offline — dashboards and saved questions still work'
              : 'Ask about the loan book — “disbursement by branch last quarter”'
          }
          className={cn('pl-9 pr-24', compact ? 'h-10' : 'h-12', offline && 'opacity-70')}
        />

        <div className="absolute right-2 top-1/2 z-10 -translate-y-1/2">
          {busy ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onCancel}
              className="h-7 gap-1 px-2 text-xs text-muted-foreground hover:text-foreground"
            >
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Stop
            </Button>
          ) : (
            value && (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label="Clear"
                onClick={() => setValue('')}
                className="h-7 w-7 text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </Button>
            )
          )}
        </div>

        {focused && !offline && suggestions.length > 0 && (
          <ul
            className={cn(
              'absolute z-20 mt-1 w-full overflow-hidden rounded-xl border border-border shadow-lg',
              'bg-popover/85 backdrop-blur-[20px] [backdrop-filter:saturate(180%)_blur(20px)]',
              '[-webkit-backdrop-filter:saturate(180%)_blur(20px)]',
            )}
          >
            {suggestions.map((suggestion) => (
              <li key={suggestion}>
                <button
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => submit(suggestion)}
                  className="w-full px-3 py-2 text-left text-sm transition-colors hover:bg-accent hover:text-accent-foreground"
                >
                  {suggestion}
                </button>
              </li>
            ))}
          </ul>
        )}
      </form>

      {offline && health && (
        <p className="mt-2 text-xs text-muted-foreground">
          Assistant offline{health.llm.detail ? ` (${health.llm.detail})` : ''}. Saved questions
          and dashboards are fully available.
        </p>
      )}

      {!value && !busy && !offline && catalog && (
        <div className="mt-3 flex flex-wrap gap-2">
          {catalog.example_questions.slice(0, 4).map((question) => (
            <Button
              key={question}
              type="button"
              variant="outline"
              size="sm"
              onClick={() => submit(question)}
              className="h-7 rounded-full text-xs font-normal text-muted-foreground hover:text-foreground"
            >
              {question}
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}

// Autocomplete over the catalog's own labels and synonyms, so the suggestions are things
// the system can definitely answer rather than plausible-sounding guesses.
function matchSuggestions(value: string, catalog: NlqCatalog | null): string[] {
  const query = value.trim().toLowerCase();
  if (!catalog || query.length < 2) return [];

  const fromExamples = catalog.example_questions.filter((q) =>
    q.toLowerCase().includes(query),
  );
  const fromMetrics = catalog.metrics
    .filter(
      (m) =>
        m.label.toLowerCase().includes(query) ||
        m.synonyms.some((s) => s.toLowerCase().includes(query)),
    )
    .map((m) => `${m.label} by branch`);

  return [...new Set([...fromExamples, ...fromMetrics])].slice(0, 6);
}
