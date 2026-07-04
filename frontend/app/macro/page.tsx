'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { auth, macro, type IntelligenceResponse } from '@/lib/api';
import { canAccess, homeRoute, type UserRole } from '@/lib/useUserRole';
import { useIntel } from '@/lib/useIntel';
import { Badge } from '@/components/ui/badge';
import AIBriefPanel from '@/components/intel/AIBriefPanel';
import IntelligenceCard from '@/components/intel/IntelligenceCard';
import LoadingCard from '@/components/intel/LoadingCard';
import WidgetError from '@/components/intel/WidgetError';

export default function MacroPage() {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    auth
      .me()
      .then((user) => {
        const role = user.role as UserRole;
        if (!canAccess(role, '/macro')) {
          router.replace(homeRoute(role));
          return;
        }
        setAuthorized(true);
      })
      .catch(() => router.replace('/login'));
  }, [router]);

  const briefing = useIntel<IntelligenceResponse>('macro:briefing', macro.briefing);
  const snapshot = useIntel<IntelligenceResponse>('macro:snapshot', macro.snapshot);
  const karnataka = useIntel<IntelligenceResponse>('macro:karnataka', macro.karnataka);
  const msme = useIntel<IntelligenceResponse>('macro:msme', macro.msme);

  if (!authorized) {
    return (
      <div className="mx-auto w-full max-w-6xl space-y-4 px-4 py-8 md:px-6">
        <LoadingCard lines={6} />
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto">
      <div className="mx-auto max-w-6xl px-4 py-6 md:px-6 md:py-8">
        <div className="space-y-5">
          {/* Header */}
          <section className="space-y-2">
            <Badge variant="outline" className="rounded-full border-border/80 bg-card/80 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              Module 1
            </Badge>
            <h1 className="font-headline text-2xl font-semibold tracking-tight md:text-3xl">Macro-economic Intelligence</h1>
            <p className="max-w-2xl text-sm text-muted-foreground">
              India&apos;s macro economy and Karnataka&apos;s MSME lending landscape, distilled for GICC leadership.
            </p>
          </section>

          {/* Executive brief — full width */}
          <div>
            {briefing.loading && <LoadingCard lines={8} />}
            {briefing.error && <WidgetError title="AI Executive Brief" onRetry={briefing.reload} />}
            {briefing.data && <AIBriefPanel data={briefing.data} onRefresh={briefing.reload} />}
          </div>

          {/* 3 intelligence cards */}
          <div className="grid gap-4 lg:grid-cols-3">
            {[
              { label: 'Economic Snapshot', state: snapshot },
              { label: 'Karnataka Economy', state: karnataka },
              { label: 'MSME Lending Trends', state: msme },
            ].map(({ label, state }) => (
              <div key={label}>
                {state.loading && <LoadingCard className="h-full" />}
                {state.error && <WidgetError title={label} onRetry={state.reload} className="h-full" />}
                {state.data && <IntelligenceCard data={state.data} className="h-full" onRefresh={state.reload} />}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
