'use client';

import { useState, useEffect } from 'react';
import { intel } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Search } from 'lucide-react';

interface Interview {
  id: number;
  job_role: string;
  client_name_raw: string;
  client?: { client_name: string };
  questions: string;
  interview_date: string;
  source: string;
}

export default function InterviewsPage() {
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [companyFilter, setCompanyFilter] = useState('');
  const [roleFilter, setRoleFilter] = useState('');

  const fetchInterviews = async () => {
    setLoading(true);
    try {
      const result = await intel.listInterviews({
        company: companyFilter || undefined,
        role: roleFilter || undefined,
      });
      setInterviews(result.results || []);
    } catch (error) {
      console.error('Failed to fetch interviews:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInterviews();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchInterviews();
  };

  const groupedInterviews = interviews.reduce<Record<string, Interview[]>>((acc, interview) => {
    const company = interview.client?.client_name || interview.client_name_raw || 'Unknown';
    if (!acc[company]) {
      acc[company] = [];
    }
    acc[company].push(interview);
    return acc;
  }, {});

  return (
    <main className="h-full overflow-auto container mx-auto px-4 max-w-7xl py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground">Interview Questions</h1>
        <p className="text-muted-foreground mt-2">
          Browse interview questions by company and role
        </p>
      </div>

      <Card className="mb-6">
        <CardContent className="p-4">
          <form onSubmit={handleSearch} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="search">Search questions</Label>
              <Input
                id="search"
                type="text"
                placeholder="Search questions..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="company">Company</Label>
                <Input
                  id="company"
                  type="text"
                  placeholder="Filter by company"
                  value={companyFilter}
                  onChange={(e) => setCompanyFilter(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="role">Role</Label>
                <Input
                  id="role"
                  type="text"
                  placeholder="Filter by role"
                  value={roleFilter}
                  onChange={(e) => setRoleFilter(e.target.value)}
                />
              </div>
            </div>
            <Button type="submit">
              <Search className="h-4 w-4 mr-2" />
              Search
            </Button>
          </form>
        </CardContent>
      </Card>

      {loading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, idx) => (
            <Card key={idx}>
              <CardHeader>
                <Skeleton className="h-6 w-48" />
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <Skeleton className="h-16" />
                  <Skeleton className="h-16" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : Object.keys(groupedInterviews).length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <p className="text-muted-foreground">No interview questions found matching your criteria</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {Object.entries(groupedInterviews).map(([company, companyInterviews]) => (
            <Card key={company}>
              <CardHeader className="border-b">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{company}</CardTitle>
                  <Badge variant="outline">
                    {companyInterviews.length} question{companyInterviews.length !== 1 ? 's' : ''}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <div className="divide-y">
                  {companyInterviews.map((interview) => (
                    <div key={interview.id} className="p-4 hover:bg-muted/50 transition-colors">
                      <div className="flex items-start justify-between mb-2">
                        <Badge variant="secondary">
                          {interview.job_role || 'General'}
                        </Badge>
                        {interview.interview_date && (
                          <span className="text-xs text-muted-foreground">
                            {new Date(interview.interview_date).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                      <p className="text-foreground whitespace-pre-wrap">
                        {interview.questions}
                      </p>
                      {interview.source && (
                        <p className="text-xs text-muted-foreground mt-2">
                          Source: {interview.source}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </main>
  );
}
