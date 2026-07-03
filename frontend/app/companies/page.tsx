'use client';

import { useEffect, useState } from 'react';
import { companies, auth } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowUpRight, Building2, RefreshCcw, ScanSearch, Plus } from 'lucide-react';

interface Company {
  id: string;
  name: string;
  url: string;
  status: string;
  is_processed: boolean;
  last_scraped_at: string | null;
}

const statusConfig: Record<string, { variant: 'success' | 'warning' | 'destructive' | 'secondary'; label: string }> = {
  completed: { variant: 'success', label: 'Completed' },
  processing: { variant: 'warning', label: 'Processing' },
  failed: { variant: 'destructive', label: 'Failed' },
  pending: { variant: 'secondary', label: 'Pending' },
};

export default function CompaniesPage() {
  const [companyList, setCompanyList] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [scrapingIncomplete, setScrapingIncomplete] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newCompany, setNewCompany] = useState({ name: '', url: '' });
  const [adding, setAdding] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  useEffect(() => {
    loadCompanies();
    checkAdmin();
  }, []);

  const checkAdmin = async () => {
    try {
      const user = await auth.me();
      const userRole = user.role || (user.is_staff ? 'admin' : 'standard');
      setIsAdmin(userRole === 'admin' || userRole === 'manager');
    } catch (e) {
      console.error('Failed to fetch user info', e);
      window.location.href = '/login';
    }
  };

  const loadCompanies = async () => {
    try {
      setLoading(true);
      const data = await companies.list();
      setCompanyList(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load companies');
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    try {
      setSyncing(true);
      await companies.sync();
      await loadCompanies();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to sync');
    } finally {
      setSyncing(false);
    }
  };

  const handleScrapeIncomplete = async () => {
    try {
      setScrapingIncomplete(true);
      const result = await companies.scrapeIncomplete();
      alert(result.message || 'Started scraping incomplete companies.');
      await loadCompanies();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to start batch scraping');
    } finally {
      setScrapingIncomplete(false);
    }
  };

  const handleScrape = async (id: string) => {
    try {
      const result = await companies.scrape(id);
      if (result.task_id) {
        await loadCompanies();
      } else {
        alert('Scraping started!');
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to start scraping');
    }
  };

  const handleAddCompany = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCompany.name || !newCompany.url) return;

    try {
      setAdding(true);
      const id = crypto.randomUUID ? crypto.randomUUID() : Date.now().toString();

      await companies.create({
        id,
        name: newCompany.name,
        url: newCompany.url
      });

      setNewCompany({ name: '', url: '' });
      setIsModalOpen(false);
      await loadCompanies();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to create company');
    } finally {
      setAdding(false);
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto max-w-7xl space-y-6 px-4 py-8">
        <div className="flex flex-col gap-1">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-4 w-64" />
        </div>

        <div className="flex items-center justify-between">
          <Skeleton className="h-5 w-40" />
          <div className="flex gap-2">
            <Skeleton className="h-10 w-32" />
            <Skeleton className="h-10 w-32" />
          </div>
        </div>

        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto">
      <div className="container mx-auto max-w-7xl px-4 py-8">
        <div className="dashboard-surface relative space-y-6 rounded-[2rem] border border-border/70 p-6 shadow-[0_24px_64px_rgba(18,28,24,0.08)] md:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-3">
              <Badge variant="outline" className="rounded-full border-border/80 bg-card/80 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                Operations
              </Badge>
              <div className="space-y-2">
                <h1 className="text-3xl font-semibold tracking-tight text-foreground md:text-4xl">Companies</h1>
                <p className="max-w-2xl text-sm leading-6 text-muted-foreground md:text-base">
                  Manage company ingestion, review scraping health, and trigger follow-up actions from one cleaner workspace.
                </p>
              </div>
            </div>
            <Card className="dashboard-surface min-w-[240px] rounded-3xl border-border/70 shadow-none">
              <CardContent className="p-5">
                <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">Portfolio status</p>
                <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground">{companyList.length}</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  company{companyList.length !== 1 ? 'ies' : ''} currently tracked
                </p>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-center">
            <div className="grid gap-4 md:grid-cols-3">
              <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none">
                <CardContent className="flex items-center gap-3 p-5">
                  <div className="rounded-2xl bg-accent p-2 text-accent-foreground">
                    <Building2 className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">Tracked companies</p>
                    <p className="text-sm text-muted-foreground">{companyList.length} records in the workspace</p>
                  </div>
                </CardContent>
              </Card>
              <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none">
                <CardContent className="flex items-center gap-3 p-5">
                  <div className="rounded-2xl bg-accent p-2 text-accent-foreground">
                    <ScanSearch className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">Pending review</p>
                    <p className="text-sm text-muted-foreground">
                      {companyList.filter((company) => company.status !== 'completed').length} items need attention
                    </p>
                  </div>
                </CardContent>
              </Card>
              <Card className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none">
                <CardContent className="flex items-center gap-3 p-5">
                  <div className="rounded-2xl bg-accent p-2 text-accent-foreground">
                    <RefreshCcw className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">Sync actions</p>
                    <p className="text-sm text-muted-foreground">Manual controls remain available for admins</p>
                  </div>
                </CardContent>
              </Card>
            </div>

          {isAdmin && (
            <div className="flex flex-wrap gap-2">
              <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
                <DialogTrigger asChild>
                  <Button className="rounded-2xl">
                    <Plus className="mr-2 h-4 w-4" />
                    Add Company
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Add New Company</DialogTitle>
                    <DialogDescription>
                      Enter the company details to add it to the monitoring system.
                    </DialogDescription>
                  </DialogHeader>
                  <form onSubmit={handleAddCompany}>
                    <div className="space-y-4 py-4">
                      <div className="space-y-2">
                        <Label htmlFor="name">Company Name</Label>
                        <Input
                          id="name"
                          placeholder="e.g. Acme Corp"
                          value={newCompany.name}
                          onChange={(e) => setNewCompany({ ...newCompany, name: e.target.value })}
                          required
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="url">Website URL</Label>
                        <Input
                          id="url"
                          placeholder="https://example.com"
                          type="url"
                          value={newCompany.url}
                          onChange={(e) => setNewCompany({ ...newCompany, url: e.target.value })}
                          required
                        />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button type="button" variant="outline" onClick={() => setIsModalOpen(false)}>
                        Cancel
                      </Button>
                      <Button type="submit" disabled={adding}>
                        {adding ? 'Adding...' : 'Add Company'}
                      </Button>
                    </DialogFooter>
                  </form>
                </DialogContent>
              </Dialog>
              <Button onClick={handleScrapeIncomplete} disabled={scrapingIncomplete} variant="secondary" className="rounded-2xl">
                {scrapingIncomplete ? 'Queueing...' : 'Scrape All Incomplete'}
              </Button>
              <Button onClick={handleSync} disabled={syncing} variant="outline" className="rounded-2xl bg-card/80">
                {syncing ? 'Syncing...' : 'Sync with API'}
              </Button>
            </div>
          )}
          </div>

          {error && (
            <Card className="rounded-[1.5rem] border-destructive bg-destructive/10 shadow-none">
              <CardContent className="pt-6">
                <p className="text-destructive">{error}</p>
              </CardContent>
            </Card>
          )}

          <Card className="dashboard-surface overflow-hidden rounded-[1.75rem] border-border/70 shadow-none">
            <CardHeader className="border-b border-border/70">
              <CardTitle className="font-serif text-xl font-semibold">Company list</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow className="border-border/70">
                    <TableHead>Name</TableHead>
                    <TableHead>URL</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Last Scraped</TableHead>
                    {isAdmin && <TableHead className="text-right">Actions</TableHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {companyList.map((company) => (
                    <TableRow key={company.id} className="border-border/70">
                      <TableCell className="font-medium">{company.name}</TableCell>
                      <TableCell>
                        <a
                          href={company.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground hover:underline"
                        >
                          <span className="max-w-[280px] truncate">{company.url}</span>
                          <ArrowUpRight className="h-3.5 w-3.5" />
                        </a>
                      </TableCell>
                      <TableCell>
                        <Badge variant={statusConfig[company.status]?.variant || 'secondary'} className="rounded-full">
                          {statusConfig[company.status]?.label || company.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {company.last_scraped_at
                          ? new Date(company.last_scraped_at).toLocaleString()
                          : 'Never'}
                      </TableCell>
                      {isAdmin && (
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="rounded-xl"
                            onClick={() => handleScrape(company.id)}
                            disabled={company.status === 'processing'}
                          >
                            {company.status === 'processing' ? 'Processing...' : 'Scrape'}
                          </Button>
                        </TableCell>
                      )}
                    </TableRow>
                  ))}
                  {companyList.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={isAdmin ? 5 : 4} className="py-12 text-center text-muted-foreground">
                        No companies found. {isAdmin && 'Add one to get started.'}
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
