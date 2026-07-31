'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { auth, nlq } from '@/lib/api';
import { canAccess, homeRoute, type UserRole } from '@/lib/useUserRole';
import AskBar from '@/components/nlq/AskBar';
import ChatThread, { type Turn } from '@/components/nlq/ChatThread';

// Ask Genesis — natural-language questions over the loan book.
//
// The SSE stream is consumed here rather than inside ChatThread so the thread stays a pure
// rendering component: it receives turns and displays them, which keeps the streaming state
// machine in one place.

export default function AskPage() {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Hiding the nav entry is not access control — the route still resolves if typed. This
  // mirrors the guard every other role-gated page carries.
  useEffect(() => {
    auth
      .me()
      .then((user) => {
        const role = user.role as UserRole;
        if (!canAccess(role, '/ask')) {
          router.replace(homeRoute(role));
          return;
        }
        setAuthorized(true);
      })
      .catch(() => router.replace('/login'));
  }, [router]);

  const ask = useCallback(
    async (question: string) => {
      const id = `t-${Date.now()}`;
      setTurns((prev) => [...prev, { id, question, stage: 'understanding', done: false }]);
      setBusy(true);

      const controller = new AbortController();
      abortRef.current = controller;

      const patch = (changes: Partial<Turn>) =>
        setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, ...changes } : t)));

      try {
        for await (const event of nlq.ask(question, conversationId, controller.signal)) {
          switch (event.type) {
            case 'stage':
              patch({ stage: event.stage });
              break;
            case 'rewrite':
              patch({ resolvedQuestion: event.resolved_question });
              break;
            case 'plan':
              patch({ planRoute: event.route, planModel: event.model });
              break;
            case 'chart':
              setConversationId(event.response.conversation_id);
              patch({
                chart: event.response.chart ?? undefined,
                turnId: event.response.turn_id,
                planSummary: event.response.plan_summary,
                done: true,
                stage: undefined,
              });
              break;
            case 'clarify':
              patch({ clarification: event.clarification, done: true, stage: undefined });
              break;
            case 'refusal':
              patch({ refusal: event.refusal, done: true, stage: undefined });
              break;
            case 'error':
              patch({ error: event.message, done: true, stage: undefined });
              break;
            case 'done':
              patch({ done: true, stage: undefined });
              break;
          }
        }
      } catch (err: any) {
        if (err?.name !== 'AbortError') {
          patch({ error: err?.message ?? 'Something went wrong.', done: true, stage: undefined });
        } else {
          patch({ error: 'Cancelled.', done: true, stage: undefined });
        }
      } finally {
        setBusy(false);
        abortRef.current = null;
      }
    },
    [conversationId],
  );

  if (!authorized) return null;

  return (
    // The page owns the scroll rather than the window, because the ask bar is pinned to the
    // bottom. Header typography and gutters match the other workspaces; the column is
    // narrower than their max-w-6xl because a conversation reads badly at full width.
    <div className="flex h-full flex-col">
      <div className="mx-auto flex h-full w-full max-w-4xl flex-col gap-5 px-4 py-6 md:px-6 md:py-8">
        <section className="space-y-2">
          <h1 className="font-headline text-2xl font-semibold tracking-tight md:text-3xl">
            Ask Genesis
          </h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Questions about the loan book, answered from the warehouse. Every number shows its
            SQL, its formula and its source tables.
          </p>
        </section>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {turns.length === 0 ? (
            <EmptyState />
          ) : (
            <ChatThread
              turns={turns}
              setTurns={setTurns}
              conversationId={conversationId}
              onAsk={ask}
            />
          )}
        </div>

        <div className="sticky bottom-0 pb-2 pt-1">
          <AskBar onAsk={ask} busy={busy} onCancel={() => abortRef.current?.abort()} />
        </div>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center text-center">
      <p className="text-sm text-muted-foreground">
        Ask a question to begin — try one of the examples below the box.
      </p>
    </div>
  );
}
