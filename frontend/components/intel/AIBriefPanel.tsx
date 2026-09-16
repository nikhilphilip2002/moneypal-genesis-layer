'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import IntelligenceBriefBody from '@/components/intel/IntelligenceBriefBody';
import { ConfidenceBadge, RefreshButton } from '@/components/intel/IntelligenceCard';
import type { IntelligenceResponse } from '@/lib/api';
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
        <IntelligenceBriefBody data={data} rendererClassName="text-[15px]" />
      </CardContent>
    </Card>
  );
}
