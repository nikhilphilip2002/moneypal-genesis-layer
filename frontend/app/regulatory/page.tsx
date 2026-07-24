'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  auth,
  regulatory,
  type RegulationCategory,
  type IntelligenceResponse,
} from '@/lib/api';
import { canAccess, homeRoute, type UserRole } from '@/lib/useUserRole';
import { useIntel } from '@/lib/useIntel';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import IntelligenceCard from '@/components/intel/IntelligenceCard';
import LoadingCard from '@/components/intel/LoadingCard';
import WidgetError from '@/components/intel/WidgetError';
import DBSchemaGraph from '@/components/intel/DBSchemaGraph';
import DNBSReport from '@/components/intel/DNBSReport';
import { ChevronDown, ExternalLink, Scale } from 'lucide-react';
import { cn } from '@/lib/utils';


const priorityStyles: Record<string, string> = {
  high: 'bg-red-500/10 text-red-600 dark:bg-red-500/20 dark:text-red-400 border-none',
  medium: 'bg-amber-500/10 text-amber-600 dark:bg-amber-500/20 dark:text-amber-400 border-none',
  low: 'bg-muted text-muted-foreground border-none',
};

function CategoryDetail({ category }: { category: RegulationCategory }) {
  const detail = useIntel<IntelligenceResponse>(`regulatory:detail:${category.id}`, (refresh) =>
    regulatory.detail(category.id, refresh),
  );
  return (
    <>
      {detail.loading && <LoadingCard lines={8} className="border-0 shadow-none" />}
      {detail.error && <WidgetError title={category.display_name} onRetry={detail.reload} className="border-0 shadow-none" />}
      {detail.data && <IntelligenceCard data={detail.data} className="border-0 shadow-none" onRefresh={detail.reload} />}
    </>
  );
}

function CategoryRow({ category }: { category: RegulationCategory }) {
  const [open, setOpen] = useState(false);

  return (
    <Card className="dashboard-surface overflow-hidden rounded-[1.5rem] border-border/70 shadow-none">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 p-4 text-left transition-colors hover:bg-accent/40 md:p-5"
      >
        <div className="rounded-2xl bg-accent p-2 text-accent-foreground">
          <Scale className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold leading-snug">{category.display_name}</p>
          <p className="mt-0.5 truncate text-xs text-muted-foreground">
            {category.applicability || 'Applies to NBFCs'}
            {category.effective_date ? ` · Effective ${category.effective_date}` : ''}
          </p>
        </div>
        <Badge
          variant="outline"
          className={cn('shrink-0 rounded-full px-2.5 py-0.5 text-[10px] uppercase', priorityStyles[category.priority || 'medium'] || priorityStyles.medium)}
        >
          {category.priority || 'medium'}
        </Badge>
        {category.rbi_url && (
          <a
            href={category.rbi_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="hidden shrink-0 items-center gap-1 text-[11px] font-medium text-primary hover:underline sm:inline-flex"
          >
            RBI source <ExternalLink className="h-3 w-3" />
          </a>
        )}
        <ChevronDown className={cn('h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200', open && 'rotate-180')} />
      </button>

      {open && (
        <CardContent className="border-t border-border/50 p-4 md:p-5">
          <CategoryDetail category={category} />
        </CardContent>
      )}
    </Card>
  );
}

export default function RegulatoryPage() {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);
  const [activeTab, setActiveTab] = useState('briefings');

  useEffect(() => {
    auth
      .me()
      .then((user) => {
        const role = user.role as UserRole;
        if (!canAccess(role, '/regulatory')) {
          router.replace(homeRoute(role));
          return;
        }
        setAuthorized(true);
      })
      .catch(() => router.replace('/login'));
  }, [router]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const tab = params.get('tab');
      if (tab === 'schema') {
        setActiveTab('schema');
      } else if (tab === 'dnbs') {
        setActiveTab('dnbs');
      }
    }
  }, []);


  const categories = useIntel<RegulationCategory[]>('regulatory:categories', regulatory.categories);

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
            <h1 className="font-headline text-2xl font-semibold tracking-tight md:text-3xl">Regulatory Intelligence</h1>
            <p className="max-w-2xl text-sm text-muted-foreground">
              RBI regulations applicable to NBFCs below ₹500 crore, translated into GICC business logic, alongside relational schema metrics.
            </p>
          </section>

          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="mb-4">
              <TabsTrigger value="briefings">RBI Regulation Briefings</TabsTrigger>
              <TabsTrigger value="schema">Database Curiosity Graph</TabsTrigger>
              <TabsTrigger value="dnbs">RBI DNBS Return</TabsTrigger>
            </TabsList>

            <TabsContent value="briefings" className="space-y-3 mt-0">
              {/* Category list */}
              {categories.loading && (
                <div className="space-y-3">
                  {[1, 2, 3, 4].map((i) => (
                    <LoadingCard key={i} lines={1} />
                  ))}
                </div>
              )}
              {categories.error && <WidgetError title="Regulation registry" onRetry={categories.reload} />}
              {categories.data && (
                <div className="space-y-3">
                  {categories.data.map((category) => (
                    <CategoryRow key={category.id} category={category} />
                  ))}
                  {categories.data.length === 0 && (
                    <p className="py-12 text-center text-sm text-muted-foreground">No regulation categories configured.</p>
                  )}
                </div>
              )}
            </TabsContent>

            <TabsContent value="schema" className="mt-0">
              <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none overflow-hidden p-4 md:p-6 bg-card min-h-[680px]">
                <DBSchemaGraph />
              </Card>
            </TabsContent>

            <TabsContent value="dnbs" className="mt-0">
              <DNBSReport />
            </TabsContent>
          </Tabs>

        </div>
      </div>
    </div>
  );
}
