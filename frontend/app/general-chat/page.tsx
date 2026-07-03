'use client';

import { useState, useCallback } from 'react';
import GeneralChat from '@/components/GeneralChat';
import { ChatSidebar } from '@/components/ChatSidebar';
import {
    Sheet,
    SheetContent,
    SheetHeader,
    SheetTitle,
    SheetTrigger,
} from '@/components/ui/sheet';
import { History } from 'lucide-react';

export default function GeneralChatPage() {
    const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
    const [sidebarKey, setSidebarKey] = useState(0);
    const [mobileSheetOpen, setMobileSheetOpen] = useState(false);

    const handleNewConversation = useCallback(() => {
        setActiveConversationId(null);
        setMobileSheetOpen(false);
    }, []);

    const handleSelectConversation = useCallback((id: string) => {
        setActiveConversationId(id);
        setMobileSheetOpen(false);
    }, []);

    const handleConversationCreated = useCallback((id: string) => {
        setActiveConversationId(id);
        setSidebarKey(prev => prev + 1);
    }, []);

    return (
        <main className="flex h-full overflow-hidden">
            {/* Desktop: persistent sidebar */}
            <div className="hidden md:flex">
                <ChatSidebar
                    key={`d-${sidebarKey}`}
                    activeConversationId={activeConversationId}
                    onSelectConversation={handleSelectConversation}
                    onNewConversation={handleNewConversation}
                    chatType="general"
                />
            </div>

            <div className="flex-1 flex flex-col min-w-0 relative">
                {/* Mobile: floating "History" pill triggers a sheet */}
                <Sheet open={mobileSheetOpen} onOpenChange={setMobileSheetOpen}>
                    <SheetTrigger asChild>
                        <button
                            type="button"
                            className="md:hidden absolute top-2 right-3 z-10 inline-flex items-center gap-1.5 rounded-full border border-white/60 bg-white/70 px-3 py-1.5 text-xs font-semibold backdrop-blur-md shadow-sm active:scale-95 transition-transform dark:bg-black/45 dark:border-white/10"
                            aria-label="Conversation history"
                        >
                            <History className="h-3.5 w-3.5" />
                            History
                        </button>
                    </SheetTrigger>
                    <SheetContent side="left" className="w-[85vw] max-w-sm p-0 flex flex-col">
                        <SheetHeader className="px-4 py-3 border-b">
                            <SheetTitle className="text-left">Conversations</SheetTitle>
                        </SheetHeader>
                        <div className="flex-1 overflow-hidden">
                            <ChatSidebar
                                key={`m-${sidebarKey}`}
                                activeConversationId={activeConversationId}
                                onSelectConversation={handleSelectConversation}
                                onNewConversation={handleNewConversation}
                                chatType="general"
                                className="w-full h-full border-0"
                            />
                        </div>
                    </SheetContent>
                </Sheet>

                <GeneralChat
                    className="flex-1"
                    conversationId={activeConversationId}
                    onConversationCreated={handleConversationCreated}
                />
            </div>
        </main>
    );
}
