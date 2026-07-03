'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  auth,
  competitive,
  regulatory,
  policy,
  type Institution,
  type RegulationCategory,
  type IntelligenceResponse,
} from '@/lib/api';
import { canAccess, homeRoute, type UserRole } from '@/lib/useUserRole';
import { useIntel } from '@/lib/useIntel';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import AIBriefPanel from '@/components/intel/AIBriefPanel';
import LoadingCard from '@/components/intel/LoadingCard';
import WidgetError from '@/components/intel/WidgetError';
import { useToast } from '@/components/ui/use-toast';
import { Building, Copy, FileText, Scale, Sparkles } from 'lucide-react';

export default function PolicyPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [authorized, setAuthorized] = useState(false);
  const [selectedRegs, setSelectedRegs] = useState<string[]>([]);
  const [selectedInsts, setSelectedInsts] = useState<string[]>([]);
  const [focus, setFocus] = useState('');
  const [brief, setBrief] = useState<IntelligenceResponse | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    auth
      .me()
      .then((user) => {
        const role = user.role as UserRole;
        if (!canAccess(role, '/policy')) {
          router.replace(homeRoute(role));
          return;
        }
        setAuthorized(true);
      })
      .catch(() => router.replace('/login'));
  }, [router]);

  const regulations = useIntel<RegulationCategory[]>(regulatory.categories);
  const institutions = useIntel<Institution[]>(competitive.institutions);

  const toggle = (list: string[], setList: (v: string[]) => void, id: string) => {
    setList(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  };

  const generate = async () => {
    setGenerating(true);
    setError('');
    setBrief(null);
    try {
      const result = await policy.brief({
        regulation_ids: selectedRegs,
        institution_ids: selectedInsts,
        focus,
      });
      setBrief(result);
    } catch (err: any) {
      setError(err.message || 'Policy synthesis failed.');
    } finally {
      setGenerating(false);
    }
  };

  const copyBrief = async () => {
    if (!brief) return;
    await navigator.clipboard.writeText(`${brief.title}\n\n${brief.summary}\n\nSource: ${brief.source.document} — ${brief.source.url}\n${brief.ai_note}`);
    toast({ title: 'Policy brief copied to clipboard' });
  };

  if (!authorized) {
    return (
      <div className="mx-auto w-full max-w-6xl space-y-4 px-4 py-8 md:px-6">
        <LoadingCard lines={6} />
      </div>
    );
  }

  const canGenerate = selectedRegs.length + selectedInsts.length > 0 && !generating;

  return (
    <div className="h-full overflow-auto">
      <div className="mx-auto max-w-6xl px-4 py-6 md:px-6 md:py-8">
        <div className="space-y-5">
          {/* Header */}
          <section className="space-y-2">
            <Badge variant="outline" className="rounded-full border-border/80 bg-card/80 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              GICC Policy Maker
            </Badge>
            <h1 className="font-headline text-2xl font-semibold tracking-tight md:text-3xl">Policy Workspace</h1>
            <p className="max-w-2xl text-sm text-muted-foreground">
              Formulate policy from evidence — select regulatory and competitive inputs and Genesis drafts a grounded, source-cited policy brief.
            </p>
          </section>

          <div className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
            {/* Input selection */}
            <div className="space-y-4">
              <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none">
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 font-headline text-base font-semibold">
                    <Scale className="h-4 w-4 text-primary" /> Regulatory inputs
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {regulations.loading && <LoadingCard lines={3} className="border-0" />}
                  {regulations.error && <WidgetError title="Regulations" onRetry={regulations.reload} className="border-0" />}
                  {regulations.data?.map((reg) => (
                    <label key={reg.id} className="flex cursor-pointer items-start gap-2.5 rounded-xl border border-border/60 bg-card/70 p-3 transition-colors hover:border-primary/40">
                      <Checkbox
                        checked={selectedRegs.includes(reg.id)}
                        onCheckedChange={() => toggle(selectedRegs, setSelectedRegs, reg.id)}
                        className="mt-0.5"
                      />
                      <span>
                        <span className="block text-[13px] font-medium leading-snug">{reg.display_name}</span>
                        {reg.applicability && (
                          <span className="mt-0.5 block text-[11px] text-muted-foreground">{reg.applicability}</span>
                        )}
                      </span>
                    </label>
                  ))}
                </CardContent>
              </Card>

              <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none">
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 font-headline text-base font-semibold">
                    <Building className="h-4 w-4 text-primary" /> Competitive inputs
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {institutions.loading && <LoadingCard lines={3} className="border-0" />}
                  {institutions.error && <WidgetError title="Institutions" onRetry={institutions.reload} className="border-0" />}
                  {institutions.data?.map((inst) => (
                    <label key={inst.id} className="flex cursor-pointer items-start gap-2.5 rounded-xl border border-border/60 bg-card/70 p-3 transition-colors hover:border-primary/40">
                      <Checkbox
                        checked={selectedInsts.includes(inst.id)}
                        onCheckedChange={() => toggle(selectedInsts, setSelectedInsts, inst.id)}
                        className="mt-0.5"
                      />
                      <span>
                        <span className="block text-[13px] font-medium leading-snug">{inst.name}</span>
                        <span className="mt-0.5 block text-[11px] text-muted-foreground">{inst.type}</span>
                      </span>
                    </label>
                  ))}
                </CardContent>
              </Card>

              <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none">
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 font-headline text-base font-semibold">
                    <FileText className="h-4 w-4 text-primary" /> Policy focus
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Textarea
                    placeholder="e.g. Should GICC introduce collateral-free digital MSME loans under ₹10 lakh?"
                    value={focus}
                    onChange={(e) => setFocus(e.target.value)}
                    className="min-h-[80px] text-sm"
                  />
                  <Button className="w-full gap-1.5" onClick={generate} disabled={!canGenerate}>
                    <Sparkles className="h-4 w-4" />
                    {generating ? 'Drafting policy brief…' : 'Generate policy brief'}
                  </Button>
                  {!selectedRegs.length && !selectedInsts.length && (
                    <p className="text-center text-[11px] text-muted-foreground">
                      Select at least one regulation or institution.
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Generated brief */}
            <div className="space-y-3">
              {generating && <LoadingCard lines={10} />}
              {error && <WidgetError title="Policy synthesis" onRetry={generate} />}
              {brief && (
                <>
                  <div className="flex justify-end">
                    <Button variant="outline" size="sm" className="gap-1.5" onClick={copyBrief}>
                      <Copy className="h-3.5 w-3.5" /> Copy brief
                    </Button>
                  </div>
                  <AIBriefPanel data={brief} />
                </>
              )}
              {!brief && !generating && !error && (
                <Card className="dashboard-surface rounded-[1.75rem] border-dashed border-border/70 shadow-none">
                  <CardContent className="flex flex-col items-center justify-center gap-2 py-20 text-center">
                    <FileText className="h-6 w-6 text-muted-foreground/50" />
                    <p className="text-sm font-medium text-muted-foreground">No brief drafted yet</p>
                    <p className="max-w-xs text-xs text-muted-foreground/80">
                      Choose regulatory and competitive inputs on the left, describe the policy question, and generate a grounded draft.
                    </p>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
