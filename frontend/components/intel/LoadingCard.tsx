'use client';

import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

// Skeleton placeholder matching IntelligenceCard's shape — prevents layout shift.
export default function LoadingCard({ className, lines = 4 }: { className?: string; lines?: number }) {
  return (
    <Card className={cn('dashboard-surface rounded-[1.5rem] border-border/70 shadow-none', className)}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-5 w-24 rounded-full" />
        </div>
      </CardHeader>
      <CardContent className="space-y-2.5">
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
