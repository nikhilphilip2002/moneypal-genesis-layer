'use client';

import { useState } from 'react';
import { Pencil, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { MessageQueue, MessageQueueAction } from '@/lib/workbench-queue';

export default function QueuedMessages({ queue, onChange }: {
  queue: MessageQueue;
  onChange: (action: MessageQueueAction) => void;
}) {
  const [draft, setDraft] = useState('');
  if (queue.messages.length === 0) return null;
  const editingIndex = queue.messages.findIndex((message) => message.id === queue.editingId);

  return (
    <section aria-label="Queued messages" className="mb-3 rounded-2xl border border-border bg-card">
      <div className="flex items-center justify-between px-4 py-2">
        <span className="text-xs font-medium text-muted-foreground" role="status">
          {queue.messages.length} queued
        </span>
        <Button type="button" variant="ghost" size="sm" onClick={() => onChange({ type: 'clear' })}>
          Clear queue
        </Button>
      </div>
      <ol className="max-h-[35svh] overflow-y-auto px-4 pb-3">
        {queue.messages.map((message, index) => (
          <li key={message.id} className="border-t border-border/60 py-2">
            <div className="flex items-start gap-2">
              <span className="mt-1 text-xs text-muted-foreground">{index + 1}.</span>
              <div className="min-w-0 flex-1">
                {queue.editingId === message.id ? (
                  <>
                    <textarea
                      autoFocus
                      aria-label="Edit queued message"
                      value={draft}
                      onChange={(event) => setDraft(event.target.value)}
                      className="min-h-20 w-full resize-y rounded-lg border border-border bg-background p-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    />
                    <div className="mt-2 flex gap-2">
                      <Button type="button" size="sm" disabled={!draft.trim()}
                        onClick={() => onChange({ type: 'save', id: message.id, text: draft })}>
                        Save
                      </Button>
                      <Button type="button" size="sm" variant="ghost"
                        onClick={() => onChange({ type: 'cancelEdit' })}>
                        Cancel
                      </Button>
                    </div>
                  </>
                ) : (
                  <p className="whitespace-pre-wrap break-words text-sm">{message.text}</p>
                )}
                {editingIndex >= 0 && index >= editingIndex && (
                  <p className="mt-1 text-xs text-muted-foreground">Waiting for edit</p>
                )}
              </div>
              <Button type="button" size="icon" variant="ghost" className="size-7 shrink-0"
                aria-label={`Edit queued message ${index + 1}`} disabled={queue.editingId !== null}
                onClick={() => {
                  setDraft(message.text);
                  onChange({ type: 'edit', id: message.id });
                }}>
                <Pencil className="size-3.5" />
              </Button>
              <Button type="button" size="icon" variant="ghost" className="size-7 shrink-0"
                aria-label={`Remove queued message ${index + 1}`}
                onClick={() => onChange({ type: 'remove', id: message.id })}>
                <X className="size-3.5" />
              </Button>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
