'use client';

import { MessageSquare, Plus } from 'lucide-react';
import type { WorkbenchConversation } from '@/lib/api';
import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { cn } from '@/lib/utils';

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  conversations: WorkbenchConversation[];
  activeId: string | null;
  onNew: () => void;
  onOpen: (id: string) => void;
};

export default function HistoryRail({
  open,
  onOpenChange,
  conversations,
  activeId,
  onNew,
  onOpen,
}: Props) {
  const startNew = () => {
    onNew();
    onOpenChange(false);
  };

  const openConversation = (id: string) => {
    onOpen(id);
    onOpenChange(false);
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="left" className="flex w-[88vw] max-w-sm flex-col gap-0 bg-card p-0">
        <SheetHeader className="border-b px-5 py-5 pr-12 text-left">
          <SheetTitle className="text-base">Conversations</SheetTitle>
          <SheetDescription>Return to a previous question or start fresh.</SheetDescription>
        </SheetHeader>

        <div className="p-3">
          <Button onClick={startNew} className="w-full justify-start gap-2 shadow-none">
            <Plus className="size-4" /> New conversation
          </Button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
          {conversations.length === 0 ? (
            <div className="rounded-xl border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">
              Your conversations will appear here.
            </div>
          ) : (
            <ul className="space-y-1">
              {conversations.map((conversation) => (
                <li key={conversation.conversation_id}>
                  <button
                    type="button"
                    onClick={() => openConversation(conversation.conversation_id)}
                    className={cn(
                      'flex w-full items-start gap-3 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-muted',
                      activeId === conversation.conversation_id && 'bg-accent text-accent-foreground',
                    )}
                  >
                    <MessageSquare className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium">{conversation.title}</span>
                      <span className="mt-0.5 block text-xs text-muted-foreground">
                        {conversation.turn_count} {conversation.turn_count === 1 ? 'question' : 'questions'}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
