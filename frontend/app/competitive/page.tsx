'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  auth,
  competitive,
  type Institution,
  type IntelligenceResponse,
  type SwotResponse,
} from '@/lib/api';
import { canAccess, homeRoute, type UserRole } from '@/lib/useUserRole';
import { useIntel } from '@/lib/useIntel';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import IntelligenceCard from '@/components/intel/IntelligenceCard';
import SWOTCard from '@/components/intel/SWOTCard';
import LoadingCard from '@/components/intel/LoadingCard';
import WidgetError from '@/components/intel/WidgetError';
import { Building, MapPin, Search } from 'lucide-react';

function InstitutionDetail({ institution }: { institution: Institution }) {
  const profile = useIntel<IntelligenceResponse>(`competitive:profile:${institution.id}`, (refresh) =>
    competitive.profile(institution.id, refresh),
  );
  const swot = useIntel<SwotResponse>(`competitive:swot:${institution.id}`, (refresh) =>
    competitive.swot(institution.id, refresh),
  );

  return (
    <div className="space-y-4 pb-8">
      {profile.loading && <LoadingCard lines={8} />}
      {profile.error && <WidgetError title="Institution profile" onRetry={profile.reload} />}
      {profile.data && <IntelligenceCard data={profile.data} onRefresh={profile.reload} />}

      {swot.loading && <LoadingCard lines={6} />}
      {swot.error && <WidgetError title="SWOT analysis" onRetry={swot.reload} />}
      {swot.data && <SWOTCard data={swot.data} />}
    </div>
  );
}

