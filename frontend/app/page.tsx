'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  auth,
  macro,
  competitive,
  regulatory,
  type IntelligenceResponse,
  type RegulatoryAlert,
} from '@/lib/api';
import { homeRoute, type UserRole } from '@/lib/useUserRole';
import { useIntel } from '@/lib/useIntel';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import AIBriefPanel from '@/components/intel/AIBriefPanel';
import IntelligenceCard from '@/components/intel/IntelligenceCard';
import LoadingCard from '@/components/intel/LoadingCard';
import WidgetError from '@/components/intel/WidgetError';

import GenesisSearch from '@/components/intel/GenesisSearch';
import {
  ArrowRight,
  TrendingUp,
  Building,
  Scale,
  ClipboardCheck,
  AlertTriangle,
  ChevronDown,
  ExternalLink,
} from 'lucide-react';

const severityStyles: Record<string, string> = {
  high: 'border-border/70 bg-card/70',
  medium: 'border-border/70 bg-card/70',
  low: 'border-border/70 bg-card/70',
};

const severityBadge: Record<string, string> = {
  high: 'bg-red-500/10 text-red-600 dark:bg-red-500/20 dark:text-red-400',
  medium: 'bg-amber-500/10 text-amber-600 dark:bg-amber-500/20 dark:text-amber-400',
  low: 'bg-muted text-muted-foreground',
};

// Row 3 static content — recent intelligence + hardcoded action items.
const RECENT_INTELLIGENCE = [
  { title: 'India Economic Survey — MSME credit outlook refreshed', module: 'Macro', href: '/macro', icon: TrendingUp },
  { title: 'Kinara Capital institution profile and SWOT updated', module: 'Competitive', href: '/competitive', icon: Building },
  { title: 'RBI Digital Lending Guidelines briefing regenerated', module: 'Regulatory', href: '/regulatory', icon: Scale },
  { title: 'Karnataka lending landscape cross-institution summary', module: 'Competitive', href: '/competitive', icon: Building },
  { title: 'KYC / AML Master Directions compliance actions revised', module: 'Regulatory', href: '/regulatory', icon: Scale },
];

// Collapsed alert = title + severity, expandable in place for a cleaner scan.
function AlertRow({ alert }: { alert: RegulatoryAlert }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`rounded-2xl border ${severityStyles[alert.severity] || severityStyles.low}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-start justify-between gap-2 p-3 text-left"
      >
        <p className="text-[13px] font-semibold leading-snug">{alert.title}</p>
        <span className="flex shrink-0 items-center gap-1.5">
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${severityBadge[alert.severity] || severityBadge.low}`}>
            {alert.severity}
          </span>
          <ChevronDown className={`h-3.5 w-3.5 text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`} />
        </span>
      </button>
      {open && (
        <div className="px-3 pb-3">
          <p className="text-xs text-muted-foreground">{alert.summary}</p>
          <p className="mt-1.5 text-xs font-medium text-foreground/80">→ {alert.action_required}</p>
          <div className="mt-2 flex items-center justify-between gap-2">
            <a
              href={alert.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:underline"
            >
              RBI source <ExternalLink className="h-3 w-3" />
            </a>
          </div>
          <p className="mt-1.5 text-[10px] italic text-muted-foreground">{alert.ai_note}</p>
        </div>
      )}
    </div>
  );
}

const ACTION_ITEMS = [
  { title: 'Review Digital Lending compliance checklist', due: 'Before next board meeting', priority: 'High' },
  { title: 'Assess Kinara Capital ticket-size overlap in Bengaluru districts', due: 'This week', priority: 'Medium' },
  { title: 'Schedule re-KYC audit for overdue customer accounts', due: 'This month', priority: 'High' },
];

