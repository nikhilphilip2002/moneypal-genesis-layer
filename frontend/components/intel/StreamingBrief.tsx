'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { streamBriefing, type IntelligenceResponse } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import BriefRenderer from '@/components/intel/BriefRenderer';
import AIBriefPanel from '@/components/intel/AIBriefPanel';
import LoadingCard from '@/components/intel/LoadingCard';
import WidgetError from '@/components/intel/WidgetError';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

// Shares the sessionStorage brief cache with useIntel (same PREFIX + key) so a
// generated brief survives tab navigation and renders instantly on return.
const CACHE_KEY = 'intel.v3:macro:briefing';

function readCache(): IntelligenceResponse | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    return raw ? (JSON.parse(raw) as IntelligenceResponse) : null;
  } catch {
    return null;
  }
}

function writeCache(data: IntelligenceResponse) {
  try {
    sessionStorage.setItem(CACHE_KEY, JSON.stringify(data));
  } catch {
    // best-effort
  }
}

type Status = 'connecting' | 'streaming' | 'done' | 'error';

// The home dashboard's executive brief, streamed token-by-token from the LLM.
// Falls back to the same panel/skeleton the rest of the dashboard uses so it
// reads as one surface.
export default function StreamingBrief({ className }: { className?: string }) {
  const [status, setStatus] = useState<Status>('connecting');
  const [partial, setPartial] = useState('');
  const [data, setData] = useState<IntelligenceResponse | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback((refresh: boolean) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setPartial('');
    setStatus('connecting');

    streamBriefing(
      { refresh, signal: controller.signal },
      {
        onToken: (text) => {
          setStatus('streaming');
          setPartial((prev) => prev + text);
        },
        onDone: (brief) => {
          writeCache(brief);
          setData(brief);
          setStatus('done');
        },
        onError: () => {
          setStatus('error');
        },
      },
    );
  }, []);

  useEffect(() => {
    const cached = readCache();
    if (cached) {
      setData(cached);
      setStatus('done');
      return;
    }
    start(false);
    return () => abortRef.current?.abort();
  }, [start]);

  const handleRefresh = useCallback(() => start(true), [start]);

  if (status === 'done' && data) {
    return <AIBriefPanel data={data} onRefresh={handleRefresh} className={className} />;
  }

  if (status === 'error') {
    return <WidgetError title="AI Executive Brief" onRetry={handleRefresh} className={className} />;
  }

  if (status === 'streaming') {
    return (
      <Card className={cn('dashboard-surface rounded-[1.75rem] border-border/70 shadow-none', className)}>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2 text-xs font-medium text-primary" aria-live="polite">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Generating live…
          </div>
          <CardTitle className="font-headline pt-2 text-xl font-semibold leading-snug md:text-2xl">
            Macro Intelligence
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-[15px]">
            <BriefRenderer content={partial} />
            <span className="ml-0.5 inline-block h-4 w-[2px] translate-y-0.5 animate-pulse bg-primary align-baseline" />
          </div>
        </CardContent>
      </Card>
    );
  }

  // connecting — no tokens yet
  return <LoadingCard lines={8} className={className} showStatus />;
}
