'use client';

import { useState } from 'react';
import { intelligence, type SearchResult } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import BriefRenderer from '@/components/intel/BriefRenderer';
import { Search, X, FileText, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';

type Mode = 'ask' | 'search';

// Query the entire Genesis knowledge base. Two modes:
//   Ask    — natural-language question -> grounded, cited AI answer + sources
//   Search — raw source-cited document excerpts (explainable retrieval)
export default function GenesisSearch() {
  const [mode, setMode] = useState<Mode>('ask');
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState<string | null>(null);
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const run = async (e: React.SyntheticEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError('');
    setAnswer(null);
    setResults(null);
    try {
      if (mode === 'ask') {
        const res = await intelligence.ask(query.trim());
        setAnswer(res.answer);
        setResults(res.results);
      } else {
        const res = await intelligence.search(query.trim());
        setResults(res.results);
      }
    } catch (err: any) {
      setError(err.message || 'Genesis intelligence is unavailable.');
    } finally {
      setLoading(false);
    }
  };

  const clear = () => {
    setAnswer(null);
    setResults(null);
    setError('');
    setQuery('');
  };

  return (
    <div className="space-y-3">
      <form onSubmit={run} className="flex gap-2">
        <div className="flex shrink-0 rounded-lg border border-border/70 bg-muted/40 p-0.5">
          {(['ask', 'search'] as Mode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold capitalize transition-colors',
                mode === m ? 'bg-background text-foreground shadow-none border border-border/50' : 'text-muted-foreground hover:text-foreground border border-transparent',
              )}
            >
              {m === 'ask' ? <Sparkles className="h-3 w-3" /> : <Search className="h-3 w-3" />}
              {m}
            </button>
          ))}
        </div>
        <div className="relative flex-1">
          <Input
            placeholder={
              mode === 'ask'
                ? 'Ask Genesis — “What are the digital lending disclosure requirements for GICC?”'
                : 'Search Genesis intelligence — regulations, competitors, macro data…'
            }
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="shadow-none hover:shadow-none border border-border bg-background focus-visible:bg-background/80"
          />
          {(results !== null || answer !== null || error) && (
            <button
              type="button"
              onClick={clear}
              aria-label="Clear"
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        <Button type="submit" disabled={loading || !query.trim()} className="shadow-none hover:shadow-none border border-primary/20">
          {loading ? (mode === 'ask' ? 'Thinking…' : 'Searching…') : mode === 'ask' ? 'Ask' : 'Search'}
        </Button>
      </form>

      {error && (
        <p className="rounded-xl border border-amber-300/60 bg-amber-50/60 px-3 py-2 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300">
          {error}
        </p>
      )}

      {answer !== null && (
        <Card className="dashboard-surface rounded-[1.5rem] border-primary/25 shadow-none">
          <CardContent className="space-y-3 p-4 md:p-5">
            <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              Genesis answer
            </p>
            <BriefRenderer content={answer} />
          </CardContent>
        </Card>
      )}

      {results !== null && (
        <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none">
          <CardContent className="space-y-3 p-4 md:p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {results.length} source excerpt{results.length === 1 ? '' : 's'} for “{query}”
            </p>
            {results.map((result, i) => (
              <div key={i} className="rounded-2xl border border-border/60 bg-card/70 p-3.5">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className="rounded-full px-2 py-0 text-[10px]">
                    {result.module}
                  </Badge>
                  <span className="text-xs font-medium">{result.collection_label}</span>
                  <span className="ml-auto text-[10px] text-muted-foreground">
                    relevance {(result.score * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-foreground/85">{result.text}…</p>
                <p className="mt-2 inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                  <FileText className="h-3 w-3" />
                  {result.source}
                  {result.page ? ` · p.${result.page}` : ''}
                </p>
              </div>
            ))}
            {results.length === 0 && (
              <p className="py-4 text-center text-sm text-muted-foreground">No matching intelligence found.</p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
