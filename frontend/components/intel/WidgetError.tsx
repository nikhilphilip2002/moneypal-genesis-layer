'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { AlertTriangle, RefreshCcw } from 'lucide-react';
import { cn } from '@/lib/utils';

// Graceful per-widget failure state — the page keeps working when one API is down.
export default function WidgetError({
  title,
  onRetry,
  className,
}: {
  title: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <Card className={cn('dashboard-surface rounded-[1.5rem] border-border/70 shadow-none', className)}>
      <CardContent className="flex flex-col items-center justify-center gap-2 py-8 text-center">
        <AlertTriangle className="h-5 w-5 text-amber-500" />
        <p className="text-sm font-medium">{title} is unavailable</p>
        <p className="text-xs text-muted-foreground">The intelligence service did not respond. Try again shortly.</p>
        {onRetry && (
          <Button variant="outline" size="sm" className="mt-1 gap-1.5" onClick={onRetry}>
            <RefreshCcw className="h-3 w-3" />
            Retry
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
