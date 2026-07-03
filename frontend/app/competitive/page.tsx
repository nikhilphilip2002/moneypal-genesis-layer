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
  const [profile, setProfile] = useState<IntelligenceResponse | null>(null);
  const [swot, setSwot] = useState<SwotResponse | null>(null);
  const [profileError, setProfileError] = useState(false);
  const [swotError, setSwotError] = useState(false);

  useEffect(() => {
    setProfile(null);
    setSwot(null);
    setProfileError(false);
    setSwotError(false);
    competitive.profile(institution.id).then(setProfile).catch(() => setProfileError(true));
    competitive.swot(institution.id).then(setSwot).catch(() => setSwotError(true));
  }, [institution.id]);

  return (
    <div className="space-y-4 pb-8">
      {!profile && !profileError && <LoadingCard lines={8} />}
      {profileError && <WidgetError title="Institution profile" />}
      {profile && <IntelligenceCard data={profile} />}

      {!swot && !swotError && <LoadingCard lines={6} />}
      {swotError && <WidgetError title="SWOT analysis" />}
      {swot && <SWOTCard data={swot} />}
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

  const institutions = useIntel<Institution[]>(competitive.institutions);

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
              Module 2
            </Badge>
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
