'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { auth, review, type ReviewItem, type DemoUser } from '@/lib/api';
import { canAccess, homeRoute, ROLE_LABELS, type UserRole } from '@/lib/useUserRole';
import { useIntel } from '@/lib/useIntel';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import LoadingCard from '@/components/intel/LoadingCard';
import WidgetError from '@/components/intel/WidgetError';
import { Building2, ChevronDown, ClipboardCheck } from 'lucide-react';
import { cn } from '@/lib/utils';

const STATUS_STYLES: Record<ReviewItem['status'], string> = {
  pending: 'border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-400',
  reviewed: 'border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-400',
  flagged: 'border-red-300 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950/50 dark:text-red-400',
};

function ReviewRow({ item, onSaved }: { item: ReviewItem; onSaved: () => void }) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<ReviewItem['status']>(item.status);
  const [note, setNote] = useState(item.note);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await review.update(item.id, status, note);
      onSaved();
      setOpen(false);
    } catch {
      // keep the row open so the reviewer can retry
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="dashboard-surface overflow-hidden rounded-[1.5rem] border-border/70 shadow-none">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 p-4 text-left transition-colors hover:bg-accent/40"
      >
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold leading-snug">{item.title}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {item.module} Intelligence
            {item.reviewed_at ? ` · last reviewed ${new Date(item.reviewed_at).toLocaleDateString()}` : ''}
          </p>
        </div>
        <Badge variant="outline" className={cn('shrink-0 rounded-full px-2.5 py-0.5 text-[10px] uppercase', STATUS_STYLES[item.status])}>
          {item.status}
        </Badge>
        <ChevronDown className={cn('h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200', open && 'rotate-180')} />
      </button>

      {open && (
        <CardContent className="space-y-3 border-t border-border/50 p-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Select value={status} onValueChange={(v) => setStatus(v as ReviewItem['status'])}>
              <SelectTrigger className="w-full sm:w-[200px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="pending">Pending review</SelectItem>
                <SelectItem value="reviewed">Reviewed</SelectItem>
                <SelectItem value="flagged">Flagged for attention</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Textarea
            placeholder="Reviewer note — accuracy concerns, follow-ups, source questions…"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="min-h-[70px] text-sm"
          />
          <div className="flex justify-end">
            <Button size="sm" onClick={save} disabled={saving}>
              {saving ? 'Saving…' : 'Save review'}
            </Button>
          </div>
        </CardContent>
      )}
    </Card>
  );
}

export default function ReviewPage() {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    auth
      .me()
      .then((user) => {
        const role = user.role as UserRole;
        if (!canAccess(role, '/review')) {
          router.replace(homeRoute(role));
          return;
        }
        setAuthorized(true);
      })
      .catch(() => router.replace('/login'));
  }, [router]);

  const items = useIntel<ReviewItem[]>('review:items', review.items);
  const users = useIntel<DemoUser[]>('auth:users', auth.users);

  if (!authorized) {
    return (
      <div className="mx-auto w-full max-w-6xl space-y-4 px-4 py-8 md:px-6">
        <LoadingCard lines={6} />
      </div>
    );
  }

  const pending = items.data?.filter((i) => i.status === 'pending').length ?? 0;
  const flagged = items.data?.filter((i) => i.status === 'flagged').length ?? 0;
  const giccUsers = (users.data || []).filter((u) => u.role.startsWith('gicc'));

  return (
    <div className="h-full overflow-auto">
      <div className="mx-auto max-w-5xl px-4 py-6 md:px-6 md:py-8">
        <div className="space-y-5">
          {/* Header */}
          <section className="space-y-2">
            <Badge variant="outline" className="rounded-full border-border/80 bg-card/80 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              GICC Administrator
            </Badge>
            <h1 className="font-headline text-2xl font-semibold tracking-tight md:text-3xl">Intelligence Review</h1>
            <p className="max-w-2xl text-sm text-muted-foreground">
              Review every AI-generated intelligence item before it informs GICC decisions — mark items reviewed or flag them for correction.
            </p>
          </section>

          <div className="grid gap-4 lg:grid-cols-[1.5fr_0.5fr]">
            {/* Review queue */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <ClipboardCheck className="h-4 w-4 text-primary" />
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Review queue
                </p>
                {items.data && (
                  <span className="text-[11px] text-muted-foreground">
                    {pending} pending · {flagged} flagged
                  </span>
                )}
              </div>
              {items.loading && [1, 2, 3, 4].map((i) => <LoadingCard key={i} lines={1} />)}
              {items.error && <WidgetError title="Review queue" onRetry={items.reload} />}
              {items.data?.map((item) => (
                <ReviewRow key={item.id} item={item} onSaved={items.reload} />
              ))}
            </div>

            {/* Institution administration */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-primary" />
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Institution
                </p>
              </div>
              <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none">
                <CardHeader className="pb-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center overflow-hidden">
                      <Image src="/gicc.png" alt="GICC" width={40} height={40} className="h-8 w-8 object-contain" />
                    </div>
                    <div>
                      <CardTitle className="font-headline text-base font-semibold">GICC</CardTitle>
                      <a
                        href="https://GICCLtd.com"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-muted-foreground hover:underline"
                      >
                        GICCLtd.com
                      </a>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3 text-xs">
                  <div className="space-y-1.5">
                    <p className="text-muted-foreground">Profile</p>
                    <p>Karnataka co-operative lender / NBFC · assets under ₹500 crore · MSME lending focus</p>
                  </div>
                  <div className="space-y-1.5 border-t border-border/50 pt-3">
                    <p className="text-muted-foreground">GICC users</p>
                    {users.loading && <p className="animate-pulse text-muted-foreground">Loading…</p>}
                    {giccUsers.map((user) => (
                      <div key={user.username} className="flex items-center justify-between gap-2">
                        <span className="font-medium">{user.full_name}</span>
                        <Badge variant="secondary" className="rounded-full text-[10px]">
                          {ROLE_LABELS[user.role as UserRole] || user.role}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
