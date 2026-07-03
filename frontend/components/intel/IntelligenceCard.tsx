'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { MarkdownRenderer } from '@/components/ui/markdown-renderer';
import SourceBadge from '@/components/intel/SourceBadge';
import type { IntelligenceResponse, Confidence } from '@/lib/api';
import { cn } from '@/lib/utils';

export function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  const styles: Record<Confidence, string> = {
    high: 'border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-400',
    medium: 'border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-400',
    low: 'border-red-300 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950/50 dark:text-red-400',
  };
  return (
    <Badge variant="outline" className={cn('rounded-full px-2.5 py-0.5 text-[11px] capitalize', styles[confidence])}>
      {confidence} confidence
    </Badge>
  );
}

// The core display unit for every AI-generated intelligence item.
export default function IntelligenceCard({
  data,
  className,
}: {
  data: IntelligenceResponse;
  className?: string;
}) {
  return (
    <Card className={cn('dashboard-surface rounded-[1.5rem] border-border/70 shadow-none', className)}>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <CardTitle className="font-headline text-base font-semibold leading-snug">{data.title}</CardTitle>
          <ConfidenceBadge confidence={data.confidence} />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <MarkdownRenderer content={data.summary} variant="light" />

        {data.key_points?.length > 0 && (
          <ul className="space-y-1.5">
            {data.key_points.map((point, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-foreground/90">
                <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                <span>{point}</span>
              </li>
            ))}
          </ul>
        )}

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <SourceBadge source={data.source} />
          <span className="text-[11px] text-muted-foreground">Updated {data.last_updated}</span>
        </div>

        <p className="border-t border-border/50 pt-3 text-xs italic text-muted-foreground">
          {data.ai_note}
        </p>
      </CardContent>
    </Card>
  );
}