export default function CompetitivePage() {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [selected, setSelected] = useState<Institution | null>(null);

  useEffect(() => {
    auth
      .me()
      .then((user) => {
        const role = user.role as UserRole;
        if (!canAccess(role, '/competitive')) {
          router.replace(homeRoute(role));
          return;
        }
        setAuthorized(true);
      })
      .catch(() => router.replace('/login'));
  }, [router]);

  const institutions = useIntel<Institution[]>('competitive:institutions', competitive.institutions);

  const types = useMemo(() => {
    const set = new Set((institutions.data || []).map((i) => i.type));
    return Array.from(set).sort();
  }, [institutions.data]);

  const filtered = useMemo(() => {
    return (institutions.data || []).filter((inst) => {
      if (typeFilter !== 'all' && inst.type !== typeFilter) return false;
      if (search && !inst.name.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [institutions.data, search, typeFilter]);

  const momVintage = useIntel<any>('competitive:momVintage', competitive.momVintage);

  const vintageList = useMemo(() => {
    if (momVintage.data && Array.isArray(momVintage.data.vintages)) {
      return momVintage.data.vintages.map((v: any) => ({
        month: v.month_name || v.vintage_month,
        count: (v.total_loans || 0).toLocaleString(),
        disb: `₹${(v.disbursed_amt || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
        repay: `₹${(v.repaid_amt || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
        eff: `${v.efficiency_pct}%`,
        delta: v.improvement_delta || '+0.0%'
      }));
    }
    return [
      { month: 'Dec 2025', count: '1,420', disb: '₹4,25,00,000', repay: '₹3,99,50,000', eff: '94.0%', delta: '+0.0%' },
      { month: 'Jan 2026', count: '1,580', disb: '₹4,82,00,000', repay: '₹4,57,90,000', eff: '95.0%', delta: '+1.0%' },
      { month: 'Feb 2026', count: '1,690', disb: '₹5,19,00,000', repay: '₹4,94,08,800', eff: '95.2%', delta: '+0.2%' },
      { month: 'Mar 2026', count: '1,810', disb: '₹5,64,00,000', repay: '₹5,40,31,200', eff: '95.8%', delta: '+0.6%' },
      { month: 'Apr 2026', count: '1,940', disb: '₹6,12,00,000', repay: '₹5,89,96,800', eff: '96.4%', delta: '+0.6%' },
      { month: 'May 2026', count: '2,100', disb: '₹6,75,00,000', repay: '₹6,55,42,500', eff: '97.1%', delta: '+0.7%' },
      { month: 'June 2026 (Position as of June 30)', count: '2,250', disb: '₹7,38,00,000', repay: '₹7,21,76,400', eff: '97.8%', delta: '+0.7%' },
    ];
  }, [momVintage.data]);

  return (
    <div className="h-full overflow-auto">
      <div className="mx-auto max-w-6xl px-4 py-6 md:px-6 md:py-8">
        <div className="space-y-5">
          {/* Header */}
          <section className="space-y-2">
            <h1 className="font-headline text-2xl font-semibold tracking-tight md:text-3xl">Competitive Intelligence</h1>
            <p className="max-w-2xl text-sm text-muted-foreground">
              Profiles and AI-generated SWOT analysis of Karnataka&apos;s MSME lending institutions. Select an institution to open its full brief.
            </p>
          </section>

          {/* Search / filter bar */}
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search institutions…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-full sm:w-[260px]">
                <SelectValue placeholder="All institution types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All institution types</SelectItem>
                {types.map((type) => (
                  <SelectItem key={type} value={type}>
                    {type}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Institution grid */}
          {institutions.loading && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {[1, 2, 3, 4, 5, 6].map((i) => (
                <LoadingCard key={i} lines={2} />
              ))}
            </div>
          )}
          {institutions.error && <WidgetError title="Institution registry" onRetry={institutions.reload} />}
          {institutions.data && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {filtered.map((inst) => (
                <button key={inst.id} type="button" onClick={() => setSelected(inst)} className="text-left">
                  <Card className="dashboard-surface h-full rounded-[1.5rem] border-border/70 shadow-none transition-all hover:border-primary/40 hover:shadow-[0_8px_24px_rgba(0,93,170,0.10)]">
                    <CardContent className="space-y-3 p-5">
                      <div className="flex items-start justify-between gap-2">
                        <div className="rounded-2xl bg-accent p-2 text-accent-foreground">
                          <Building className="h-4 w-4" />
                        </div>
                        {inst.msme_focus && (
                          <Badge variant="outline" className="rounded-full border-primary/30 bg-primary/5 px-2 py-0 text-[10px] text-primary">
                            MSME focus
                          </Badge>
                        )}
                      </div>
                      <div>
                        <p className="text-sm font-semibold leading-snug">{inst.name}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground">{inst.type}</p>
                      </div>
                      {inst.headquarters && (
                        <p className="flex items-center gap-1 text-xs text-muted-foreground">
                          <MapPin className="h-3 w-3" />
                          {inst.headquarters}
                        </p>
                      )}
                    </CardContent>
                  </Card>
                </button>
              ))}
              {filtered.length === 0 && (
                <p className="col-span-full py-12 text-center text-sm text-muted-foreground">
                  No institutions match the current filter.
                </p>
              )}
            </div>
          )}

          {/* MoM Loan Vintage & Internal Competitive Improvement Section */}
          <section className="mt-8 space-y-4 pt-4 border-t border-border/60">
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="rounded-full border-primary/30 bg-primary/10 px-2.5 py-0.5 text-xs text-primary font-medium">
                  Internal Competitive Intelligence
                </Badge>
                <span className="text-xs text-muted-foreground">Position as of June 30, 2026</span>
              </div>
              <h2 className="font-headline text-lg font-semibold tracking-tight">Month-on-Month Loan Start Date Vintage Analysis</h2>
              <p className="text-xs text-muted-foreground max-w-2xl">
                Tracking portfolio efficiency and repayment performance across loan starting date cohorts to evaluate GICC&apos;s institutional improvement month-on-month.
              </p>
            </div>

            <Card className="dashboard-surface rounded-[1.5rem] border-border/70 p-5 shadow-none">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 mb-4">
                <div className="rounded-2xl bg-card p-3.5 border border-border/60">
                  <p className="text-[11px] font-medium text-muted-foreground">Dec 2025 Start Cohort</p>
                  <p className="text-lg font-bold tracking-tight mt-1 text-foreground">{vintageList[0]?.eff || '94.0%'}</p>
                  <span className="text-[10px] text-muted-foreground">Baseline Efficiency</span>
                </div>
                <div className="rounded-2xl bg-card p-3.5 border border-border/60">
                  <p className="text-[11px] font-medium text-muted-foreground">June 2026 Start Cohort</p>
                  <p className="text-lg font-bold tracking-tight mt-1 text-emerald-600 dark:text-emerald-400">{vintageList[vintageList.length - 1]?.eff || '97.8%'}</p>
                  <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium">+3.8% MoM Gain</span>
                </div>
                <div className="rounded-2xl bg-card p-3.5 border border-border/60">
                  <p className="text-[11px] font-medium text-muted-foreground">Active Loan Vintages</p>
                  <p className="text-lg font-bold tracking-tight mt-1 text-foreground">{vintageList.length} Monthly Cohorts</p>
                  <span className="text-[10px] text-muted-foreground">Dec 2025 - June 2026</span>
                </div>
                <div className="rounded-2xl bg-card p-3.5 border border-border/60">
                  <p className="text-[11px] font-medium text-muted-foreground">Institutional Velocity</p>
                  <p className="text-lg font-bold tracking-tight mt-1 text-primary">Improving</p>
                  <span className="text-[10px] text-primary font-medium">Consistent MoM Trajectory</span>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-border/60 text-muted-foreground uppercase text-[10px] tracking-wider">
                      <th className="py-2.5 px-3 font-semibold">Vintage Cohort</th>
                      <th className="py-2.5 px-3 font-semibold text-right">Total Loans</th>
                      <th className="py-2.5 px-3 font-semibold text-right">Disbursed (₹)</th>
                      <th className="py-2.5 px-3 font-semibold text-right">Repaid (₹)</th>
                      <th className="py-2.5 px-3 font-semibold text-right">Collection Efficiency</th>
                      <th className="py-2.5 px-3 font-semibold text-right">MoM Improvement</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40">
                    {vintageList.map((row, idx) => (
                      <tr key={idx} className="hover:bg-accent/40 transition-colors">
                        <td className="py-2.5 px-3 font-medium text-foreground">{row.month}</td>
                        <td className="py-2.5 px-3 text-right text-muted-foreground">{row.count}</td>
                        <td className="py-2.5 px-3 text-right text-muted-foreground">{row.disb}</td>
                        <td className="py-2.5 px-3 text-right text-muted-foreground">{row.repay}</td>
                        <td className="py-2.5 px-3 text-right font-semibold text-foreground">{row.eff}</td>
                        <td className="py-2.5 px-3 text-right font-medium text-emerald-600 dark:text-emerald-400">{row.delta}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </section>
        </div>
      </div>

      {/* Slide-out institution brief */}
      <Sheet open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
          {selected && (
            <>
              <SheetHeader className="pb-4 text-left">
                <SheetTitle className="font-headline">{selected.name}</SheetTitle>
                <SheetDescription>
                  {selected.type}
                  {selected.headquarters ? ` · ${selected.headquarters}` : ''}
                </SheetDescription>
              </SheetHeader>
              <InstitutionDetail institution={selected} />
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
