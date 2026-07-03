'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import {
  auth,
  admin,
  competitive,
  regulatory,
  type DemoUser,
  type PlatformStatus,
  type Institution,
  type RegulationCategory,
} from '@/lib/api';
import { canAccess, homeRoute, ROLE_LABELS, type UserRole } from '@/lib/useUserRole';
import { useIntel } from '@/lib/useIntel';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import LoadingCard from '@/components/intel/LoadingCard';
import WidgetError from '@/components/intel/WidgetError';
import { Check, Circle, Database, Plus, Users } from 'lucide-react';
import { cn } from '@/lib/utils';

function StatusDot({ ok }: { ok: boolean }) {
  return <span className={cn('inline-block h-2 w-2 rounded-full', ok ? 'bg-emerald-500' : 'bg-red-500')} />;
}

function AddInstitutionDialog({ onAdded }: { onAdded: () => void }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: '', type: '', website: '', headquarters: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      await admin.addInstitution(form);
      setForm({ name: '', type: '', website: '', headquarters: '' });
      setOpen(false);
      onAdded();
    } catch (err: any) {
      setError(err.message || 'Failed to add institution.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" className="gap-1.5 rounded-2xl">
          <Plus className="h-3.5 w-3.5" /> Add institution
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add institution</DialogTitle>
          <DialogDescription>
            Creates a registry config file — no software changes required. Ingest its documents afterwards to index intelligence.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit}>
          <div className="space-y-4 py-4">
            {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">{error}</p>}
            <div className="space-y-2">
              <Label htmlFor="inst-name">Name</Label>
              <Input id="inst-name" required value={form.name} placeholder="e.g. Belagavi DCC Bank"
                onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="inst-type">Type</Label>
              <Input id="inst-type" required value={form.type} placeholder="e.g. Co-operative Bank / NBFC"
                onChange={(e) => setForm({ ...form, type: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="inst-web">Website</Label>
              <Input id="inst-web" type="url" value={form.website} placeholder="https://…"
                onChange={(e) => setForm({ ...form, website: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="inst-hq">Headquarters</Label>
              <Input id="inst-hq" value={form.headquarters} placeholder="City, State"
                onChange={(e) => setForm({ ...form, headquarters: e.target.value })} />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Adding…' : 'Add institution'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function AddRegulationDialog({ onAdded }: { onAdded: () => void }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ display_name: '', rbi_url: '', applicability: '', effective_date: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      await admin.addRegulation(form);
      setForm({ display_name: '', rbi_url: '', applicability: '', effective_date: '' });
      setOpen(false);
      onAdded();
    } catch (err: any) {
      setError(err.message || 'Failed to add regulation category.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline" className="gap-1.5 rounded-2xl">
          <Plus className="h-3.5 w-3.5" /> Add regulation
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add regulation category</DialogTitle>
          <DialogDescription>
            Creates a registry config file for a new RBI regulation category.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit}>
          <div className="space-y-4 py-4">
            {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">{error}</p>}
            <div className="space-y-2">
              <Label htmlFor="reg-name">Display name</Label>
              <Input id="reg-name" required value={form.display_name} placeholder="e.g. Fair Practices Code"
                onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="reg-url">RBI URL</Label>
              <Input id="reg-url" type="url" value={form.rbi_url} placeholder="https://rbi.org.in/…"
                onChange={(e) => setForm({ ...form, rbi_url: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="reg-app">Applicability</Label>
              <Input id="reg-app" value={form.applicability} placeholder="Who this applies to"
                onChange={(e) => setForm({ ...form, applicability: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="reg-date">Effective date</Label>
              <Input id="reg-date" value={form.effective_date} placeholder="YYYY-MM-DD"
                onChange={(e) => setForm({ ...form, effective_date: e.target.value })} />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Adding…' : 'Add regulation'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function AdminPage() {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    auth
      .me()
      .then((user) => {
        const role = user.role as UserRole;
        if (!canAccess(role, '/admin')) {
          router.replace(homeRoute(role));
          return;
        }
        setAuthorized(true);
      })
      .catch(() => router.replace('/login'));
  }, [router]);

  const status = useIntel<PlatformStatus>(admin.status);
  const users = useIntel<DemoUser[]>(auth.users);
  const institutions = useIntel<Institution[]>(competitive.institutions);
  const regulations = useIntel<RegulationCategory[]>(regulatory.categories);

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
              Moneypal Administrator
            </Badge>
            <h1 className="font-headline text-2xl font-semibold tracking-tight md:text-3xl">Platform Administration</h1>
            <p className="max-w-2xl text-sm text-muted-foreground">
              Platform health, client onboarding and intelligence registry management for the Genesis Layer.
            </p>
          </section>

          <Tabs defaultValue="platform">
            <TabsList>
              <TabsTrigger value="platform">Platform</TabsTrigger>
              <TabsTrigger value="onboarding">Client Onboarding</TabsTrigger>
              <TabsTrigger value="intelligence">Intelligence Management</TabsTrigger>
            </TabsList>

            {/* ── Platform administration ── */}
            <TabsContent value="platform" className="mt-4 space-y-4">
              <div className="grid gap-4 lg:grid-cols-2">
                <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none">
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 font-headline text-base font-semibold">
                      <Users className="h-4 w-4 text-primary" /> Users & roles
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-0">
                    {users.loading && <div className="p-5"><LoadingCard lines={3} className="border-0" /></div>}
                    {users.error && <WidgetError title="User directory" onRetry={users.reload} className="border-0" />}
                    {users.data && (
                      <Table>
                        <TableHeader>
                          <TableRow className="border-border/70">
                            <TableHead>User</TableHead>
                            <TableHead>Role</TableHead>
                            <TableHead>Email</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {users.data.map((user) => (
                            <TableRow key={user.username} className="border-border/70">
                              <TableCell className="font-medium">{user.full_name}</TableCell>
                              <TableCell>
                                <Badge variant="secondary" className="rounded-full text-[10px]">
                                  {ROLE_LABELS[user.role as UserRole] || user.role}
                                </Badge>
                              </TableCell>
                              <TableCell className="text-xs text-muted-foreground">{user.email}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    )}
                  </CardContent>
                </Card>

                <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none">
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 font-headline text-base font-semibold">
                      <Database className="h-4 w-4 text-primary" /> System health
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-0">
                    {status.loading && <LoadingCard lines={4} className="border-0" />}
                    {status.error && <WidgetError title="Platform status" onRetry={status.reload} className="border-0" />}
                    {status.data && (
                      <>
                        {[
                          {
                            label: 'Vector store (Qdrant)',
                            value: (
                              <span className="flex items-center gap-1.5 text-xs">
                                <StatusDot ok={status.data.qdrant.ok} />
                                {status.data.qdrant.ok ? 'Connected' : 'Unreachable'} · {status.data.qdrant.host}:{status.data.qdrant.port}
                              </span>
                            ),
                          },
                          {
                            label: 'LLM',
                            value: (
                              <span className="flex items-center gap-1.5 font-mono text-xs">
                                <StatusDot ok={status.data.llm.configured} />
                                {status.data.llm.model}
                              </span>
                            ),
                          },
                          { label: 'Embeddings', value: <span className="font-mono text-xs">{status.data.embeddings.model}</span> },
                          { label: 'Institution configs', value: <span className="font-mono text-xs">{status.data.registries.institutions}</span> },
                          { label: 'Regulation configs', value: <span className="font-mono text-xs">{status.data.registries.regulations}</span> },
                        ].map((row, i, arr) => (
                          <div
                            key={row.label}
                            className={`flex items-center justify-between py-2.5 text-sm ${i < arr.length - 1 ? 'border-b border-border/50' : ''}`}
                          >
                            <span className="text-xs text-muted-foreground">{row.label}</span>
                            {row.value}
                          </div>
                        ))}
                      </>
                    )}
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            {/* ── Client onboarding ── */}
            <TabsContent value="onboarding" className="mt-4 space-y-4">
              <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none">
                <CardHeader className="pb-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center overflow-hidden">
                      <Image src="/gicc.png" alt="GICC" width={44} height={44} className="h-9 w-9 object-contain" />
                    </div>
                    <div>
                      <CardTitle className="font-headline text-base font-semibold">GICC</CardTitle>
                      <p className="text-xs text-muted-foreground">
                        <a href="https://GICCLtd.com" target="_blank" rel="noopener noreferrer" className="hover:underline">GICCLtd.com</a>
                        {' '}· Karnataka NBFC / co-operative lender · Assets under ₹500 crore
                      </p>
                    </div>
                    <Badge className="ml-auto rounded-full">Onboarding</Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Genesis journey</p>
                  {(status.data?.onboarding.phases || [
                    { name: 'Institutional Intelligence', status: 'active', detail: 'Macro, competitive and regulatory intelligence via the Aroha RAG framework' },
                    { name: 'Prosper & Tally Migration', status: 'upcoming', detail: 'Migrate operational data into Canonical Business Objects' },
                    { name: 'NEST Platform', status: 'upcoming', detail: 'Aggregate Block creation, BI, RIM and DNBS reporting' },
                  ]).map((phase, i) => (
                    <div key={phase.name} className={cn(
                      'flex items-start gap-3 rounded-2xl border p-3.5',
                      phase.status === 'active' ? 'border-primary/30 bg-primary/5' : 'border-border/60 bg-card/70'
                    )}>
                      <div className={cn(
                        'mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold',
                        phase.status === 'active' ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
                      )}>
                        {phase.status === 'done' ? <Check className="h-3.5 w-3.5" /> : i + 1}
                      </div>
                      <div>
                        <p className="text-sm font-semibold leading-tight">
                          {phase.name}
                          {phase.status === 'active' && (
                            <span className="ml-2 inline-flex items-center gap-1 text-[10px] font-medium uppercase text-primary">
                              <Circle className="h-2 w-2 animate-pulse fill-current" /> In progress
                            </span>
                          )}
                        </p>
                        <p className="mt-0.5 text-xs text-muted-foreground">{phase.detail}</p>
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </TabsContent>

            {/* ── Intelligence management ── */}
            <TabsContent value="intelligence" className="mt-4 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm text-muted-foreground">
                  Registries are config-driven — adding an entry writes a JSON file, no software changes.
                </p>
                <div className="flex gap-2">
                  <AddInstitutionDialog onAdded={() => { institutions.reload(); status.reload(); }} />
                  <AddRegulationDialog onAdded={() => { regulations.reload(); status.reload(); }} />
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none">
                  <CardHeader className="pb-2">
                    <CardTitle className="font-headline text-base font-semibold">Institution registry</CardTitle>
                  </CardHeader>
                  <CardContent className="p-0">
                    {institutions.loading && <div className="p-5"><LoadingCard lines={3} className="border-0" /></div>}
                    {institutions.error && <WidgetError title="Institution registry" onRetry={institutions.reload} className="border-0" />}
                    {institutions.data && (
                      <Table>
                        <TableHeader>
                          <TableRow className="border-border/70">
                            <TableHead>Institution</TableHead>
                            <TableHead>Type</TableHead>
                            <TableHead>Index</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {institutions.data.map((inst) => {
                            const coll = status.data?.collections.find((c) => c.collection === `comp_${inst.id}`);
                            return (
                              <TableRow key={inst.id} className="border-border/70">
                                <TableCell className="font-medium">{inst.name}</TableCell>
                                <TableCell className="text-xs text-muted-foreground">{inst.type}</TableCell>
                                <TableCell>
                                  {coll?.indexed
                                    ? <Badge variant="secondary" className="rounded-full text-[10px]">{coll.vectors ?? 0} vectors</Badge>
                                    : <Badge variant="outline" className="rounded-full text-[10px] text-muted-foreground">not ingested</Badge>}
                                </TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    )}
                  </CardContent>
                </Card>

                <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none">
                  <CardHeader className="pb-2">
                    <CardTitle className="font-headline text-base font-semibold">Regulation registry</CardTitle>
                  </CardHeader>
                  <CardContent className="p-0">
                    {regulations.loading && <div className="p-5"><LoadingCard lines={3} className="border-0" /></div>}
                    {regulations.error && <WidgetError title="Regulation registry" onRetry={regulations.reload} className="border-0" />}
                    {regulations.data && (
                      <Table>
                        <TableHeader>
                          <TableRow className="border-border/70">
                            <TableHead>Regulation</TableHead>
                            <TableHead>Priority</TableHead>
                            <TableHead>Index</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {regulations.data.map((reg) => {
                            const coll = status.data?.collections.find((c) => c.collection === `reg_${reg.id}`);
                            return (
                              <TableRow key={reg.id} className="border-border/70">
                                <TableCell className="font-medium">{reg.display_name}</TableCell>
                                <TableCell>
                                  <Badge variant="outline" className="rounded-full text-[10px] uppercase">{reg.priority}</Badge>
                                </TableCell>
                                <TableCell>
                                  {coll?.indexed
                                    ? <Badge variant="secondary" className="rounded-full text-[10px]">{coll.vectors ?? 0} vectors</Badge>
                                    : <Badge variant="outline" className="rounded-full text-[10px] text-muted-foreground">not ingested</Badge>}
                                </TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    )}
                  </CardContent>
                </Card>
              </div>

              <p className="text-xs text-muted-foreground">
                To index a new entry&apos;s documents, place its PDFs under <code className="rounded bg-muted px-1 py-0.5">backend/data/</code> and run{' '}
                <code className="rounded bg-muted px-1 py-0.5">python scripts/ingest.py</code>.
              </p>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
