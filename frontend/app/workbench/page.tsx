'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import {
  ArrowUpRight,
  BarChart3,
  Clock3,
  Landmark,
  Loader2,
  LogOut,
  Plus,
  Scale,
  TrendingUp,
} from 'lucide-react';
import {
  auth,
  workbench,
  type DemoUser,
  type WorkbenchConversation,
  type WorkbenchTool,
} from '@/lib/api';
import { clearUserRoleCache } from '@/lib/useUserRole';
import Composer from '@/components/workbench/Composer';
import WorkbenchTurn, { type WorkbenchTurnData } from '@/components/workbench/WorkbenchTurn';
import HistoryRail from '@/components/workbench/HistoryRail';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

export default function WorkbenchPage() {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);
  const [user, setUser] = useState<DemoUser | null>(null);
  const [turns, setTurns] = useState<WorkbenchTurnData[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pinned, setPinned] = useState<string | null>(null);
  const [conversations, setConversations] = useState<WorkbenchConversation[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const refreshHistory = useCallback(() => {
    workbench.conversations().then((result) => setConversations(result.conversations)).catch(() => {});
  }, []);

  useEffect(() => {
    auth.me()
      .then((currentUser) => {
        setUser(currentUser as DemoUser);
        setAuthorized(true);
        refreshHistory();
      })
      .catch(() => router.replace('/login'));
  }, [router, refreshHistory]);

  const newConversation = useCallback(() => {
    abortRef.current?.abort();
    setTurns([]);
    setConversationId(null);
    setBusy(false);
  }, []);

  const openConversation = useCallback(async (id: string) => {
    try {
      const record = await workbench.conversation(id);
      setTurns(record.turns.map((turn, index) => ({
        id: `h-${id}-${index}`,
        question: turn.question,
        pending: [],
        cards: [],
        done: true,
        route: { sources: turn.sources, intent: turn.question },
      })));
      setConversationId(id);
    } catch {
      // Keep the current conversation visible when a saved thread cannot be loaded.
    }
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [turns]);

  const ask = useCallback(async (question: string) => {
    const id = `t-${Date.now()}`;
    setTurns((previous) => [
      ...previous,
      { id, question, stage: 'understanding', pending: [], cards: [], done: false },
    ]);
    setBusy(true);

    const controller = new AbortController();
    abortRef.current = controller;

    const patch = (changes: Partial<WorkbenchTurnData>) =>
      setTurns((previous) => previous.map((turn) => turn.id === id ? { ...turn, ...changes } : turn));
    const patchWith = (update: (turn: WorkbenchTurnData) => WorkbenchTurnData) =>
      setTurns((previous) => previous.map((turn) => turn.id === id ? update(turn) : turn));

    try {
      for await (const event of workbench.ask(question, conversationId, pinned, controller.signal)) {
        switch (event.type) {
          case 'conversation':
            setConversationId(event.conversation_id);
            break;
          case 'stage':
            patch({ stage: event.stage });
            break;
          case 'route':
            patch({ route: { sources: event.sources, intent: event.intent }, pending: event.sources });
            break;
          case 'source_start':
            patchWith((turn) => ({ ...turn, pending: [...new Set([...turn.pending, event.source])] }));
            break;
          case 'source_card':
            patchWith((turn) => ({ ...turn, cards: [...turn.cards, event.card] }));
            break;
          case 'synthesis':
            patch({ synthesis: event.text });
            break;
          case 'refusal':
            patch({ refusal: event.refusal });
            break;
          case 'error':
            patch({ error: event.message });
            break;
          case 'done':
            patch({ done: true, stage: undefined });
            break;
        }
      }
    } catch (error: any) {
      patch({
        error: error?.name === 'AbortError' ? 'Response stopped.' : error?.message ?? 'Something went wrong.',
        done: true,
      });
    } finally {
      setBusy(false);
      abortRef.current = null;
      refreshHistory();
    }
  }, [conversationId, pinned, refreshHistory]);

  const runTool = useCallback(async (tool: WorkbenchTool) => {
    const id = `t-${Date.now()}`;
    setTurns((previous) => [
      ...previous,
      {
        id,
        question: tool.label,
        pending: [],
        cards: [],
        done: false,
        route: { sources: [], intent: tool.label },
      },
    ]);
    setBusy(true);

    const patch = (changes: Partial<WorkbenchTurnData>) =>
      setTurns((previous) => previous.map((turn) => turn.id === id ? { ...turn, ...changes } : turn));

    try {
      const card = await workbench.runTool(tool.id);
      patch({ cards: [card], done: true });
    } catch (error: any) {
      patch({ error: error?.message ?? 'The tool failed.', done: true });
    } finally {
      setBusy(false);
    }
  }, []);

  const logout = async () => {
    await auth.logout();
    clearUserRoleCache();
    router.replace('/login');
  };

  if (!authorized) {
    return (
      <div className="flex h-svh items-center justify-center bg-background">
        <Loader2 className="size-5 animate-spin text-primary" />
      </div>
    );
  }

  const composer = (
    <Composer
      onAsk={ask}
      busy={busy}
      onCancel={() => abortRef.current?.abort()}
      pinned={pinned}
      onPin={setPinned}
      onRunTool={runTool}
    />
  );

  return (
    <div className="flex h-svh flex-col overflow-hidden bg-background">
      <WorkbenchHeader
        user={user}
        onNew={newConversation}
        onHistory={() => setHistoryOpen(true)}
        onLogout={logout}
      />

      <main className="mx-auto flex min-h-0 w-full max-w-4xl flex-1 flex-col px-4 sm:px-6">
        {turns.length === 0 ? (
          <EmptyState onAsk={ask}>{composer}</EmptyState>
        ) : (
          <>
            <div className="min-h-0 flex-1 overflow-y-auto py-6 sm:py-8">
              <div className="space-y-8">
                {turns.map((turn) => (
                  <WorkbenchTurn key={turn.id} turn={turn} onAsk={ask} />
                ))}
                <div ref={bottomRef} />
              </div>
            </div>
            <div className="shrink-0 bg-background pb-[calc(env(safe-area-inset-bottom,0px)+12px)] pt-2 sm:pb-4">
              {composer}
              <p className="mt-2 text-center text-[11px] text-muted-foreground">
                Private by default. Verify important decisions against the cited source.
              </p>
            </div>
          </>
        )}
      </main>

      <HistoryRail
        open={historyOpen}
        onOpenChange={setHistoryOpen}
        conversations={conversations}
        activeId={conversationId}
        onNew={newConversation}
        onOpen={openConversation}
      />
    </div>
  );
}

function WorkbenchHeader({
  user,
  onNew,
  onHistory,
  onLogout,
}: {
  user: DemoUser | null;
  onNew: () => void;
  onHistory: () => void;
  onLogout: () => void;
}) {
  const name = user?.full_name || user?.username || 'User';
  const initials = name.split(' ').map((part) => part[0]).join('').toUpperCase().slice(0, 2);

  return (
    <header className="shrink-0 border-b border-border/60 bg-card/95">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-3">
          <Image
            src="/moneypal.png"
            alt="Moneypal"
            width={112}
            height={42}
            priority
            className="h-9 w-auto object-contain"
          />
          <span className="hidden border-l pl-3 text-sm font-medium text-muted-foreground sm:block">
            Workbench
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onNew}
            className="gap-2 rounded-xl text-muted-foreground shadow-none hover:bg-muted hover:text-foreground"
          >
            <Plus className="size-4" />
            <span className="hidden sm:inline">New chat</span>
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onHistory}
            className="gap-2 rounded-xl text-muted-foreground shadow-none hover:bg-muted hover:text-foreground"
          >
            <Clock3 className="size-4" />
            <span className="hidden sm:inline">History</span>
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button type="button" className="ml-1 rounded-full outline-none ring-offset-2 focus-visible:ring-2 focus-visible:ring-ring">
                <Avatar className="size-8 border border-border/70">
                  <AvatarFallback className="bg-primary text-[11px] font-semibold text-primary-foreground">
                    {initials}
                  </AvatarFallback>
                </Avatar>
                <span className="sr-only">Open account menu</span>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56 bg-card">
              <DropdownMenuLabel>
                <span className="block truncate text-sm">{name}</span>
                <span className="mt-0.5 block truncate text-xs font-normal text-muted-foreground">{user?.email}</span>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={onLogout} className="cursor-pointer gap-2 rounded-lg">
                <LogOut className="size-4" /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}

