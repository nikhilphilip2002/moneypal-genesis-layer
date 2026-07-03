'use client';

import { useState, useEffect, useCallback } from 'react';
import { intel, auth } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import IntelAssistant from '@/components/IntelAssistant';
import { ChatSidebar } from '@/components/ChatSidebar';
import {
  Briefcase,
  Users,
  Building,
} from 'lucide-react';

interface Stats {
  clients: { total: number; active: number };
  employees: { total: number; current: number };
  requirements: { total: number; open: number };
  interviews: { total: number };
}

export default function IntelPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [sidebarKey, setSidebarKey] = useState(0);

  useEffect(() => {
    auth.me()
      .then(user => {
        const userRole = user.role || (user.is_staff ? 'admin' : 'standard');
        if (userRole === 'standard') window.location.href = '/knowledge-base';
      })
      .catch(() => { window.location.href = '/login'; });

    intel.stats()
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleNewConversation = useCallback(() => { setActiveConversationId(null); }, []);
  const handleSelectConversation = useCallback((id: string) => { setActiveConversationId(id); }, []);
  const handleConversationCreated = useCallback((id: string) => {
    setActiveConversationId(id);
    setSidebarKey(prev => prev + 1);
  }, []);

  const statCards = stats ? [
    { title: 'Active Clients', value: stats.clients.active, total: stats.clients.total, icon: Building, color: 'text-blue-600', bg: 'bg-blue-50 dark:bg-blue-950', href: '/intel/requirements' },
    { title: 'Open Requirements', value: stats.requirements.open, total: stats.requirements.total, icon: Briefcase, color: 'text-green-600', bg: 'bg-green-50 dark:bg-green-950', href: '/intel/requirements' },
    { title: 'Current Employees', value: stats.employees.current, total: stats.employees.total, icon: Users, color: 'text-orange-600', bg: 'bg-orange-50 dark:bg-orange-950' },
  ] : [];

  return (
    <main className="flex h-full overflow-hidden">
      <ChatSidebar
        key={sidebarKey}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
      />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-transparent">
        <div className="flex-shrink-0 border-b border-border/70 bg-background/60 px-4 py-4 backdrop-blur">
          <div className="dashboard-surface rounded-[1.5rem] border border-border/70 px-4 py-3 shadow-none">
            <div className="mb-3 flex items-center justify-between gap-4">
              <div>
                <h1 className="text-lg font-semibold text-foreground">Intel workspace</h1>
                <p className="text-sm text-muted-foreground">
                  Focused analysis with cleaner status treatment and less visual compression.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
            {loading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-7 w-28 rounded-lg" />
              ))
            ) : (
              statCards.map((stat) => (
                <button
                  key={stat.title}
                  onClick={() => stat.href && (window.location.href = stat.href)}
                  className={`flex items-center gap-2 rounded-2xl border border-border/70 px-3 py-2 ${stat.bg} ${stat.href ? 'cursor-pointer hover:opacity-80' : ''} transition-opacity`}
                >
                  <stat.icon className={`h-3.5 w-3.5 ${stat.color}`} />
                  <span className="text-sm font-semibold text-foreground">{stat.value}</span>
                  <span className="text-xs text-muted-foreground">{stat.title}</span>
                </button>
              ))
            )}
            </div>
          </div>
        </div>

        <div className="flex-1 min-h-0">
          <IntelAssistant
            className="h-full"
            conversationId={activeConversationId}
            onConversationCreated={handleConversationCreated}
          />
        </div>
      </div>
    </main>
  );
}
