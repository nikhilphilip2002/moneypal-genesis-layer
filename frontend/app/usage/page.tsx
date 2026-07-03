'use client';

import { useEffect, useState } from 'react';
import { usage, auth } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton';

interface UsageStats {
  tokens_1m: number;
  tokens_1h: number;
  tokens_24h: number;
  req_1m: number;
  req_1h: number;
  req_24h: number;
}

interface LogEntry {
  timestamp: string;
  model: string;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  requests: number;
}

const timeFrames = [
  { key: 'tokens_1m', label: 'Tokens (1 min)', reqKey: 'req_1m' },
  { key: 'tokens_1h', label: 'Tokens (1 hour)', reqKey: 'req_1h' },
  { key: 'tokens_24h', label: 'Tokens (24 hours)', reqKey: 'req_24h' },
];

export default function UsagePage() {
  const [stats, setStats] = useState<UsageStats | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [authorized, setAuthorized] = useState(false);
  const [authChecking, setAuthChecking] = useState(true);
  const router = useRouter();

  useEffect(() => {
    checkPermission();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const checkPermission = async () => {
    try {
      const user = await auth.me();
      const userRole = user.role || (user.is_staff ? 'admin' : 'standard');
      if (userRole === 'standard') {
        router.push('/');
      } else {
        setAuthorized(true);
        loadData();
      }
    } catch (e) {
      router.push('/login');
    } finally {
      setAuthChecking(false);
    }
  };

  const loadData = async () => {
    try {
      setLoading(true);
      const [statsData, logsData] = await Promise.all([
        usage.stats(),
        usage.logs(10),
      ]);
      setStats(statsData);
      setLogs(logsData.logs || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load usage data');
    } finally {
      setLoading(false);
    }
  };

  if (authChecking) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col gap-1">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-4 w-64" />
        </div>
      </div>
    );
  }

  if (!authorized) return null;

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col gap-1">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-4 w-64" />
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-32" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-16" />
                <Skeleton className="h-4 w-24 mt-2" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto container mx-auto px-4 py-8 max-w-7xl">
      <div className="space-y-8">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold text-foreground">API Usage</h1>
          <p className="text-muted-foreground">Monitor your API usage statistics</p>
        </div>

        {error && (
          <Card className="border-destructive bg-destructive/10">
            <CardContent className="pt-6">
              <p className="text-destructive">{error}</p>
            </CardContent>
          </Card>
        )}

        <div className="grid gap-4 md:grid-cols-3">
          {timeFrames.map((frame) => (
            <Card key={frame.key}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {frame.label}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-foreground">
                  {stats?.[frame.key as keyof UsageStats]?.toLocaleString() || 0}
                </div>
                <p className="text-sm text-muted-foreground mt-1">
                  {stats?.[frame.reqKey as keyof UsageStats] || 0} requests
                </p>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="space-y-4">
          <h2 className="text-xl font-semibold text-foreground">Recent Activity (Last 10 Requests)</h2>
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>Model</TableHead>
                    <TableHead>Total Tokens</TableHead>
                    <TableHead>Prompt</TableHead>
                    <TableHead>Completion</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logs.length > 0 ? (
                    logs.map((log, index) => (
                      <TableRow key={index}>
                        <TableCell className="text-muted-foreground">
                          {new Date(log.timestamp).toLocaleString()}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="font-mono text-xs">
                            {log.model}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-medium text-foreground">
                          {log.total_tokens}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {log.prompt_tokens}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {log.completion_tokens}
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                        No recent activity logs found.
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
