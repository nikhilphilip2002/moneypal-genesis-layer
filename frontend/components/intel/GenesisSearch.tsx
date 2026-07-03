'use client';

import { useState } from 'react';
import { intelligence, type SearchResult } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Search, X, FileText } from 'lucide-react';

// Explainable semantic search across every Genesis collection — results are
// source-cited document excerpts, deliberately not a chatbot (brief §6).
export default function GenesisSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const runSearch = async (e: React.SyntheticEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError('');
    try {
      const res = await intelligence.search(query.trim());
      setResults(res.results);
    } catch (err: any) {
      setError(err.message || 'Search is unavailable.');
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  const clear = () => {
    setResults(null);
    setError('');
    setQuery('');
  };

  return (
    <div className="space-y-3">
      <form onSubmit={runSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search Genesis intelligence — regulations, competitors, macro data…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-9"
          />
          {(results !== null || error) && (
            <button
              type="button"
              onClick={clear}
              aria-label="Clear search"
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        <Button type="submit" disabled={loading || !query.trim()}>
          {loading ? 'Searching…' : 'Search'}
        </Button>
      </form>

      {error && (
        <p className="rounded-xl border border-amber-300/60 bg-amber-50/60 px-3 py-2 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300">
          {error}
        </p>
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