export default function Dashboard() {
  const router = useRouter();
  const [authorized, setAuthorized] = useState<boolean | null>(null);

  useEffect(() => {
    auth
      .me()
      .then((user) => {
        const role = user.role as UserRole;
        // Policy makers land on Regulatory — the dashboard is not part of their view.
        if (role === 'gicc_policy') {
          router.replace(homeRoute(role));
          return;
        }
        setAuthorized(true);
      })
      .catch(() => router.replace('/login'));
  }, [router]);

  const briefing = useIntel<IntelligenceResponse>('macro:briefing', macro.briefing);
  const alerts = useIntel<RegulatoryAlert[]>('regulatory:alerts', regulatory.alerts);
  const snapshot = useIntel<IntelligenceResponse>('macro:snapshot', macro.snapshot);
  const landscape = useIntel<IntelligenceResponse>('competitive:landscape', competitive.landscape);

  if (authorized === null) {
    return (
      <div className="mx-auto w-full max-w-6xl space-y-4 px-4 py-8 md:px-6">
        <LoadingCard lines={6} />
        <div className="grid gap-4 md:grid-cols-2">
          <LoadingCard />
          <LoadingCard />
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto">
      <div className="mx-auto max-w-6xl px-4 py-6 md:px-6 md:py-8">
        <div className="space-y-5">
          {/* Header */}
          <section className="space-y-1">
            <h1 className="font-headline text-2xl font-semibold tracking-tight">Executive Dashboard</h1>
            <p className="text-sm text-muted-foreground">
              What GICC leadership should know today — every insight traced back to its source.
            </p>
          </section>



          {/* Explainable semantic search across all Genesis collections */}
          <GenesisSearch />

          {/* AI Briefings — Row 1: AI Executive Brief (2/3) + Regulatory Alerts (1/3) */}
          <p className="pt-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            AI Briefings
          </p>
          <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
            <div>
              {briefing.loading && <LoadingCard lines={8} className="h-full" />}
              {briefing.error && <WidgetError title="AI Executive Brief" onRetry={briefing.reload} className="h-full" />}
              {briefing.data && <AIBriefPanel data={briefing.data} className="h-full" onRefresh={briefing.reload} />}
            </div>

            <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 font-headline text-base font-semibold">
                  <AlertTriangle className="h-4 w-4 text-amber-500" />
                  Regulatory Alerts
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2.5">
                {alerts.loading &&
                  [1, 2, 3].map((i) => <div key={i} className="h-20 animate-pulse rounded-2xl bg-muted" />)}
                {alerts.error && (
                  <p className="py-4 text-center text-xs text-muted-foreground">
                    Alerts are unavailable right now.
                  </p>
                )}
                {alerts.data?.map((alert, i) => (
                  <AlertRow key={i} alert={alert} />
                ))}
              </CardContent>
            </Card>
          </div>

          {/* Strategic Insights — Row 2: Economic Snapshot + Karnataka Lending Landscape */}
          <p className="pt-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Strategic Insights
          </p>
          <div className="grid gap-4 lg:grid-cols-2">
            <div>
              {snapshot.loading && <LoadingCard className="h-full" />}
              {snapshot.error && <WidgetError title="Economic Snapshot" onRetry={snapshot.reload} className="h-full" />}
              {snapshot.data && <IntelligenceCard data={snapshot.data} className="h-full" onRefresh={snapshot.reload} collapsible />}
            </div>
            <div>
              {landscape.loading && <LoadingCard className="h-full" />}
              {landscape.error && <WidgetError title="Karnataka Lending Landscape" onRetry={landscape.reload} className="h-full" />}
              {landscape.data && <IntelligenceCard data={landscape.data} className="h-full" onRefresh={landscape.reload} collapsible />}
            </div>
          </div>

          {/* Row 3 — Recently Updated Intelligence + Action Items */}
          <div className="grid gap-4 lg:grid-cols-[1.4fr_0.6fr]">
            <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none">
              <CardHeader className="pb-3">
                <CardTitle className="font-headline text-base font-semibold">Recently Updated Intelligence</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {RECENT_INTELLIGENCE.map((item, i) => (
                  <Link
                    key={i}
                    href={item.href}
                    className="group flex w-full items-center gap-3 rounded-lg border border-border/60 bg-background px-3.5 py-3 text-left transition-all hover:border-border hover:bg-accent"
                  >
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border/60 bg-muted text-muted-foreground transition-all group-hover:border-border group-hover:bg-foreground group-hover:text-background">
                      <item.icon className="h-3.5 w-3.5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-medium group-hover:text-accent-foreground">{item.title}</p>
                      <p className="text-xs text-muted-foreground">{item.module} Intelligence</p>
                    </div>
                    <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-colors group-hover:text-foreground" />
                  </Link>
                ))}
              </CardContent>
            </Card>

            <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 font-headline text-base font-semibold">
                  <ClipboardCheck className="h-4 w-4 text-primary" />
                  Action Items
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2.5">
                {ACTION_ITEMS.map((item, i) => (
                  <div key={i} className="rounded-2xl border border-border/60 bg-card/70 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-[13px] font-medium leading-snug">{item.title}</p>
                      <Badge
                        variant="outline"
                        className={`shrink-0 rounded-full px-2 py-0 text-[10px] border-none ${
                          item.priority === 'High'
                            ? 'bg-red-500/10 text-red-600 dark:bg-red-500/20 dark:text-red-400'
                            : 'bg-amber-500/10 text-amber-600 dark:bg-amber-500/20 dark:text-amber-400'
                        }`}
                      >
                        {item.priority}
                      </Badge>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{item.due}</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
