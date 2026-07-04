'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import BriefRenderer from '@/components/intel/BriefRenderer';
import SourceBadge from '@/components/intel/SourceBadge';
import type { IntelligenceResponse, Confidence } from '@/lib/api';
import { cn } from '@/lib/utils';
import { ChevronDown, RotateCw } from 'lucide-react';

// Strip citations/labels/markdown for the collapsed one-glance preview.
export function briefPreview(summary: string): string {
  return summary
    .replace(/\((?:Source:\s*)?[^()\n]{2,90}?,\s*(?:p\.|page\s+)[\w?]+\)/g, '')
    .replace(/\[(?:FACT|AI INTERPRETATION)\]/g, '')
    .replace(/\*\*/g, '')
    .replace(/^#{1,4}\s+/gm, '')
    .replace(/\s+/g, ' ')
    .trim();
}

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

export function RefreshButton({ onRefresh }: { onRefresh: () => void }) {
  return (
    <button
      type="button"
      onClick={onRefresh}
      aria-label="Refresh"
      title="Refresh"
      className="rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
    >
      <RotateCw className="h-3.5 w-3.5" />
    </button>
  );
}

// The core display unit for every AI-generated intelligence item.
// `collapsible` renders a scannable preview with an in-place "Read more" —
// used on the dashboard so leadership scans headlines and expands what matters.
export default function IntelligenceCard({
  data,
  className,
  onRefresh,
  collapsible = false,
  defaultOpen = false,
}: {
  data: IntelligenceResponse;
  className?: string;
  onRefresh?: () => void;
  collapsible?: boolean;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(!collapsible || defaultOpen);

  return (
    <Card className={cn('dashboard-surface rounded-[1.5rem] border-border/70 shadow-none', className)}>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <CardTitle className="font-headline text-base font-semibold leading-snug">{data.title}</CardTitle>
          <div className="flex items-center gap-1.5">
            <ConfidenceBadge confidence={data.confidence} />
            {onRefresh && open && <RefreshButton onRefresh={onRefresh} />}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {!open ? (
          <>
            <p className="line-clamp-3 text-sm leading-relaxed text-foreground/85">
              {briefPreview(data.summary)}
            </p>
            <button
              type="button"
              onClick={() => setOpen(true)}
              className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
            >
              Read full brief <ChevronDown className="h-3.5 w-3.5" />
            </button>
          </>
        ) : (
          <>
            <BriefRenderer content={data.summary} />

            {data.key_points?.length > 0 && (
              <div className="flex flex-wrap gap-1.5 border-t border-border/50 pt-3">
                {data.key_points.map((point, i) => (
                  <span
                    key={i}
                    className="rounded-full border border-border/60 bg-muted/50 px-2.5 py-1 text-[11px] font-medium text-foreground/80"
                  >
                    {point}
                  </span>
                ))}
              </div>
            )}

            <div className="flex flex-wrap items-center gap-2 pt-1">
              <SourceBadge source={data.source} />
              <span className="text-[11px] text-muted-foreground">Updated {data.last_updated}</span>
            </div>

            <div className="flex items-start justify-between gap-3 border-t border-border/50 pt-3">
              <p className="text-xs italic text-muted-foreground">{data.ai_note}</p>
              {collapsible && (
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="inline-flex shrink-0 items-center gap-1 text-xs font-semibold text-muted-foreground hover:text-foreground"
                >
                  Collapse <ChevronDown className="h-3.5 w-3.5 rotate-180" />
                </button>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
