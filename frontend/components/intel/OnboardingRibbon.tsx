'use client';

import Image from 'next/image';
import { Card, CardContent } from '@/components/ui/card';
import { Check, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

// Genesis onboarding journey (developer brief §9). Static by design — the
// phase definitions also live in the backend's /admin/status payload; the
// ribbon renders without any API dependency so it never blocks the dashboard.
const PHASES = [
  { name: 'Institutional Intelligence', status: 'active' as const },
  { name: 'Prosper & Tally Migration', status: 'upcoming' as const },
  { name: 'NEST Platform', status: 'upcoming' as const },
];

// Presents the console as a joint onboarding environment: GICC is being
// onboarded onto the Moneypal platform, currently in Genesis Phase 1.
export default function OnboardingRibbon({ className }: { className?: string }) {
  return (
    <Card className={cn('dashboard-surface rounded-[1.5rem] border-border/70 shadow-none', className)}>
      <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between md:p-5">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <div className="flex h-9 w-[68px] items-center justify-center overflow-hidden">
              <Image src="/moneypal.png" alt="Moneypal" width={128} height={64} className="h-8 w-16 object-contain" />
            </div>
            <span className="text-xs text-muted-foreground">×</span>
            <div className="flex h-9 w-9 items-center justify-center overflow-hidden">
              <Image src="/gicc.png" alt="GICC" width={36} height={36} className="h-8 w-8 object-contain" />
            </div>
          </div>
          <div>
            <p className="text-[13px] font-semibold leading-tight">GICC onboarding — Genesis Layer</p>
            <p className="text-xs text-muted-foreground">Joint environment · Moneypal Digital Services × GICC</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {PHASES.map((phase, i) => (
            <div key={phase.name} className="flex items-center gap-1.5">
              <span
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium',
                  phase.status === 'active'
                    ? 'border-primary/30 bg-primary/10 text-primary'
                    : 'border-border/70 bg-muted/50 text-muted-foreground'
                )}
              >
                {phase.status === 'active' ? (
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />
                ) : (
                  <Check className="h-3 w-3 opacity-0" aria-hidden />
                )}
                Phase {i + 1}: {phase.name}
              </span>
              {i < PHASES.length - 1 && <ChevronRight className="h-3 w-3 text-muted-foreground/50" />}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
