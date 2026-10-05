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
    <section aria-label="Queued messages" className="w-full">
      <div className="flex justify-end py-2 text-right">
        <Button type="button" variant="ghost" size="sm" className="px-0" onClick={() => onChange({ type: 'clear' })}>
          Clear queue
        </Button>
      </div>
      <ul className="space-y-3">
        {queue.messages.map((message, index) => (
          <li key={message.id} className="flex justify-end">
            <div className="group relative max-w-[88%] sm:max-w-[78%]">
              <div className="rounded-2xl rounded-br-md border border-border/50 bg-muted px-4 py-2.5 text-right text-sm leading-6 text-foreground shadow-none">
                <div className="relative min-w-0 flex-1">
                  <p className={`whitespace-pre-wrap break-words${queue.editingId === message.id ? ' invisible' : ''}`}>
                    {message.text}
                  </p>
                  {queue.editingId === message.id && (
                    <textarea
                      autoFocus
                      aria-label="Edit queued message"
                      value={draft}
                      onChange={(event) => setDraft(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.nativeEvent.isComposing) return;
                        if (event.key === 'Enter' && !event.shiftKey) {
                          event.preventDefault();
                          onChange({ type: 'save', id: message.id, text: draft });
                        } else if (event.key === 'Escape') {
                          event.preventDefault();
                          onChange({ type: 'cancelEdit' });
                        }
                      }}
                      className="queued-message-editor absolute inset-0 size-full resize-none overflow-auto appearance-none bg-transparent p-0 text-right text-sm leading-6"
                    />
                  )}
                  {editingIndex >= 0 && index >= editingIndex && (
                    <p className="sr-only">Waiting for edit</p>
                  )}
                </div>
              </div>
              <div className="absolute left-full top-2.5 flex items-center gap-1 pl-2 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 [@media(hover:none)]:opacity-100">
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
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
