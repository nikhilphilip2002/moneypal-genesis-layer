'use client';

import { useState, useEffect } from 'react';
import { intel, auth } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import {
  BarChart3,
  RefreshCw,
  Clock,
  User,
  Search,
} from 'lucide-react';

interface SearchRecord {
  id: number;
  query_text: string;
  query_type: string;
  company_searched: string;
  created_at: string;
  user: { username: string } | null;
}

interface TopIntent {
  intent: string;
  count: number;
}

interface AdminStats {
  clients: { total: number; active: number };
  requirements: { total: number; open: number };
  interviews: { total: number };
  searches?: { total: number; today: number };
  top_intents?: TopIntent[];
}

export default function AdminPage() {
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [history, setHistory] = useState<SearchRecord[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [syncLoading, setSyncLoading] = useState(false);
  const [daysFilter, setDaysFilter] = useState('7');

  useEffect(() => {
    // Check admin status
    auth.me()
      .then((user) => {
        const userRole = user.role || (user.is_staff ? 'admin' : 'standard');
        setIsAdmin(userRole === 'admin' || userRole === 'manager');
        if (userRole !== 'standard') {
          loadData();
        }
      })
      .catch(() => setIsAdmin(false))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadData = async () => {
    try {
      const [statsData, historyData] = await Promise.all([
        intel.stats(),
        intel.getHistory({ days: parseInt(daysFilter) }),
      ]);
      setStats(statsData);
      setHistory(historyData.results || []);
    } catch (error) {
      console.error('Failed to load admin data:', error);
    }
  };

  const handleSync = async (syncType: 'all' | 'clients' | 'requirements' | 'interviews') => {
    setSyncLoading(true);
    try {
      const result = await intel.triggerSync(syncType);
      alert(`Sync started! Task ID: ${result.task_id}`);
    } catch (error) {
      alert(`Sync failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setSyncLoading(false);
    }
  };

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const data = await intel.getHistory({ days: parseInt(daysFilter) });
      setHistory(data.results || []);
    } catch (error) {
      console.error('Failed to load history:', error);
    } finally {
      setHistoryLoading(false);
    }
  };

  if (loading) {
    return (
      <main className="h-full overflow-auto container mx-auto px-4 max-w-7xl py-8">
        <div className="space-y-6">
          <Skeleton className="h-10 w-64" />
          <div className="grid grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, idx) => (
              <Skeleton key={idx} className="h-32" />
            ))}
          </div>
        </div>
      </main>
    );
  }

  if (!isAdmin) {
    return (
      <main className="h-full overflow-auto container mx-auto px-4 max-w-7xl py-8">
        <Card>
          <CardContent className="p-8 text-center">
            <h2 className="text-xl font-semibold text-foreground mb-2">Access Denied</h2>
            <p className="text-muted-foreground">
              This page is only accessible to administrators.
            </p>
          </CardContent>
        </Card>
      </main>
    );
  }

  return (
    <main className="container mx-auto px-4 max-w-7xl py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground">Intel Admin</h1>
        <p className="text-muted-foreground mt-2">
          Search analytics, data sync, and system management
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <BarChart3 className="h-8 w-8 text-blue-600" />
              <div>
                <p className="text-2xl font-bold text-foreground">{stats?.searches?.total || 0}</p>
                <p className="text-sm text-muted-foreground">Total Searches</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <Clock className="h-8 w-8 text-green-600" />
              <div>
                <p className="text-2xl font-bold text-foreground">{stats?.searches?.today || 0}</p>
                <p className="text-sm text-muted-foreground">Today</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <Search className="h-8 w-8 text-purple-600" />
              <div>
                <p className="text-2xl font-bold text-foreground">{stats?.requirements?.open || 0}</p>
                <p className="text-sm text-muted-foreground">Open Requirements</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <User className="h-8 w-8 text-orange-600" />
              <div>
                <p className="text-2xl font-bold text-foreground">{stats?.clients?.active || 0}</p>
                <p className="text-sm text-muted-foreground">Active Clients</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <RefreshCw className="h-5 w-5" />
              Data Sync
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button
              className="w-full"
              onClick={() => handleSync('all')}
              disabled={syncLoading}
            >
              {syncLoading ? 'Syncing...' : 'Sync All Data'}
            </Button>
            <div className="grid grid-cols-2 gap-2">
              <Button
                variant="outline"
                onClick={() => handleSync('clients')}
                disabled={syncLoading}
              >
                Clients
              </Button>
              <Button
                variant="outline"
                onClick={() => handleSync('requirements')}
                disabled={syncLoading}
              >
                Requirements
              </Button>
            </div>
            <Button
              variant="outline"
              className="w-full"
              onClick={() => handleSync('interviews')}
              disabled={syncLoading}
            >
              Interviews
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Top Search Intents</CardTitle>
          </CardHeader>
          <CardContent>
            {stats?.top_intents && stats.top_intents.length > 0 ? (
              <div className="space-y-3">
                {stats.top_intents.map((item, idx) => (
                  <div key={idx} className="flex items-center justify-between">
                    <span className="text-foreground capitalize">{item.intent}</span>
                    <Badge variant="outline">{item.count}</Badge>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-center py-4">No search data yet</p>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-1">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="text-lg">Recent Searches</CardTitle>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                value={daysFilter}
                onChange={(e) => setDaysFilter(e.target.value)}
                className="w-20 h-8 text-sm"
                min="1"
                max="30"
              />
              <Button size="sm" onClick={loadHistory} disabled={historyLoading}>
                Filter
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {history.length === 0 ? (
              <p className="text-muted-foreground text-center py-4">No searches found</p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {history.slice(0, 10).map((record) => (
                  <div
                    key={record.id}
                    className="p-2 bg-muted rounded text-sm"
                  >
                    <p className="font-medium text-foreground truncate">
                      {record.query_text}
                    </p>
                    <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                      <Badge variant="outline" className="text-xs">
                        {record.query_type}
                      </Badge>
                      {record.company_searched && (
                        <span>@ {record.company_searched}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
