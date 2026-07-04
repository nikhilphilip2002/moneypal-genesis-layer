'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import BriefRenderer from '@/components/intel/BriefRenderer';
import SourceBadge from '@/components/intel/SourceBadge';
import { ConfidenceBadge, RefreshButton } from '@/components/intel/IntelligenceCard';
import type { IntelligenceResponse } from '@/lib/api';
import { Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';

// Full-width executive briefing panel — the dashboard's hero element.
export default function AIBriefPanel({
  data,
  className,
  onRefresh,
}: {
  data: IntelligenceResponse;
  className?: string;
  onRefresh?: () => void;
}) {
  return (
    <Card className={cn('dashboard-surface rounded-[1.75rem] border-border/70 shadow-none', className)}>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="rounded-full border-primary/30 bg-primary/5 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-primary">
            <Sparkles className="mr-1.5 h-3 w-3" />
            AI Executive Brief
          </Badge>
          <ConfidenceBadge confidence={data.confidence} />
          {onRefresh && (
            <span className="ml-auto">
              <RefreshButton onRefresh={onRefresh} />
            </span>
          )}
        </div>
        <CardTitle className="font-headline pt-2 text-xl font-semibold leading-snug md:text-2xl">
          {data.title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <BriefRenderer content={data.summary} className="text-[15px]" />

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

        {data.ai_note && (
          <p className="border-t border-border/50 pt-3 text-xs italic text-muted-foreground">{data.ai_note}</p>
        )}
      </CardContent>
    </Card>
  );
}
