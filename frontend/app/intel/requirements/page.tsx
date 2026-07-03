'use client';

import { useState, useEffect } from 'react';
import { intel } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Briefcase, MapPin, Search, Sparkles } from 'lucide-react';

interface Requirement {
  id: number;
  position: string;
  client_name?: string;
  client_name_raw: string;
  location: string;
  skills: string;
  experience_level: string;
  status: string;
  date_posted: string;
}

export default function RequirementsPage() {
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [companyFilter, setCompanyFilter] = useState('');
  const [locationFilter, setLocationFilter] = useState('');

  const fetchRequirements = async () => {
    setLoading(true);
    try {
      const result = await intel.listRequirements({
        company: companyFilter || undefined,
        location: locationFilter || undefined,
        skills: searchQuery || undefined,
      });
      setRequirements(result.results || []);
    } catch (error) {
      console.error('Failed to fetch requirements:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRequirements();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchRequirements();
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'open':
      case 'active':
        return 'success';
      case 'closed':
        return 'destructive';
      case 'pending':
        return 'warning';
      default:
        return 'secondary';
    }
  };

  return (
    <main className="h-full overflow-auto">
      <div className="container mx-auto max-w-7xl px-4 py-8">
        <div className="dashboard-surface space-y-6 rounded-[2rem] border border-border/70 p-6 shadow-[0_24px_64px_rgba(18,28,24,0.08)] md:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-3">
              <Badge variant="outline" className="rounded-full border-border/80 bg-card/80 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                Intel
              </Badge>
              <div className="space-y-2">
                <h1 className="text-3xl font-semibold tracking-tight text-foreground md:text-4xl">Job requirements</h1>
                <p className="max-w-2xl text-sm leading-6 text-muted-foreground md:text-base">
                  Browse open positions across clients with a calmer filter surface and better scan hierarchy.
                </p>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Card className="dashboard-surface rounded-3xl border-border/70 shadow-none">
                <CardContent className="flex items-center gap-3 p-5">
                  <div className="rounded-2xl bg-accent p-2 text-accent-foreground">
                    <Briefcase className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">{requirements.length}</p>
                    <p className="text-sm text-muted-foreground">results loaded</p>
                  </div>
                </CardContent>
              </Card>
              <Card className="dashboard-surface rounded-3xl border-border/70 shadow-none">
                <CardContent className="flex items-center gap-3 p-5">
                  <div className="rounded-2xl bg-accent p-2 text-accent-foreground">
                    <Sparkles className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">Filtered search</p>
                    <p className="text-sm text-muted-foreground">skills, company, and location</p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>

          <Card className="dashboard-surface rounded-[1.75rem] border-border/70 shadow-none">
            <CardContent className="p-5">
              <form onSubmit={handleSearch} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="skills">Search by skills</Label>
                  <Input
                    id="skills"
                    type="text"
                    placeholder="e.g., Python, React"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="h-11 rounded-2xl border-border/80 bg-card/80"
                  />
                </div>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="company">Company</Label>
                    <Input
                      id="company"
                      type="text"
                      placeholder="Filter by company"
                      value={companyFilter}
                      onChange={(e) => setCompanyFilter(e.target.value)}
                      className="h-11 rounded-2xl border-border/80 bg-card/80"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="location">Location</Label>
                    <Input
                      id="location"
                      type="text"
                      placeholder="Filter by location"
                      value={locationFilter}
                      onChange={(e) => setLocationFilter(e.target.value)}
                      className="h-11 rounded-2xl border-border/80 bg-card/80"
                    />
                  </div>
                </div>
                <Button type="submit" className="w-full rounded-2xl md:w-auto">
                  <Search className="mr-2 h-4 w-4" />
                  Search
                </Button>
              </form>
            </CardContent>
          </Card>

          {loading ? (
            <div className="space-y-4">
              {Array.from({ length: 5 }).map((_, idx) => (
                <Card key={idx} className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none">
                  <CardContent className="p-6">
                    <Skeleton className="mb-2 h-6 w-64" />
                    <Skeleton className="mb-4 h-4 w-48" />
                    <Skeleton className="h-4 w-full" />
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : requirements.length === 0 ? (
            <Card className="dashboard-surface rounded-[1.75rem] border-border/70 shadow-none">
              <CardContent className="p-8 text-center">
                <p className="text-muted-foreground">No requirements found matching your criteria</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {requirements.map((req) => (
                <Card key={req.id} className="dashboard-surface rounded-[1.5rem] border-border/70 shadow-none transition-colors hover:bg-card/90">
                  <CardContent className="p-6">
                    <div className="mb-3 flex items-start justify-between gap-4">
                      <div>
                        <h3 className="text-lg font-semibold text-foreground">
                          {req.position}
                        </h3>
                        <p className="text-muted-foreground">
                          {req.client_name || req.client_name_raw}
                        </p>
                      </div>
                      <Badge variant={getStatusColor(req.status)} className="rounded-full">
                        {req.status}
                      </Badge>
                    </div>

                    <div className="mb-3 flex flex-wrap gap-4 text-sm text-muted-foreground">
                      {req.location && (
                        <span className="flex items-center gap-1">
                          <MapPin className="h-4 w-4" />
                          {req.location}
                        </span>
                      )}
                      {req.experience_level && (
                        <span className="flex items-center gap-1">
                          <Sparkles className="h-4 w-4" />
                          {req.experience_level}
                        </span>
                      )}
                      {req.date_posted && (
                        <span>{new Date(req.date_posted).toLocaleDateString()}</span>
                      )}
                    </div>

                    {req.skills && (
                      <div className="flex flex-wrap gap-2">
                        {req.skills.split(',').slice(0, 5).map((skill, idx) => (
                          <Badge key={idx} variant="outline" className="rounded-full text-xs">
                            {skill.trim()}
                          </Badge>
                        ))}
                        {req.skills.split(',').length > 5 && (
                          <Badge variant="outline" className="rounded-full text-xs">
                            +{req.skills.split(',').length - 5} more
                          </Badge>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
