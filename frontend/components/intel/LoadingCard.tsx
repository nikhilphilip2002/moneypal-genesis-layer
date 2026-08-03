'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

// Default phase labels for AI-generated intelligence briefs. Indicative of the
// backend pipeline (retrieve → summarise → generate) rather than tied to real
// progress events — enough to tell the user work is happening, not a spinner.
export const BRIEF_STAGES = ['Fetching sources', 'Summarizing evidence', 'Generating brief'];

// Advances through `stages` on a timer and holds on the final stage until the
// real data arrives and this card unmounts.
function StatusLine({ stages, intervalMs = 1600 }: { stages: string[]; intervalMs?: number }) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    setIndex(0);
    const id = setInterval(() => {
      setIndex((i) => (i < stages.length - 1 ? i + 1 : i));
    }, intervalMs);
    return () => clearInterval(id);
  }, [stages, intervalMs]);

  return (
    <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground" aria-live="polite">
      <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" />
      <span className="truncate">{stages[index]}…</span>
      <span className="flex items-center gap-1">
        {stages.map((_, i) => (
          <span
            key={i}
            className={cn(
              'h-1 w-1 rounded-full transition-colors',
              i <= index ? 'bg-primary' : 'bg-muted-foreground/25',
            )}
          />
        ))}
      </span>
    </div>
  );
}

// Skeleton placeholder matching IntelligenceCard's shape — prevents layout shift.
// Pass `showStatus` (or a custom `stages` list) to surface what the backend is
// doing while an AI brief is generated, instead of a silent skeleton.
export default function LoadingCard({
  className,
  lines = 4,
  showStatus = false,
  stages,
}: {
  className?: string;
  lines?: number;
  showStatus?: boolean;
  stages?: string[];
}) {
  const phases = stages ?? (showStatus ? BRIEF_STAGES : null);

  return (
    <Card className={cn('dashboard-surface rounded-[1.5rem] border-border/70 shadow-none', className)}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-5 w-24 rounded-full" />
        </div>
      </CardHeader>
      <CardContent className="space-y-2.5">
        {phases && (
          <div className="pb-1">
            <StatusLine stages={phases} />
          </div>
        )}
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton key={i} className={cn('h-3.5', i === lines - 1 ? 'w-1/2' : 'w-full')} />
        ))}
        <div className="flex items-center gap-2 pt-2">
          <Skeleton className="h-5 w-40 rounded-full" />
        </div>
      </CardContent>
    </Card>
  );
}
