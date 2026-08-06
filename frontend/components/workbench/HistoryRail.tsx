'use client';

import { Plus, MessageSquare } from 'lucide-react';
import type { WorkbenchConversation } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

// The left rail for the full-replacement workbench: New + recent conversations. Deliberately
// slim and dense — it is navigation, not content — and hidden on small screens where the
// chat owns the whole width.

type Props = {
  conversations: WorkbenchConversation[];
  activeId: string | null;
  onNew: () => void;
  onOpen: (id: string) => void;
};

export default function HistoryRail({ conversations, activeId, onNew, onOpen }: Props) {
  return (
    <aside className="hidden w-56 shrink-0 flex-col border-r md:flex">
      <div className="p-2">
        <Button variant="outline" size="sm" className="w-full justify-start gap-2" onClick={onNew}>
          <Plus className="size-4" /> New
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
        <div className="px-1 py-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/50">
          History
        </div>
        {conversations.length === 0 ? (
          <p className="px-1 py-2 text-xs text-muted-foreground">No conversations yet.</p>
        ) : (
          <ul className="space-y-0.5">
            {conversations.map((c) => (
              <li key={c.conversation_id}>
                <button
                  onClick={() => onOpen(c.conversation_id)}
                  className={cn(
                    'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors hover:bg-muted',
                    activeId === c.conversation_id && 'bg-muted font-medium',
                  )}
                >
                  <MessageSquare className="size-3.5 shrink-0 text-muted-foreground" />
                  <span className="truncate">{c.title}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
