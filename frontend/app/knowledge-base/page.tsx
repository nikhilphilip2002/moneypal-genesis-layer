'use client';

import { useState, useCallback } from 'react';
import IntelAssistant from '@/components/IntelAssistant';
import { ChatSidebar } from '@/components/ChatSidebar';

export default function KnowledgeBasePage() {
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [sidebarKey, setSidebarKey] = useState(0);

  const handleNewConversation = useCallback(() => {
    setActiveConversationId(null);
  }, []);

  const handleSelectConversation = useCallback((id: string) => {
    setActiveConversationId(id);
  }, []);

  const handleConversationCreated = useCallback((id: string) => {
    setActiveConversationId(id);
    setSidebarKey(prev => prev + 1);
  }, []);

  return (
    <main className="flex h-full overflow-hidden">
      <ChatSidebar
        key={sidebarKey}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
      />
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden bg-transparent">
        <div className="flex-shrink-0 border-b border-border/70 bg-background/60 px-4 py-4 backdrop-blur">
          <div className="dashboard-surface rounded-[1.5rem] border border-border/70 px-4 py-3 shadow-none">
            <h1 className="text-lg font-semibold text-foreground">Knowledge base</h1>
            <p className="text-sm text-muted-foreground">
              Retrieval and grounded Q&A in the same quieter workspace language.
            </p>
          </div>
        </div>
        <IntelAssistant
          className="flex-1"
          conversationId={activeConversationId}
          onConversationCreated={handleConversationCreated}
        />
      </div>
    </main>
  );
}
