'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { auth, workbench, type WorkbenchTool, type WorkbenchConversation } from '@/lib/api';
import Composer from '@/components/workbench/Composer';
import WorkbenchTurn, { type WorkbenchTurnData } from '@/components/workbench/WorkbenchTurn';
import HistoryRail from '@/components/workbench/HistoryRail';
import Guidebot from '@/components/workbench/Guidebot';
import { Sparkles } from 'lucide-react';

// The Workbench — one chat that answers from every intelligence source. The SSE stream is
// consumed here so the turn components stay pure renderers: they receive turns and display
// them, and this page owns the streaming state machine (mirrors the Ask page's design).

export default function WorkbenchPage() {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);
  const [turns, setTurns] = useState<WorkbenchTurnData[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pinned, setPinned] = useState<string | null>(null);
  const [conversations, setConversations] = useState<WorkbenchConversation[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const refreshHistory = useCallback(() => {
    workbench.conversations().then((r) => setConversations(r.conversations)).catch(() => {});
  }, []);

  useEffect(() => {
    auth
      .me()
      .then(() => { setAuthorized(true); refreshHistory(); })
      .catch(() => router.replace('/login'));
  }, [router, refreshHistory]);

  const newConversation = useCallback(() => {
    setTurns([]);
    setConversationId(null);
    abortRef.current?.abort();
  }, []);

  const openConversation = useCallback(async (id: string) => {
    // Past turns store the question + which sources answered, not the rendered cards, so
    // opening a conversation seeds the thread with those questions as a lightweight recap
    // and threads new turns onto the same id. Full card replay is a later enhancement.
    try {
      const rec = await workbench.conversation(id);
      setTurns(
        rec.turns.map((t, i) => ({
          id: `h-${id}-${i}`,
          question: t.question,
          pending: [],
          cards: [],
          done: true,
          route: { sources: t.sources, intent: t.question },
        })),
      );
      setConversationId(id);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [turns]);

  const ask = useCallback(
    async (question: string) => {
      const id = `t-${Date.now()}`;
      setTurns((prev) => [
        ...prev,
        { id, question, stage: 'understanding', pending: [], cards: [], done: false },
      ]);
      setBusy(true);

      const controller = new AbortController();
      abortRef.current = controller;

      const patch = (changes: Partial<WorkbenchTurnData>) =>
        setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, ...changes } : t)));
      const patchFn = (fn: (t: WorkbenchTurnData) => WorkbenchTurnData) =>
        setTurns((prev) => prev.map((t) => (t.id === id ? fn(t) : t)));

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
              patchFn((t) => ({ ...t, pending: [...new Set([...t.pending, event.source])] }));
              break;
            case 'source_card':
              patchFn((t) => ({ ...t, cards: [...t.cards, event.card] }));
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
      } catch (err: any) {
        if (err?.name !== 'AbortError') {
          patch({ error: err?.message ?? 'Something went wrong.', done: true });
        } else {
          patch({ error: 'Cancelled.', done: true });
        }
      } finally {
        setBusy(false);
        abortRef.current = null;
        refreshHistory();
      }
    },
    [conversationId, pinned, refreshHistory],
  );

  const runTool = useCallback(async (tool: WorkbenchTool) => {
    const id = `t-${Date.now()}`;
    setTurns((prev) => [
      ...prev,
      { id, question: tool.label, pending: [], cards: [], done: false,
        route: { sources: [], intent: tool.label } },
    ]);
    setBusy(true);
    const patch = (changes: Partial<WorkbenchTurnData>) =>
      setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, ...changes } : t)));
    try {
      const card = await workbench.runTool(tool.id);
      patch({ cards: [card], done: true });
    } catch (err: any) {
      patch({ error: err?.message ?? 'The tool failed.', done: true });
    } finally {
      setBusy(false);
    }
  }, []);

  if (!authorized) return null;

  return (
    <div className="flex h-full">
      <HistoryRail
        conversations={conversations}
        activeId={conversationId}
        onNew={newConversation}
        onOpen={openConversation}
      />
      <div className="mx-auto flex h-full w-full max-w-3xl flex-col px-4 py-4 md:px-6">
        <div className="min-h-0 flex-1 overflow-y-auto pb-4">
          {turns.length === 0 ? (
            <EmptyState onAsk={ask} />
          ) : (
            <div className="space-y-6">
              {turns.map((turn) => (
                <WorkbenchTurn key={turn.id} turn={turn} onAsk={ask} />
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <div className="pt-1">
          <Composer
            onAsk={ask}
            busy={busy}
            onCancel={() => abortRef.current?.abort()}
            pinned={pinned}
            onPin={setPinned}
            onRunTool={runTool}
          />
          <p className="mt-1.5 text-center text-[11px] text-muted-foreground">
            Runs locally. Every number shows its source.
          </p>
        </div>
      </div>
      <Guidebot />
    </div>
  );
}

const EXAMPLES = [
  'What was our disbursement by branch last quarter?',
  'What is the RBI repo rate stance right now?',
  'How does our MSME book compare with the wider MSME credit market?',
  'What is our PAR 30 right now?',
];

function EmptyState({ onAsk }: { onAsk: (q: string) => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
      <div className="flex size-11 items-center justify-center rounded-xl border bg-muted/40">
        <Sparkles className="size-5 text-muted-foreground" />
      </div>
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Genesis Workbench</h1>
        <p className="mt-1 max-w-md text-sm text-muted-foreground">
          Ask about the loan book, the market, or the regulations. One chat routes to the right
          source and answers from it — grounded, and running on your own machine.
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {EXAMPLES.map((q) => (
          <button
            key={q}
            onClick={() => onAsk(q)}
            className="rounded-full border px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
