'use client';

import { useState, useCallback } from 'react';
import YoutubeChat from '@/components/YoutubeChat';
import { ChatSidebar } from '@/components/ChatSidebar';

export default function YoutubeChatPage() {
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
                chatType="youtube"
            />
            <div className="flex-1 flex flex-col min-w-0">
                <YoutubeChat
                    className="flex-1"
                    conversationId={activeConversationId}
                    onConversationCreated={handleConversationCreated}
                />
            </div>
        </main>
    );
}
