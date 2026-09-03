'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  BadgeCheck,
  Building2,
  Calendar,
  CheckCircle2,
  ChevronRight,
  CircleDollarSign,
  Clock,
  CreditCard,
  FileText,
  Mail,
  MapPin,
  Phone,
  RefreshCw,
  Shield,
  ShieldAlert,
  User,
  X,
  XCircle,
} from 'lucide-react';

import { admin, Customer360Response } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

interface Customer360DialogProps {
  customerId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function formatExactMoney(val?: number): string {
  const num = Number(val || 0);
  return `₹${num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatCompactMoney(val?: number): string {
  const value = Number(val || 0);
  const abs = Math.abs(value);
  if (abs >= 10_000_000) return `₹${(value / 10_000_000).toFixed(2)} Cr`;
  if (abs >= 100_000) return `₹${(value / 100_000).toFixed(2)} L`;
  if (abs >= 1_000) return `₹${(value / 1_000).toFixed(1)} K`;
  return `₹${value.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

export default function Customer360Dialog({
  customerId,
  open,
  onOpenChange,
}: Customer360DialogProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [data, setData] = useState<Customer360Response | null>(null);
  const [selectedLoanAccount, setSelectedLoanAccount] = useState<string>('all');

  useEffect(() => {
    if (!open || !customerId) {
      setData(null);
      setError('');
      return;
    }

    let isCancelled = false;
    setLoading(true);
    setError('');

    admin
      .customerDetails(customerId)
      .then((res) => {
        if (!isCancelled) {
          setData(res);
          setSelectedLoanAccount('all');
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          setError(err instanceof Error ? err.message : 'Could not fetch customer 360 details');
        }
      })
      .finally(() => {
        if (!isCancelled) {
          setLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [open, customerId]);

  const filteredRepayments = useMemo(() => {
    if (!data?.repayment_history) return [];
    if (selectedLoanAccount === 'all') return data.repayment_history;
    return data.repayment_history.filter(
      (item) => item.loan_account_number === selectedLoanAccount
    );
  }, [data?.repayment_history, selectedLoanAccount]);

  const profile = data?.profile;
  const summary = data?.summary;
  const loans = data?.loans || [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col p-0 gap-0 sm:rounded-2xl bg-card border-border/80 shadow-2xl">
        {/* Header Ribbon */}
        <DialogHeader className="px-6 pt-5 pb-4 border-b border-border/70 bg-muted/20 shrink-0">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <User className="h-4 w-4" />
                </span>
                <DialogTitle className="text-lg font-bold truncate">
                  {profile?.full_name || (loading ? 'Loading borrower details…' : `Customer ${customerId}`)}
                </DialogTitle>
                {profile?.kyc_verified ? (
                  <Badge variant="outline" className="border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 text-[10px] gap-1">
                    <BadgeCheck className="h-3 w-3" /> KYC Verified
                  </Badge>
                ) : (
                  <Badge variant="outline" className="border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300 text-[10px]">
                    KYC Pending
                  </Badge>
                )}
                {profile?.risk_rating && (
                  <Badge variant="secondary" className="text-[10px]">
                    Risk: {profile.risk_rating}
                  </Badge>
                )}
              </div>
              <DialogDescription className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                <span className="font-mono">ID: {customerId}</span>
                {profile?.mobile_primary && (
                  <span className="flex items-center gap-1">
                    <Phone className="h-3 w-3" /> {profile.mobile_primary}
                  </span>
                )}
                {profile?.email && (
                  <span className="flex items-center gap-1">
                    <Mail className="h-3 w-3" /> {profile.email}
                  </span>
                )}
                {profile?.address && (
                  <span className="flex items-center gap-1 truncate max-w-xs" title={profile.address}>
                    <MapPin className="h-3 w-3 shrink-0" /> {profile.address}
                  </span>
                )}
              </DialogDescription>
            </div>
            {summary && (
              <div className="text-right shrink-0">
                <div className="text-[10px] uppercase font-semibold text-muted-foreground">Collection Efficiency</div>
                <div className={`font-mono text-base font-extrabold ${summary.overall_collection_efficiency >= 95 ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'}`}>
                  {summary.overall_collection_efficiency.toFixed(1)}%
                </div>
              </div>
            )}
          </div>

          {/* Quick Metrics Bar */}
          {summary && (
            <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
              <div className="rounded-xl border bg-background/80 p-2.5">
                <div className="text-[10px] font-semibold uppercase text-muted-foreground">Sanctioned</div>
                <div className="mt-0.5 font-mono text-sm font-bold text-foreground">
                  {formatCompactMoney(summary.total_sanctioned)}
                </div>
              </div>
              <div className="rounded-xl border bg-background/80 p-2.5">
                <div className="text-[10px] font-semibold uppercase text-muted-foreground">Disbursed</div>
                <div className="mt-0.5 font-mono text-sm font-bold text-foreground">
                  {formatCompactMoney(summary.total_disbursed)}
                </div>
              </div>
              <div className="rounded-xl border bg-background/80 p-2.5">
                <div className="text-[10px] font-semibold uppercase text-muted-foreground">Principal Outstanding</div>
                <div className="mt-0.5 font-mono text-sm font-bold text-primary">
                  {formatCompactMoney(summary.principal_outstanding)}
                </div>
              </div>
              <div className={`rounded-xl border p-2.5 ${summary.total_overdue > 0 ? 'bg-destructive/10 border-destructive/30' : 'bg-background/80'}`}>
                <div className="text-[10px] font-semibold uppercase text-muted-foreground">Total Overdue</div>
                <div className={`mt-0.5 font-mono text-sm font-bold ${summary.total_overdue > 0 ? 'text-destructive' : 'text-foreground'}`}>
                  {formatCompactMoney(summary.total_overdue)}
                </div>
              </div>
            </div>
          )}
        </DialogHeader>

        {/* Content Body */}
        <div className="min-h-0 flex-1 overflow-y-auto p-6">
          {loading && (
            <div className="flex h-64 flex-col items-center justify-center text-sm text-muted-foreground">
              <RefreshCw className="h-6 w-6 animate-spin text-primary mb-2" />
              Loading customer portfolio details and repayment ledger…
            </div>
          )}

          {error && !loading && (
            <div className="flex items-center gap-2 rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {!loading && !error && data && (
            <Tabs defaultValue="repayments" className="w-full">
              <div className="flex items-center justify-between border-b pb-2 mb-4">
                <TabsList className="bg-muted/50 p-1">
                  <TabsTrigger value="repayments" className="text-xs">
                    Repayment History ({data.repayment_history.length})
                  </TabsTrigger>
                  <TabsTrigger value="loans" className="text-xs">
                    Loan Accounts ({loans.length})
                  </TabsTrigger>
                  <TabsTrigger value="profile" className="text-xs">
                    Borrower Profile & KYC
                  </TabsTrigger>
                </TabsList>
              </div>

              {/* TAB 1: Repayment History Ledger */}
              <TabsContent value="repayments" className="space-y-4 m-0">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="text-xs font-semibold text-muted-foreground">
                    Contractual due versus actual paid repayment events
                  </div>
                  {loans.length > 1 && (
                    <div className="flex items-center gap-1.5 text-xs">
                      <span className="text-muted-foreground">Account:</span>
                      <select
                        value={selectedLoanAccount}
                        onChange={(e) => setSelectedLoanAccount(e.target.value)}
                        className="rounded-lg border bg-background px-2.5 py-1 text-xs font-mono outline-none"
                      >
                        <option value="all">All Accounts ({loans.length})</option>
                        {loans.map((loan) => (
                          <option key={loan.loan_account_number} value={loan.loan_account_number}>
                            {loan.loan_account_number} — {loan.scheme_name || loan.product_name}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>

                {filteredRepayments.length === 0 ? (
                  <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
                    <Clock className="mx-auto h-8 w-8 opacity-30 mb-2" />
                    No repayment events recorded yet for this selection.
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-xl border bg-card">
                    <table className="w-full min-w-[700px] border-collapse text-left text-xs">
                      <thead className="sticky top-0 bg-muted/80 text-[10px] uppercase text-muted-foreground backdrop-blur-sm">
                        <tr>
                          <th className="p-3">Seq</th>
                          <th className="p-3">Due Date</th>
                          <th className="p-3">Loan Account</th>
                          <th className="p-3 text-right">Total Due</th>
                          <th className="p-3 text-right">Total Paid</th>
                          <th className="p-3 text-right">Shortfall</th>
                          <th className="p-3 text-right">Efficiency</th>
                          <th className="p-3 text-center">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {filteredRepayments.map((event, idx) => (
                          <tr key={`${event.loan_account_number}:${event.sequence}:${idx}`} className="hover:bg-muted/30 transition-colors">
                            <td className="p-3 font-mono font-bold text-muted-foreground">#{event.sequence}</td>
                            <td className="p-3 font-medium whitespace-nowrap">{event.repayment_date || '—'}</td>
                            <td className="p-3 font-mono text-[11px]">{event.loan_account_number}</td>
                            <td className="p-3 text-right font-mono font-medium">{formatExactMoney(event.total_due)}</td>
                            <td className="p-3 text-right font-mono font-bold text-foreground">{formatExactMoney(event.total_paid)}</td>
                            <td className={`p-3 text-right font-mono ${event.collection_shortfall > 0 ? 'text-destructive font-semibold' : 'text-muted-foreground'}`}>
                              {formatExactMoney(event.collection_shortfall)}
                            </td>
                            <td className="p-3 text-right font-mono">
                              <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${event.collection_efficiency >= 100 ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' : event.collection_efficiency > 0 ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400' : 'bg-rose-500/10 text-rose-600 dark:text-rose-400'}`}>
                                {event.collection_efficiency.toFixed(0)}%
                              </span>
                            </td>
                            <td className="p-3 text-center">
                              {event.status === 'PAID' ? (
                                <Badge variant="outline" className="border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 text-[9px] uppercase">
                                  Paid
                                </Badge>
                              ) : event.status === 'PARTIAL' ? (
                                <Badge variant="outline" className="border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300 text-[9px] uppercase">
                                  Partial
                                </Badge>
                              ) : (
                                <Badge variant="outline" className="border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300 text-[9px] uppercase">
                                  Missed
                                </Badge>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </TabsContent>

              {/* TAB 2: Loan Accounts */}
              <TabsContent value="loans" className="space-y-3 m-0">
                <div className="grid gap-3 sm:grid-cols-2">
                  {loans.map((loan) => (
                    <div
                      key={loan.loan_account_number}
                      className="rounded-xl border border-border/80 bg-background/50 p-4 transition hover:border-primary/50 shadow-sm"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="text-[10px] font-semibold uppercase text-muted-foreground">
                            {loan.product_name}
                          </div>
                          <div className="text-sm font-bold text-foreground">
                            {loan.scheme_name || 'Business Loan'}
                          </div>
                          <div className="font-mono text-[11px] text-muted-foreground mt-0.5">
                            Account: {loan.loan_account_number}
                          </div>
                        </div>
                        <Badge
                          variant={loan.active ? 'default' : 'secondary'}
                          className={`text-[9px] uppercase ${loan.is_npa ? 'bg-destructive text-destructive-foreground' : ''}`}
                        >
                          {loan.loan_status || (loan.active ? 'Active' : 'Closed')}
                        </Badge>
                      </div>

                      <div className="mt-3 grid grid-cols-2 gap-2 text-xs border-t pt-2.5">
                        <div>
                          <span className="text-muted-foreground text-[10px] block">Sanctioned</span>
                          <span className="font-mono font-semibold">{formatExactMoney(loan.sanction_amount)}</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground text-[10px] block">Outstanding</span>
                          <span className="font-mono font-bold text-primary">{formatExactMoney(loan.principal_outstanding)}</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground text-[10px] block">Tenure / EMIs</span>
                          <span className="font-medium">{loan.number_of_emis} Months</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground text-[10px] block">EMI Amount</span>
                          <span className="font-mono">{formatExactMoney(loan.emi_amount)}</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground text-[10px] block">Interest Rate</span>
                          <span className="font-medium">{loan.interest_rate}% p.a.</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground text-[10px] block">Overdue / DPD</span>
                          <span className={`font-mono ${loan.total_overdue > 0 ? 'text-destructive font-bold' : ''}`}>
                            {formatExactMoney(loan.total_overdue)} ({loan.dpd_days} DPD)
                          </span>
                        </div>
                      </div>

                      <div className="mt-2.5 flex items-center justify-between text-[10px] text-muted-foreground border-t pt-2">
                        <span>Agent: {loan.agent_name || loan.agent_code}</span>
                        <span>Sanctioned: {loan.sanction_date || '—'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </TabsContent>

              {/* TAB 3: Borrower Profile & Demographics */}
              <TabsContent value="profile" className="space-y-4 m-0">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="rounded-xl border bg-muted/10 p-4 space-y-3">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                      <User className="h-3.5 w-3.5" /> Identity & Contact
                    </h4>
                    <div className="space-y-2 text-xs">
                      <div className="flex justify-between border-b pb-1.5">
                        <span className="text-muted-foreground">Full Name</span>
                        <span className="font-semibold">{profile?.full_name || '—'}</span>
                      </div>
                      <div className="flex justify-between border-b pb-1.5">
                        <span className="text-muted-foreground">Customer ID</span>
                        <span className="font-mono">{profile?.customer_id}</span>
                      </div>
                      <div className="flex justify-between border-b pb-1.5">
                        <span className="text-muted-foreground">Primary Mobile</span>
                        <span>{profile?.mobile_primary || '—'}</span>
                      </div>
                      <div className="flex justify-between border-b pb-1.5">
                        <span className="text-muted-foreground">Email</span>
                        <span>{profile?.email || '—'}</span>
                      </div>
                      <div className="flex justify-between pb-1">
                        <span className="text-muted-foreground">Home Branch</span>
                        <span>{profile?.home_branch_name || profile?.home_branch_code || '—'}</span>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-xl border bg-muted/10 p-4 space-y-3">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                      <Shield className="h-3.5 w-3.5" /> KYC & Regulatory
                    </h4>
                    <div className="space-y-2 text-xs">
                      <div className="flex justify-between border-b pb-1.5">
                        <span className="text-muted-foreground">KYC Status</span>
                        <span className="font-semibold">{profile?.kyc_verified ? 'Verified (Y)' : 'Pending'}</span>
                      </div>
                      <div className="flex justify-between border-b pb-1.5">
                        <span className="text-muted-foreground">KYC Documents</span>
                        <span>{profile?.kyc_document_count} submitted</span>
                      </div>
                      <div className="flex justify-between border-b pb-1.5">
                        <span className="text-muted-foreground">PAN Number</span>
                        <span className="font-mono">{profile?.pan_number || '—'}</span>
                      </div>
                      <div className="flex justify-between border-b pb-1.5">
                        <span className="text-muted-foreground">Aadhaar (Masked)</span>
                        <span className="font-mono">{profile?.aadhaar_masked || '—'}</span>
                      </div>
                      <div className="flex justify-between pb-1">
                        <span className="text-muted-foreground">Risk Rating</span>
                        <Badge variant="outline" className="text-[10px]">{profile?.risk_rating || 'STANDARD'}</Badge>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-xl border bg-muted/10 p-4 space-y-3 sm:col-span-2">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                      <CircleDollarSign className="h-3.5 w-3.5" /> Income & Address Details
                    </h4>
                    <div className="grid gap-3 sm:grid-cols-2 text-xs">
                      <div>
                        <span className="text-muted-foreground text-[10px] block">Annual Income</span>
                        <span className="font-mono font-bold text-foreground text-sm">
                          {formatExactMoney(profile?.yearly_income)}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground text-[10px] block">Occupation</span>
                        <span className="font-medium text-foreground">
                          {profile?.occupation_name || profile?.occupation_type || 'Self-Employed / Business'}
                        </span>
                      </div>
                      <div className="sm:col-span-2 border-t pt-2">
                        <span className="text-muted-foreground text-[10px] block">Full Registered Address</span>
                        <span className="text-foreground leading-relaxed mt-0.5 block">
                          {profile?.address || 'No address on file'}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
