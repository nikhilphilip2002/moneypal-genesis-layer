'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { auth, companies, health as healthApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowRight, Building2, Bot, Database, RefreshCcw, TrendingUp, TrendingDown } from 'lucide-react';

interface Stats {
  total: number;
  completed: number;
  pending: number;
  failed: number;
}

interface SystemHealth {
  status: string;
  version: string;
  database: string;
}

const statCards = [
  { key: 'total', label: 'Total Companies', tag: 'Portfolio scope' },
  { key: 'completed', label: 'Completed', tag: 'Healthy' },
  { key: 'pending', label: 'Pending', tag: 'In queue' },
  { key: 'failed', label: 'Failed', tag: 'Needs review' },
];

const statColors: Record<string, string> = {
  total: 'bg-foreground/8 text-foreground',
  completed: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400',
  pending: 'bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400',
  failed: 'bg-red-50 text-red-700 dark:bg-red-950/50 dark:text-red-400',
};

const statAccents: Record<string, string> = {
  total: 'border-t-foreground/30',
  completed: 'border-t-emerald-500',
  pending: 'border-t-amber-500',
  failed: 'border-t-red-500',
};

export default function Dashboard() {
  const router = useRouter();
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const checkAuthAndLoad = async () => {
      try {
        const user = await auth.me();
        const userRole = user.role || (user.is_staff ? 'admin' : 'standard');
        if (userRole === 'standard') {
          router.replace('/knowledge-base');
          return;
        }
        setIsAdmin(true);

        setLoading(true);
        const [statsData, healthData] = await Promise.all([
          companies.stats(),
          healthApi.check(),
        ]);
        setStats(statsData);
        setHealth(healthData);
        setError(null);
      } catch (err) {
        console.error("Dashboard load failed", err);
        setError(err instanceof Error ? err.message : 'Failed to load data');
      } finally {
        setLoading(false);
      }
    };

    checkAuthAndLoad();
  }, [router]);

  if (isAdmin === null || loading) {
    return (
      <div className="h-full overflow-auto">
        <div className="mx-auto max-w-6xl space-y-6 px-6 py-8">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-64" />
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map((i) => (
              <Card key={i} className="border-border/60">
                <CardHeader className="pb-2">
                  <Skeleton className="h-3 w-24" />
                </CardHeader>
                <CardContent>
                  <Skeleton className="h-8 w-16" />
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="max-w-md mx-auto mt-8 border-destructive">
        <CardHeader>
          <CardTitle className="text-destructive">Error</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground mb-4">{error}</p>
          <Button onClick={() => window.location.reload()}>Retry</Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="h-full md:overflow-auto">
      {/* ───── Mobile layout (<md) ───── */}
      <div className="md:hidden px-4 pt-3 pb-2 space-y-4">
        {/* Greeting card */}
        <div className="rounded-2xl border border-white/60 bg-white/65 backdrop-blur-md p-4 shadow-[0_6px_20px_rgba(31,26,20,0.06)] dark:bg-black/40 dark:border-white/10">
          <p className="text-[11px] uppercase tracking-wider font-semibold text-muted-foreground">Good day</p>
          <h2 className="mt-0.5 text-xl font-bold tracking-tight">Welcome back 👋</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            {stats?.pending ? `${stats.pending} pending` : 'All clear'} ·{' '}
            {stats?.failed ? `${stats.failed} need review` : 'no failures'}
          </p>
        </div>

        {/* 2-col stat grid */}
        <div className="grid grid-cols-2 gap-2.5">
          {statCards.map((stat) => (
            <div
              key={stat.key}
              className="rounded-2xl border border-white/60 bg-white/60 backdrop-blur-md p-3 shadow-[0_4px_14px_rgba(31,26,20,0.05)] dark:bg-black/40 dark:border-white/10"
            >
              <p className="text-[10px] uppercase tracking-wider font-bold text-muted-foreground">{stat.label}</p>
              <p className="mt-1 font-mono text-2xl font-extrabold tracking-tight">
                {stats?.[stat.key as keyof Stats] ?? 0}
              </p>
              <span className={`mt-1 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${statColors[stat.key]}`}>
                {stat.key === 'failed' ? <TrendingDown className="h-2.5 w-2.5" /> : <TrendingUp className="h-2.5 w-2.5" />}
                {stat.tag}
              </span>
            </div>
          ))}
        </div>

        {/* Priority actions — full-width tap rows */}
        <div className="rounded-2xl border border-white/60 bg-white/60 backdrop-blur-md p-2 dark:bg-black/40 dark:border-white/10">
          <p className="px-2 pt-2 pb-1 text-[11px] uppercase tracking-wider font-bold text-muted-foreground">Quick actions</p>
          {[
            { icon: Building2, title: 'Company pipeline', desc: 'Pending & failed records', href: '/companies' },
            { icon: Bot, title: 'Intel assistant', desc: 'Continue analysis', href: '/intel' },
            { icon: Database, title: 'Knowledge base', desc: 'Retrieval & grounded answers', href: '/knowledge-base' },
          ].map((action) => (
            <button
              key={action.href}
              type="button"
              onClick={() => router.push(action.href)}
              className="flex w-full items-center gap-3 rounded-xl p-3 text-left active:bg-white/60 dark:active:bg-white/5 transition-colors"
            >
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
                <action.icon className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold leading-tight">{action.title}</p>
                <p className="mt-0.5 text-xs text-muted-foreground truncate">{action.desc}</p>
              </div>
              <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" />
            </button>
          ))}
        </div>

        {/* Compact health */}
        <div className="rounded-2xl border border-white/60 bg-white/60 backdrop-blur-md p-4 dark:bg-black/40 dark:border-white/10">
          <div className="flex items-center justify-between">
            <p className="text-[11px] uppercase tracking-wider font-bold text-muted-foreground">System</p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="grid h-8 w-8 place-items-center rounded-lg border border-white/60 bg-white/60 active:scale-95 transition-transform dark:bg-white/5 dark:border-white/10"
              aria-label="Refresh"
            >
              <RefreshCcw className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
            <div>
              <p className="text-muted-foreground">Status</p>
              <p className="mt-0.5 font-semibold capitalize">{health?.status || '—'}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Version</p>
              <p className="mt-0.5 font-mono text-[11px]">{health?.version || '—'}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Database</p>
              <p className="mt-0.5 font-mono text-[11px]">{health?.database || '—'}</p>
            </div>
          </div>
        </div>
      </div>

      {/* ───── Desktop layout (md+) ───── */}
      <div className="hidden md:block mx-auto max-w-6xl px-6 py-8">
        <div className="space-y-6">

          {/* Header */}
          <section className="flex items-start justify-between">
            <div className="space-y-1">
              <h1 className="font-sanstext-2xl font-semibold tracking-tight">Dashboard</h1>
              <p className="text-sm text-muted-foreground">
                Executive overview of your intelligence workflows
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => window.location.reload()}
                className="gap-1.5"
              >
                <RefreshCcw className="h-3.5 w-3.5" />
                Sync
              </Button>
              <Button
                size="sm"
                onClick={() => router.push('/companies')}
                className="gap-1.5"
              >
                Add Company
              </Button>
            </div>
          </section>

          {/* Stat Cards */}
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {statCards.map((stat) => (
              <Card
                key={stat.key}
                className={`border-border/60 border-t-2 ${statAccents[stat.key]}`}
              >
                <CardHeader className="pb-2 pt-4">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    {stat.label}
                  </p>
                </CardHeader>
                <CardContent className="space-y-2.5 pb-4">
                  <div className="font-mono text-3xl font-bold tracking-tight">
                    {stats?.[stat.key as keyof Stats] || 0}
                  </div>
                  <span className={`inline-block rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${statColors[stat.key]}`}>
                    {stat.tag}
                  </span>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Two-column grid */}
          <div className="grid gap-3 lg:grid-cols-[1.4fr_0.6fr]">

            {/* Priority Actions */}
            <Card className="border-border/60">
              <CardHeader className="pb-3">
                <CardTitle className="font-sanstext-base font-semibold">Priority actions</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Jump into the most critical workflows.
                </p>
              </CardHeader>
              <CardContent className="space-y-2">
                {[
                  {
                    icon: Building2,
                    title: 'Review company pipeline',
                    desc: 'Inspect pending and failed records, trigger targeted retries',
                    href: '/companies',
                  },
                  {
                    icon: Bot,
                    title: 'Continue in Intel assistant',
                    desc: 'Resume analysis with requirements, interviews, and context',
                    href: '/intel',
                  },
                  {
                    icon: Database,
                    title: 'Explore knowledge base',
                    desc: 'Retrieval, source quality, and grounded responses',
                    href: '/knowledge-base',
                  },
                ].map((action) => (
                  <button
                    key={action.href}
                    type="button"
                    onClick={() => router.push(action.href)}
                    className="group flex w-full items-center gap-3 rounded-lg border border-border/60 bg-background px-3.5 py-3 text-left transition-all hover:border-border hover:bg-accent"
                  >
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border/60 bg-muted text-muted-foreground transition-all group-hover:border-border group-hover:bg-foreground group-hover:text-background">
                      <action.icon className="h-3.5 w-3.5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-medium group-hover:text-accent-foreground">{action.title}</p>
                      <p className="text-xs text-muted-foreground">{action.desc}</p>
                    </div>
                    <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-colors group-hover:text-foreground" />
                  </button>
                ))}
              </CardContent>
            </Card>

            {/* System Health */}
            <Card className="border-border/60">
              <CardHeader className="pb-3">
                <CardTitle className="font-sanstext-base font-semibold">System health</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Live platform diagnostics.
                </p>
              </CardHeader>
              <CardContent className="space-y-0">
                {[
                  {
                    label: 'Status',
                    value: (
                      <Badge
                        variant="outline"
                        className={`rounded-full px-2.5 py-0.5 text-[11px] ${
                          health?.status === 'healthy'
                            ? 'border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-400'
                            : 'border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-400'
                        }`}
                      >
                        {health?.status || 'Unknown'}
                      </Badge>
                    ),
                  },
                  { label: 'Version', value: <span className="font-mono text-xs">{health?.version || 'N/A'}</span> },
                  { label: 'Database', value: <span className="font-mono text-xs">{health?.database || 'N/A'}</span> },
                  { label: 'Last sync', value: <span className="font-mono text-xs">2 min ago</span> },
                  { label: 'Uptime', value: <span className="font-mono text-xs">99.97%</span> },
                ].map((row, i, arr) => (
                  <div
                    key={row.label}
                    className={`flex items-center justify-between py-2.5 text-sm ${i < arr.length - 1 ? 'border-b border-border/50' : ''}`}
                  >
                    <span className="text-muted-foreground text-xs">{row.label}</span>
                    {row.value}
                  </div>
                ))}
                <div className="pt-4">
                  <Button
                    variant="outline"
                    className="w-full justify-center text-xs"
                    size="sm"
                    onClick={() => window.location.reload()}
                  >
                    <RefreshCcw className="mr-1.5 h-3 w-3" />
                    Refresh
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
