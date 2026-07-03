'use client';

import { useState, useEffect } from 'react';
import { conversations } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
    SquarePen,
    ChevronLeft,
    ChevronRight,
    Loader2,
    X,
} from 'lucide-react';

interface Conversation {
    id: string;
    title: string;
    created_at: string;
    updated_at: string;
    message_count: number;
    last_message?: string;
}

interface ChatSidebarProps {
    activeConversationId?: string | null;
    onSelectConversation: (id: string) => void;
    onNewConversation: () => void;
    className?: string;
    chatType?: 'intel' | 'general' | 'youtube';
}

export function ChatSidebar({
    activeConversationId,
    onSelectConversation,
    onNewConversation,
    className,
    chatType = 'intel',
}: ChatSidebarProps) {
    const [isOpen, setIsOpen] = useState(true);
    const [conversationList, setConversationList] = useState<Conversation[]>([]);
    const [loading, setLoading] = useState(true);
    const [deletingId, setDeletingId] = useState<string | null>(null);

    useEffect(() => {
        loadConversations();
    }, [chatType]);

    const loadConversations = async () => {
        try {
            setLoading(true);
            const data = await conversations.list(chatType);
            setConversationList(data);
        } catch (error) {
            console.error('Failed to load conversations:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (e: React.MouseEvent, id: string) => {
        e.stopPropagation();
        if (deletingId) return;
        setDeletingId(id);
        try {
            await conversations.delete(id);
            setConversationList((prev) => prev.filter((c) => c.id !== id));
            if (activeConversationId === id) {
                onNewConversation();
            }
        } catch (error) {
            console.error('Failed to delete conversation:', error);
        } finally {
            setDeletingId(null);
        }
    };

    const groupedConversations = groupByDate(conversationList);

    if (!isOpen) {
        return (
            <div className={cn("flex flex-col items-center gap-2 border-r border-border/70 bg-sidebar/95 px-2 py-4 backdrop-blur", className)}>
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setIsOpen(true)}
                    className="h-8 w-8 text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent"
                    title="Open sidebar"
                >
                    <ChevronRight className="h-4 w-4" />
                </Button>
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={onNewConversation}
                    className="h-8 w-8 text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent"
                    title="New chat"
                >
                    <SquarePen className="h-4 w-4" />
                </Button>
            </div>
        );
    }

    return (
        <div className={cn("flex w-72 flex-shrink-0 flex-col border-r border-border/70 bg-sidebar/95 backdrop-blur", className)}>
            <div className="border-b border-border/70 px-3 py-3">
                <div className="mb-3 rounded-2xl border border-sidebar-border/80 bg-white/75 p-3 shadow-sm">
                    <p className="text-xs font-medium uppercase tracking-[0.16em] text-sidebar-foreground/45">Workspace</p>
                    <p className="mt-1 text-sm font-semibold text-sidebar-foreground">
                        {chatType === 'intel' ? 'Intel assistant' : chatType === 'general' ? 'General chat' : 'YouTube snippets'}
                    </p>
                </div>
                <div className="flex flex-shrink-0 items-center justify-between">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={onNewConversation}
                        className="flex items-center gap-2 px-2 text-sm font-medium text-sidebar-foreground hover:bg-sidebar-accent"
                    >
                        <SquarePen className="h-4 w-4" />
                        New chat
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setIsOpen(false)}
                        className="h-7 w-7 text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent"
                    >
                        <ChevronLeft className="h-4 w-4" />
                    </Button>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto min-h-0 px-2 pb-2">
                {loading ? (
                    <div className="flex items-center justify-center py-10">
                        <Loader2 className="h-4 w-4 animate-spin text-sidebar-foreground/40" />
                    </div>
                ) : conversationList.length === 0 ? (
                    <div className="text-center py-10 px-4">
                        <p className="text-xs text-sidebar-foreground/50">No conversations yet</p>
                    </div>
                ) : (
                    Object.entries(groupedConversations).map(([group, items]) => (
                        <div key={group} className="mb-4">
                            <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-sidebar-foreground/40">
                                {group}
                            </div>
                            <div className="space-y-0.5">
                                {items.map((conv) => (
                                    <div
                                        key={conv.id}
                                        className={cn(
                                            "group flex w-full items-center gap-2 rounded-2xl px-3 py-3 text-left text-xs transition-colors",
                                            activeConversationId === conv.id
                                                ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-sm"
                                                : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
                                        )}
                                    >
                                        <button
                                            type="button"
                                            onClick={() => onSelectConversation(conv.id)}
                                            className="flex-1 truncate text-left leading-snug"
                                        >
                                        <span className="flex-1 truncate leading-snug">{conv.title}</span>
                                        </button>
                                        <button
                                            type="button"
                                            onClick={(e) => handleDelete(e, conv.id)}
                                            className="flex-shrink-0 rounded p-0.5 opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                                            title="Delete"
                                        >
                                            {deletingId === conv.id ? (
                                                <Loader2 className="h-3 w-3 animate-spin" />
                                            ) : (
                                                <X className="h-3 w-3" />
                                            )}
                                        </button>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}

function groupByDate(convList: Conversation[]): Record<string, Conversation[]> {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000);
    const lastWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);

    const groups: Record<string, Conversation[]> = {};

    for (const conv of convList) {
        const date = new Date(conv.updated_at);
        let group: string;
        if (date >= today) group = 'Today';
        else if (date >= yesterday) group = 'Yesterday';
        else if (date >= lastWeek) group = 'Last 7 days';
        else group = 'Older';

        if (!groups[group]) groups[group] = [];
        groups[group].push(conv);
    }

    return groups;
}

export function useChatSidebar() {
    const [refreshKey, setRefreshKey] = useState(0);
    const refresh = () => setRefreshKey((k) => k + 1);
    return { refreshKey, refresh };
}
