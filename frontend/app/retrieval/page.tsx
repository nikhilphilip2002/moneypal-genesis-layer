'use client';

import { useState, useEffect } from 'react';
import { rag, auth } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { MarkdownRenderer } from '@/components/ui/markdown-renderer';
import { Skeleton } from '@/components/ui/skeleton';

interface Result {
  content: string;
  url: string;
  title: string;
  score: number;
  company_name: string;
}

export default function RetrievalPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Result[]>([]);
  const [mode, setMode] = useState<string>('vector');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [authorized, setAuthorized] = useState(false);
  const [authChecking, setAuthChecking] = useState(true);
  const router = useRouter();

  useEffect(() => {
    checkPermission();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const checkPermission = async () => {
    try {
      const user = await auth.me();
      const userRole = user.role || (user.is_staff ? 'admin' : 'standard');
      if (userRole === 'standard') {
        router.push('/');
      } else {
        setAuthorized(true);
      }
    } catch (e) {
      router.push('/login');
    } finally {
      setAuthChecking(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    try {
      setLoading(true);
      setError(null);
      const data = await rag.search(query, 10);
      setMode(data.mode || 'vector');

      const formatted = data.results.map((result: any) => ({
        content: result.content,
        ...result.metadata,
        score: result.score
      }));

      setResults(formatted);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  };

  if (authChecking) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col gap-1">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-64" />
        </div>
        <Card>
          <CardContent className="pt-6">
            <Skeleton className="h-10 w-full" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!authorized) return null;

  return (
    <div className="h-full overflow-auto container mx-auto px-4 py-8 max-w-7xl">
      <div className="space-y-6">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold text-foreground">Raw Retrieval</h1>
          <p className="text-muted-foreground">
            {mode === 'payload'
              ? 'Browsing Qdrant payloads without semantic embeddings'
              : 'Searching raw vectors in the knowledge base'}
          </p>
        </div>

        <Card>
          <CardContent className="pt-6">
            <form onSubmit={handleSearch} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="query">Search query</Label>
                <Input
                  id="query"
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="e.g., 'pricing models' or 'tech stack'"
                />
              </div>
              <Button type="submit" disabled={loading}>
                {loading ? 'Searching...' : 'Search'}
              </Button>
            </form>
          </CardContent>
        </Card>

        {error && (
          <Card className="border-destructive bg-destructive/10">
            <CardContent className="pt-6">
              <p className="text-destructive">{error}</p>
            </CardContent>
          </Card>
        )}

        {loading && (
          <div className="space-y-4">
            {Array.from({ length: 3 }).map((_, idx) => (
              <Card key={idx}>
                <CardContent className="p-6">
                  <Skeleton className="h-5 w-32 mb-4" />
                  <Skeleton className="h-4 w-48 mb-2" />
                  <Skeleton className="h-4 w-full" />
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        <div className="space-y-4">
          {results.map((result, index) => (
            <Card key={index}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">{result.company_name}</Badge>
                    <span className="text-sm text-muted-foreground">{result.title}</span>
                  </div>
                  <Badge>Score: {result.score.toFixed(4)}</Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="line-clamp-4 hover:line-clamp-none cursor-pointer transition-all">
                  <MarkdownRenderer content={result.content} variant="light" />
                </div>
                <a
                  href={result.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-muted-foreground hover:text-foreground underline mt-3 block"
                >
                  {result.url}
                </a>
              </CardContent>
            </Card>
          ))}
          {!loading && results.length === 0 && !error && (
            <Card>
              <CardContent className="py-12 text-center">
                <p className="text-muted-foreground">No results found. Try a different query.</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