const EXAMPLES = [
  { icon: BarChart3, label: 'Portfolio performance', question: 'Summarize our current portfolio performance and the most important risks.' },
  { icon: TrendingUp, label: 'Market outlook', question: 'What is the current macroeconomic outlook for our lending business?' },
  { icon: Scale, label: 'Regulatory changes', question: 'What recent regulatory changes should we pay attention to?' },
  { icon: Landmark, label: 'Competitive landscape', question: 'How does our MSME portfolio compare with the wider market?' },
];

function EmptyState({ onAsk, children }: { onAsk: (question: string) => void; children: React.ReactNode }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center overflow-y-auto py-8 sm:py-12">
      <div className="w-full max-w-3xl text-center">
        <div className="mx-auto mb-5 flex size-11 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-[0_8px_24px_rgba(0,69,129,0.18)]">
          <ArrowUpRight className="size-5" />
        </div>
        <h1 className="font-headline text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
          What would you like to know?
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-muted-foreground sm:text-base">
          Ask across the loan book, market conditions, competitors, and regulations from one place.
        </p>

        <div className="mt-8 text-left">{children}</div>

        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          {EXAMPLES.map(({ icon: Icon, label, question }) => (
            <button
              key={label}
              type="button"
              onClick={() => onAsk(question)}
              className="group flex items-center gap-3 rounded-xl border border-border/70 bg-card px-3.5 py-3 text-left text-sm text-muted-foreground transition hover:border-primary/25 hover:bg-accent/50 hover:text-foreground"
            >
              <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted text-primary transition group-hover:bg-primary group-hover:text-primary-foreground">
                <Icon className="size-4" />
              </span>
              <span className="font-medium">{label}</span>
              <ArrowUpRight className="ml-auto size-3.5 opacity-40" />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
