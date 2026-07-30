'use client';

import { useCallback, useRef, useState } from 'react';
import { nlq } from '@/lib/api';
import AskBar from '@/components/nlq/AskBar';
import ChatThread, { type Turn } from '@/components/nlq/ChatThread';

// Ask Genesis — natural-language questions over the loan book.
//
// The SSE stream is consumed here rather than inside ChatThread so the thread stays a pure
// rendering component: it receives turns and displays them, which keeps the streaming state
// machine in one place.

export default function AskPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

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
            case 'chart':
              setConversationId(event.response.conversation_id);
              patch({
                chart: event.response.chart ?? undefined,
                turnId: event.response.turn_id,
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

  return (
    <div className="mx-auto flex h-full w-full max-w-4xl flex-col gap-6 px-4 py-6">
      <header>
        <h1 className="text-xl font-semibold text-foreground">Ask Genesis</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Questions about the loan book, answered from the warehouse. Every number shows its
          SQL, its formula and its source tables.
        </p>
      </header>

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

      <div className="sticky bottom-0 bg-background pb-2 pt-1">
        <AskBar onAsk={ask} busy={busy} onCancel={() => abortRef.current?.abort()} />
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
