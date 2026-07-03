'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { MarkdownRenderer } from '@/components/ui/markdown-renderer';
import SourceBadge from '@/components/intel/SourceBadge';
import { ConfidenceBadge } from '@/components/intel/IntelligenceCard';
import type { IntelligenceResponse } from '@/lib/api';
import { Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';

// Full-width executive briefing panel — the dashboard's hero element.
export default function AIBriefPanel({ data, className }: { data: IntelligenceResponse; className?: string }) {
  return (
    <Card className={cn('dashboard-surface rounded-[1.75rem] border-border/70 shadow-none', className)}>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="rounded-full border-primary/30 bg-primary/5 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-primary">
            <Sparkles className="mr-1.5 h-3 w-3" />
            AI Executive Brief
          </Badge>
          <ConfidenceBadge confidence={data.confidence} />
        </div>
        <CardTitle className="font-headline pt-2 text-xl font-semibold leading-snug md:text-2xl">
          {data.title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="text-[15px] leading-7">
          <MarkdownRenderer content={data.summary} variant="light" />
        </div>

        {data.key_points?.length > 0 && (
          <ul className="grid gap-2 md:grid-cols-2">
            {data.key_points.map((point, i) => (
              <li key={i} className="flex items-start gap-2 rounded-xl border border-border/60 bg-card/60 px-3 py-2 text-sm">
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

        <p className="border-t border-border/50 pt-3 text-xs italic text-muted-foreground">{data.ai_note}</p>
      </CardContent>
    </Card>
  );
}
