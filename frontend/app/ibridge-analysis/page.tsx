'use client';

import { useEffect, useRef, useState } from 'react';
import { auth, ibridge } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import { WordCloud } from '@/components/WordCloud';
import type { WordCloudItem } from '@/components/WordCloud';
import { AlertTriangle, Check, ChevronDown, ChevronsUpDown, Database, FileSearch, Lightbulb, Users, X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface IBridgeStats {
  total_records: number;
  unique_users: number;
  unique_databases: number;
  distinct_questions: number;
}

interface IBridgeUserOption {
  username: string;
  display_name?: string;
  attempt_count: number;
}

interface IBridgeDatabaseOption {
  databasename: string;
  attempt_count: number;
  question_count: number;
}

interface IBridgeQuestionSummary {
  question: string;
  total_attempts: number;
  distinct_queries: number;
  repeated_query_attempts: number;
  solved: boolean;
  best_score: number;
  best_verdict: string;
  exception_attempts: number;
  dominant_exception_family: string;
  dominant_exception_code: string;
  insight: string;
  knowledge_gaps: string[];
}

interface IBridgeExceptionPattern {
  family: string;
  code: string;
  count: number;
  sample: string;
}

interface IBridgeKnowledgeGap {
  area: string;
  count: number;
  reason: string;
}

interface IBridgeLlmSummary {
  executive_summary: string;
  behavior_patterns: string[];
  knowledge_gaps: string[];
  recommendations: string[];
}

interface IBridgeTrendSummary {
  direction: string;
  summary: string;
}

interface IBridgeSkillAreaSummary {
  area: string;
  question_count: number;
  attempt_count: number;
  solved_count: number;
  unsolved_count: number;
  avg_best_score: number;
  exception_attempts: number;
  top_signal: string;
}

interface IBridgeHardestQuestion {
  question: string;
  severity_score: number;
  best_score: number;
  attempts: number;
  solved: boolean;
  dominant_exception_family: string;
}

interface IBridgePriorityAction {
  priority: number;
  area: string;
  why: string;
  recommended_practice: string;
}

interface IBridgeReport {
  username: string;
  databasename: string;
  total_attempts: number;
  total_questions: number;
  total_distinct_queries: number;
  repeated_question_attempts: number;
  questions_retried: number;
  repeated_query_attempts: number;
  solved_questions: number;
  unsolved_questions: number;
  exception_attempts: number;
  exception_rate: number;
  readiness_score: number;
  strengths: string[];
  top_risks: string[];
  trend_summary: IBridgeTrendSummary;
  skill_area_summary: IBridgeSkillAreaSummary[];
  hardest_questions: IBridgeHardestQuestion[];
  priority_actions: IBridgePriorityAction[];
  question_summaries: IBridgeQuestionSummary[];
  exception_patterns: IBridgeExceptionPattern[];
  knowledge_gaps: IBridgeKnowledgeGap[];
  llm_summary: IBridgeLlmSummary | null;
}

interface IBridgeAttempt {
  id: number;
  user_query: string;
  normalized_query: string;
  result_text: string;
  correct_query: string | null;
  exception_string: string | null;
  exception_family: string;
  exception_code: string;
  score: number;
  verdict: string;
  similarity: number;
  created_at: string | null;
}

interface IBridgeQuestionDetail {
  question: string;
  attempts: IBridgeAttempt[];
}

function verdictBadge(verdict: string, score: number) {
  if (verdict === 'correct') {
    return <Badge variant="success">Correct {score}</Badge>;
  }
  if (verdict === 'partially_correct') {
    return <Badge variant="warning">Partial {score}</Badge>;
  }
  return <Badge variant="destructive">Incorrect {score}</Badge>;
}

function formatLabel(value: string) {
  return value.replace(/_/g, ' ');
}

function readinessVariant(score: number) {
  if (score >= 80) return 'success';
  if (score >= 60) return 'warning';
  return 'destructive';
}

const TRACK_OPTIONS = [
  { value: 'sql',        label: 'SQL / RDBMS' },
  { value: 'mysql',      label: 'MySQL' },
  { value: 'python',     label: 'Python' },
  { value: 'java',       label: 'Java' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'csharp',     label: 'C#' },
  { value: 'c',          label: 'C' },
  { value: 'linux',      label: 'Linux' },
  { value: 'html',       label: 'HTML & CSS' },
];

export default function IBridgeAnalysisPage() {
  const [role, setRole] = useState<string>('standard');
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<IBridgeStats | null>(null);
  const [users, setUsers] = useState<IBridgeUserOption[]>([]);
  const [databases, setDatabases] = useState<IBridgeDatabaseOption[]>([]);
  const [report, setReport] = useState<IBridgeReport | null>(null);
  const [questionDetail, setQuestionDetail] = useState<IBridgeQuestionDetail | null>(null);
  const [selectedTrack, setSelectedTrack] = useState('sql');
  const [selectedUser, setSelectedUser] = useState('');
  const [userComboOpen, setUserComboOpen] = useState(false);
  const [selectedDatabase, setSelectedDatabase] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [usersLoading, setUsersLoading] = useState(false);
  const [databasesLoading, setDatabasesLoading] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [kgOpen, setKgOpen] = useState(true);
  const [epOpen, setEpOpen] = useState(true);
  const [wordFilter, setWordFilter] = useState<{ type: 'gap' | 'exception'; label: string } | null>(null);
  const questionTableRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    auth.me()
      .then(async (user) => {
        const userRole = user.role || (user.is_staff ? 'admin' : 'standard');
        setRole(userRole);
        const isPrivileged = userRole === 'admin' || userRole === 'manager';
        await Promise.all([
          loadStats(selectedTrack),
          isPrivileged ? loadUsers(selectedTrack) : Promise.resolve(),
          loadDatabases(isPrivileged ? '' : undefined, selectedTrack),
        ]);
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : 'Failed to load iBridge analysis');
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadStats = async (track: string) => {
    const response = await ibridge.stats(track);
    setStats(response);
  };

  const loadUsers = async (track: string) => {
    try {
      setUsersLoading(true);
      const response = await ibridge.users(track);
      setUsers(response.results || []);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load users');
    } finally {
      setUsersLoading(false);
    }
  };

  const loadDatabases = async (user?: string, track?: string) => {
    try {
      setDatabasesLoading(true);
      const response = await ibridge.databases(user, track ?? selectedTrack);
      const nextDatabases = response.results || [];
      setDatabases(nextDatabases);
      if (nextDatabases.length === 1) {
        setSelectedDatabase(nextDatabases[0].databasename);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load databases');
    } finally {
      setDatabasesLoading(false);
    }
  };

  const loadReport = async (database: string, user?: string, track?: string) => {
    try {
      setReportLoading(true);
      setQuestionDetail(null);
      const response = await ibridge.report({ user, database, track: track ?? selectedTrack });
      setReport(response);
      setError(null);
    } catch (loadError) {
      setReport(null);
      setQuestionDetail(null);
      setError(loadError instanceof Error ? loadError.message : 'Failed to load report');
    } finally {
      setReportLoading(false);
    }
  };

  const loadQuestionDetail = async (question: string) => {
    try {
      setDetailLoading(true);
      const response = await ibridge.questionDetail({
        user: role === 'standard' ? undefined : selectedUser,
        database: selectedDatabase,
        question,
        track: selectedTrack,
      });
      setQuestionDetail(response);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load question detail');
    } finally {
      setDetailLoading(false);
    }
  };

  // When track changes: reset all selections and reload
  useEffect(() => {
    setSelectedUser('');
    setSelectedDatabase('');
    setReport(null);
    setQuestionDetail(null);
    setDatabases([]);
    const isPrivileged = role === 'admin' || role === 'manager';
    void Promise.all([
      loadStats(selectedTrack),
      isPrivileged ? loadUsers(selectedTrack) : loadDatabases(undefined, selectedTrack),
    ]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTrack]);

  useEffect(() => {
    if (role === 'standard') {
      void loadDatabases(undefined, selectedTrack);
      return;
    }

    setSelectedDatabase('');
    setReport(null);
    setQuestionDetail(null);
    if (selectedUser) {
      void loadDatabases(selectedUser, selectedTrack);
    } else {
      setDatabases([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedUser, role]);

  useEffect(() => {
    if (!selectedDatabase) {
      return;
    }
    void loadReport(selectedDatabase, role === 'standard' ? undefined : selectedUser, selectedTrack);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDatabase]);

  if (loading) {
    return (
      <main className="h-full overflow-auto container mx-auto px-3 py-4 md:px-4 md:py-8 max-w-7xl">
        <div className="space-y-6">
          <Skeleton className="h-10 w-72" />
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, idx) => (
              <Skeleton key={idx} className="h-28" />
            ))}
          </div>
          <Skeleton className="h-[480px] w-full" />
        </div>
      </main>
    );
  }

  return (
    <main className="h-full overflow-auto container mx-auto px-3 py-4 md:px-4 md:py-8 max-w-7xl">
      <div className="space-y-6">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl md:text-3xl font-bold text-foreground">iBridge Analysis</h1>
          <p className="text-sm md:text-base text-muted-foreground">
            Select a technology, then a user and database or module to generate an analysis report
            covering attempts, exceptions, knowledge gaps, and coaching actions.
          </p>
        </div>

        {error && (
          <Card className="border-destructive/40">
            <CardContent className="p-4 text-sm text-destructive">{error}</CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-5 flex items-center gap-3">
              <FileSearch className="h-8 w-8 text-sky-600" />
              <div>
                <p className="text-2xl font-bold">{stats?.total_records ?? 0}</p>
                <p className="text-sm text-muted-foreground">Attempts</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-5 flex items-center gap-3">
              <Users className="h-8 w-8 text-emerald-600" />
              <div>
                <p className="text-2xl font-bold">{stats?.unique_users ?? 0}</p>
                <p className="text-sm text-muted-foreground">Users</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-5 flex items-center gap-3">
              <Database className="h-8 w-8 text-violet-600" />
              <div>
                <p className="text-2xl font-bold">{stats?.unique_databases ?? 0}</p>
                <p className="text-sm text-muted-foreground">Databases</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-5 flex items-center gap-3">
              <Lightbulb className="h-8 w-8 text-amber-600" />
              <div>
                <p className="text-2xl font-bold">{stats?.distinct_questions ?? 0}</p>
                <p className="text-sm text-muted-foreground">Distinct Questions</p>
              </div>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-xl">Report Selection</CardTitle>
            <CardDescription>
              {role === 'standard'
                ? 'Choose one database from your own attempt history.'
                : 'Search for a user, choose the matching user record, then select one of their attempted databases.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <Select
              value={selectedTrack}
              onValueChange={(value) => setSelectedTrack(value)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select technology" />
              </SelectTrigger>
              <SelectContent>
                {TRACK_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {role === 'admin' || role === 'manager' ? (
              <Popover open={userComboOpen} onOpenChange={setUserComboOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={userComboOpen}
                    className="w-full justify-between font-normal"
                  >
                    {usersLoading
                      ? 'Loading users...'
                      : selectedUser
                        ? (users.find((u) => u.username === selectedUser)?.display_name || selectedUser)
                        : 'Select user...'}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
                  <Command>
                    <CommandInput placeholder="Search users..." />
                    <CommandList>
                      <CommandEmpty>No user found.</CommandEmpty>
                      <CommandGroup>
                        {users.map((user) => (
                          <CommandItem
                            key={user.username}
                            value={user.display_name || user.username}
                            onSelect={() => {
                              setSelectedUser(selectedUser === user.username ? '' : user.username);
                              setUserComboOpen(false);
                            }}
                          >
                            <Check
                              className={cn(
                                'mr-2 h-4 w-4',
                                selectedUser === user.username ? 'opacity-100' : 'opacity-0'
                              )}
                            />
                            <span className="flex-1">{user.display_name || user.username}</span>
                            <Badge variant="outline" className="ml-2 text-xs">
                              {user.attempt_count}
                            </Badge>
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            ) : null}

            <Select
              value={selectedDatabase || 'none'}
              onValueChange={(value) => setSelectedDatabase(value === 'none' ? '' : value)}
              disabled={databasesLoading || ((role === 'admin' || role === 'manager') && !selectedUser)}
            >
              <SelectTrigger>
                <SelectValue placeholder={
                  databasesLoading
                    ? 'Loading...'
                    : ['sql', 'mysql', 'rdbms'].includes(selectedTrack)
                      ? 'Select database'
                      : 'Select module'
                } />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">
                  {['sql', 'mysql', 'rdbms'].includes(selectedTrack) ? 'Select database' : 'Select module'}
                </SelectItem>
                {databases.map((database) => (
                  <SelectItem key={database.databasename} value={database.databasename}>
                    {database.databasename} ({database.attempt_count} attempts)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        {reportLoading ? (
          <Card>
            <CardContent className="p-6 space-y-3">
              <Skeleton className="h-8 w-48" />
              <Skeleton className="h-32 w-full" />
              <Skeleton className="h-56 w-full" />
            </CardContent>
          </Card>
        ) : report ? (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
              <Card>
                <CardContent className="p-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-2xl font-bold">{report.readiness_score}</p>
                      <p className="text-sm text-muted-foreground">Readiness Score</p>
                    </div>
                    <Badge variant={readinessVariant(report.readiness_score)}>
                      {formatLabel(report.trend_summary.direction)}
                    </Badge>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-5">
                  <p className="text-2xl font-bold">{report.total_questions}</p>
                  <p className="text-sm text-muted-foreground">Questions</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-5">
                  <p className="text-2xl font-bold">{report.questions_retried}</p>
                  <p className="text-sm text-muted-foreground">Questions Retried</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-5">
                  <p className="text-2xl font-bold">{report.repeated_query_attempts}</p>
                  <p className="text-sm text-muted-foreground">Repeated Queries</p>
                </CardContent>
              </Card>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
              <Card className="xl:col-span-2">
                <CardHeader>
                  <CardTitle className="text-xl">
                    {report.username} on {report.databasename}
                  </CardTitle>
                  <CardDescription>
                    {report.solved_questions} solved, {report.unsolved_questions} unsolved, {report.exception_attempts} attempts with exceptions.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="rounded-md border bg-muted/30 p-4 space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">{formatLabel(report.trend_summary.direction)}</Badge>
                      <Badge variant="secondary">
                        Exception Rate {(report.exception_rate * 100).toFixed(1)}%
                      </Badge>
                    </div>
                    <p className="text-sm">
                      {report.llm_summary?.executive_summary || report.trend_summary.summary}
                    </p>
                    {report.llm_summary?.behavior_patterns?.length ? (
                      <div className="flex flex-wrap gap-2">
                        {report.llm_summary.behavior_patterns.map((pattern) => (
                          <Badge key={pattern} variant="outline">{pattern}</Badge>
                        ))}
                      </div>
                    ) : null}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base">Strengths</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-2">
                        {report.strengths.length ? report.strengths.map((strength) => (
                          <div key={strength} className="rounded-md border p-3 text-sm">
                            {strength}
                          </div>
                        )) : (
                          <p className="text-sm text-muted-foreground">No clear strengths detected yet.</p>
                        )}
                      </CardContent>
                    </Card>
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base">Top Risks</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-2">
                        {report.top_risks.length ? report.top_risks.map((risk) => (
                          <div key={risk} className="rounded-md border border-destructive/20 bg-destructive/5 p-3 text-sm">
                            {risk}
                          </div>
                        )) : (
                          <p className="text-sm text-muted-foreground">No major risks detected.</p>
                        )}
                      </CardContent>
                    </Card>
                  </div>

                  <div className="space-y-4">
                    <Card>
                      <CardHeader
                        className="pb-3 flex flex-row items-center justify-between cursor-pointer select-none"
                        onClick={() => setKgOpen((v) => !v)}
                      >
                        <CardTitle className="text-lg">Knowledge Gaps</CardTitle>
                        <ChevronDown className={cn('h-5 w-5 text-muted-foreground transition-transform duration-200', !kgOpen && '-rotate-90')} />
                      </CardHeader>
                      {kgOpen && (
                        <CardContent>
                          <WordCloud
                            items={report.knowledge_gaps.map((g) => ({
                              label: formatLabel(g.area),
                              value: g.count,
                              tooltip: g.reason,
                            }))}
                            palette="cool"
                            emptyMessage="No strong deterministic knowledge-gap signal found."
                            onWordClick={(item: WordCloudItem) => {
                              setWordFilter((prev) =>
                                prev?.type === 'gap' && prev.label === item.label
                                  ? null
                                  : { type: 'gap', label: item.label }
                              );
                              questionTableRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                            }}
                          />
                        </CardContent>
                      )}
                    </Card>

                    <Card>
                      <CardHeader
                        className="pb-3 flex flex-row items-center justify-between cursor-pointer select-none"
                        onClick={() => setEpOpen((v) => !v)}
                      >
                        <CardTitle className="text-lg">Exception Patterns</CardTitle>
                        <ChevronDown className={cn('h-5 w-5 text-muted-foreground transition-transform duration-200', !epOpen && '-rotate-90')} />
                      </CardHeader>
                      {epOpen && (
                        <CardContent>
                          <WordCloud
                            items={report.exception_patterns.map((p) => ({
                              label: formatLabel(p.family),
                              value: p.count,
                              tooltip: p.sample,
                              code: p.code,
                            }))}
                            palette="warm"
                            emptyMessage="No exceptions were recorded for this user and database."
                            onWordClick={(item: WordCloudItem) => {
                              setWordFilter((prev) =>
                                prev?.type === 'exception' && prev.label === item.label
                                  ? null
                                  : { type: 'exception', label: item.label }
                              );
                              questionTableRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                            }}
                          />
                        </CardContent>
                      )}
                    </Card>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-xl">Action Plan</CardTitle>
                  <CardDescription>Prioritized coaching actions derived from report signals.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {report.priority_actions.length ? report.priority_actions.map((action) => (
                    <div key={`${action.priority}-${action.area}`} className="rounded-md border p-3 text-sm space-y-2">
                      <div className="flex items-center justify-between gap-2">
                        <Badge variant="secondary">Priority {action.priority}</Badge>
                        <Badge variant="outline">{formatLabel(action.area)}</Badge>
                      </div>
                      <p>{action.why}</p>
                      <p className="text-muted-foreground">{action.recommended_practice}</p>
                    </div>
                  )) : (
                    <p className="text-sm text-muted-foreground">No priority actions available yet.</p>
                  )}
                  {report.llm_summary?.recommendations?.length ? (
                    <div className="space-y-2 pt-2">
                      <h3 className="font-semibold text-sm">LLM Recommendations</h3>
                      {report.llm_summary.recommendations.map((recommendation) => (
                        <div key={recommendation} className="rounded-md border p-3 text-sm">
                          {recommendation}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-xl">Skill Area Summary</CardTitle>
                  <CardDescription>Grouped by deterministic SQL learning areas.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {report.skill_area_summary.map((skill) => (
                    <div key={skill.area} className="rounded-md border p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="font-semibold">{formatLabel(skill.area)}</div>
                        <div className="flex flex-wrap gap-2">
                          <Badge variant="secondary">{skill.avg_best_score.toFixed(1)} avg score</Badge>
                          <Badge variant={skill.unsolved_count > 0 ? 'warning' : 'success'}>
                            {skill.solved_count}/{skill.question_count} solved
                          </Badge>
                        </div>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                        <span>{skill.attempt_count} attempts</span>
                        <span>{skill.exception_attempts} exceptions</span>
                        {skill.top_signal && <span>Top signal: {formatLabel(skill.top_signal)}</span>}
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-xl">Hardest Questions</CardTitle>
                  <CardDescription>Highest coaching priority based on retries, score, and exceptions.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {report.hardest_questions.map((question) => (
                    <div key={question.question} className="rounded-md border p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="font-medium">{question.question}</div>
                          <div className="mt-2 flex flex-wrap gap-2">
                            <Badge variant="outline">Severity {question.severity_score}</Badge>
                            <Badge variant={question.solved ? 'success' : 'destructive'}>
                              {question.solved ? 'Solved' : 'Unsolved'}
                            </Badge>
                          </div>
                        </div>
                        <div className="text-right text-xs text-muted-foreground">
                          <div>{question.attempts} attempts</div>
                          <div>Best score {question.best_score}</div>
                        </div>
                      </div>
                      {question.dominant_exception_family && (
                        <div className="mt-2 text-xs text-muted-foreground">
                          Dominant failure: {formatLabel(question.dominant_exception_family)}
                        </div>
                      )}
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>

            <Card ref={questionTableRef}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-xl">Question Summary</CardTitle>
                    <CardDescription>
                      Click a question row to inspect the full attempt history and repeated query patterns.
                    </CardDescription>
                  </div>
                  {wordFilter && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-1.5"
                      onClick={() => setWordFilter(null)}
                    >
                      Filtered by: <Badge variant="secondary">{wordFilter.label}</Badge>
                      <X className="h-3 w-3" />
                    </Button>
                  )}
                </div>
              </CardHeader>
              <CardContent className="px-2 md:px-6">
                <div className="-mx-2 md:mx-0 overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Question</TableHead>
                      <TableHead>Attempts</TableHead>
                      <TableHead>Distinct Queries</TableHead>
                      <TableHead>Repeated Queries</TableHead>
                      <TableHead>Best Attempt</TableHead>
                      <TableHead>Exceptions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {report.question_summaries
                      .filter((summary) => {
                        if (!wordFilter) return true;
                        if (wordFilter.type === 'gap') {
                          return summary.knowledge_gaps.some(
                            (g) => formatLabel(g) === wordFilter.label
                          );
                        }
                        return formatLabel(summary.dominant_exception_family) === wordFilter.label;
                      })
                      .map((summary) => (
                        <TableRow
                          key={summary.question}
                          className="cursor-pointer"
                          onClick={() => void loadQuestionDetail(summary.question)}
                        >
                          <TableCell className="max-w-[560px]">
                            <div className="font-medium">{summary.question}</div>
                            <div className="text-xs text-muted-foreground mt-1">{summary.insight}</div>
                          </TableCell>
                          <TableCell>{summary.total_attempts}</TableCell>
                          <TableCell>{summary.distinct_queries}</TableCell>
                          <TableCell>{summary.repeated_query_attempts}</TableCell>
                          <TableCell>{verdictBadge(summary.best_verdict, summary.best_score)}</TableCell>
                          <TableCell>
                            {summary.exception_attempts > 0 ? (
                              <Badge variant="outline">
                                {summary.dominant_exception_code || formatLabel(summary.dominant_exception_family)}
                              </Badge>
                            ) : (
                              <Badge variant="success">No exceptions</Badge>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-xl">
                  {questionDetail ? `Question Detail: ${questionDetail.question}` : 'Question Detail'}
                </CardTitle>
                <CardDescription>
                  {questionDetail ? 'Normalized queries help identify when the same SQL was submitted repeatedly.' : 'Select a question above to inspect the attempt history.'}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {detailLoading ? (
                  <div className="space-y-3">
                    <Skeleton className="h-8 w-full" />
                    <Skeleton className="h-40 w-full" />
                  </div>
                ) : !questionDetail ? (
                  <p className="text-sm text-muted-foreground">No question selected.</p>
                ) : (
                  <div className="space-y-4">
                    {questionDetail.attempts.map((attempt) => (
                      <div key={attempt.id} className="rounded-md border p-4 space-y-3">
                        <div className="flex flex-wrap items-center gap-2">
                          {verdictBadge(attempt.verdict, attempt.score)}
                          <Badge variant="outline">Similarity {(attempt.similarity * 100).toFixed(1)}%</Badge>
                          {attempt.exception_family ? (
                            <Badge variant="destructive">
                              <AlertTriangle className="h-3 w-3 mr-1" />
                              {attempt.exception_code || formatLabel(attempt.exception_family)}
                            </Badge>
                          ) : (
                            <Badge variant="success">Executed</Badge>
                          )}
                        </div>
                        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                          <div>
                            <h3 className="font-semibold mb-2">User Query</h3>
                            <pre className="rounded-md bg-muted/30 border p-3 text-xs whitespace-pre-wrap overflow-x-auto">
                              {attempt.user_query || '(empty)'}
                            </pre>
                          </div>
                          <div>
                            <h3 className="font-semibold mb-2">Correct Query</h3>
                            <pre className="rounded-md bg-muted/30 border p-3 text-xs whitespace-pre-wrap overflow-x-auto">
                              {attempt.correct_query || 'No reference query available.'}
                            </pre>
                          </div>
                        </div>
                        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                          <div>
                            <h3 className="font-semibold mb-2">Normalized Query</h3>
                            <div className="rounded-md border p-3 text-xs break-all">{attempt.normalized_query || '(empty)'}</div>
                          </div>
                          <div>
                            <h3 className="font-semibold mb-2">Exception</h3>
                            <div className="rounded-md border p-3 text-xs whitespace-pre-wrap">
                              {attempt.exception_string || 'No exception captured.'}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </>
        ) : (
          <Card>
            <CardContent className="p-6 text-sm text-muted-foreground">
              Select a database to generate the analytics report.
            </CardContent>
          </Card>
        )}
      </div>
    </main>
  );
}
