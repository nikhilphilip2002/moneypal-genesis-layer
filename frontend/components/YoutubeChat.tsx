'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { youtubeChat, conversations } from '@/lib/api';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { ArrowUp, Square, Bot, User, ChevronDown, Video } from 'lucide-react';
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/cjs/styles/prism';

interface Message {
    id?: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
}

interface YoutubeChatProps {
    className?: string;
    conversationId?: string | null;
    onConversationCreated?: (id: string) => void;
}

const WELCOME_MESSAGE: Message = {
    role: 'assistant',
    content: "Hello! I can help you find and extract snippets from YouTube videos. Do you want to search our processed database or search YouTube directly?",
    timestamp: new Date(),
};

export default function YoutubeChat({
    className,
    conversationId,
    onConversationCreated
}: YoutubeChatProps) {
    const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
    const [input, setInput] = useState('');
    const [searchMode, setSearchMode] = useState<'db' | 'direct'>('db');
    const [isLoading, setIsLoading] = useState(false);
    const [loadingConversation, setLoadingConversation] = useState(false);
    const [showScrollButton, setShowScrollButton] = useState(false);
    const [youtubeSources, setYoutubeSources] = useState<Record<number, any[]>>({});

    const messagesEndRef = useRef<HTMLDivElement>(null);
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const currentConversationId = useRef<string | null>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const isNearBottom = useCallback(() => {
        const el = scrollContainerRef.current;
        if (!el) return true;
        return el.scrollHeight - el.scrollTop - el.clientHeight < 120;
    }, []);

    const scrollToBottom = useCallback((force = false) => {
        if (force || isNearBottom()) {
            messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }, [isNearBottom]);

    const handleScroll = useCallback(() => {
        setShowScrollButton(!isNearBottom());
    }, [isNearBottom]);

    useEffect(() => {
        const el = scrollContainerRef.current;
        if (!el) return;
        el.addEventListener('scroll', handleScroll, { passive: true });
        return () => el.removeEventListener('scroll', handleScroll);
    }, [handleScroll]);

    useEffect(() => {
        if (conversationId && conversationId !== currentConversationId.current) {
            loadConversationData(conversationId);
        } else if (!conversationId) {
            currentConversationId.current = null;
            setMessages([WELCOME_MESSAGE]);
        }
    }, [conversationId]);

    const loadConversationData = async (id: string) => {
        try {
            setLoadingConversation(true);
            currentConversationId.current = id;
            const data = await conversations.get(id);
            if (data.messages && data.messages.length > 0) {
                const loadedMessages: Message[] = data.messages.map((msg: any) => ({
                    id: msg.id,
                    role: msg.role,
                    content: msg.content,
                    timestamp: new Date(msg.timestamp),
                }));
                setMessages(loadedMessages);
                setTimeout(() => scrollToBottom(true), 100);
            } else {
                setMessages([WELCOME_MESSAGE]);
            }
        } catch (error) {
            console.error('Failed to load conversation:', error);
            setMessages([WELCOME_MESSAGE]);
        } finally {
            setLoadingConversation(false);
        }
    };

    const adjustTextareaHeight = () => {
        const el = textareaRef.current;
        if (!el) return;
        el.style.height = 'auto';
        el.style.height = Math.min(el.scrollHeight, 180) + 'px';
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (input.trim() && !isLoading) handleSubmit();
        }
    };

    const handleSubmit = async () => {
        if (!input.trim() || isLoading) return;

        const userMessage: Message = {
            role: 'user',
            content: input,
            timestamp: new Date(),
        };

        setMessages(prev => [...prev, userMessage]);
        setInput('');
        if (textareaRef.current) textareaRef.current.style.height = 'auto';
        setIsLoading(true);
        setTimeout(() => scrollToBottom(true), 50);

        try {
            let activeConversationId: string = currentConversationId.current ?? '';
            if (!activeConversationId) {
                const newConv = await conversations.create(undefined, 'youtube');
                activeConversationId = newConv.id;
                currentConversationId.current = activeConversationId;
                onConversationCreated?.(activeConversationId);
            }

            await conversations.addMessage(activeConversationId, 'user', userMessage.content, 'youtube_chat');

            const history = messages.slice(-10).map(m => ({
                role: m.role,
                content: m.content,
            }));

            // Prepare placeholder for streaming assistant message
            const initialAssistantMessage: Message = {
                role: 'assistant',
                content: '',
                timestamp: new Date(),
            };

            // Unique ID for the temporary streaming message (using Date.now() is fine for frontend tracking)
            const tempId = `temp-${Date.now()}`;
            initialAssistantMessage.id = tempId;

            setMessages(prev => [...prev, initialAssistantMessage]);
            setIsLoading(false);

            let fullAssistantResponse = '';

            await youtubeChat.queryStream(
                userMessage.content,
                history,
                searchMode,
                (chunkText: string) => {
                    fullAssistantResponse += chunkText;
                    setMessages(prev =>
                        prev.map(msg =>
                            msg.id === tempId ? { ...msg, content: fullAssistantResponse } : msg
                        )
                    );
                    scrollToBottom();
                },
                (errorText: string) => {
                    console.error("Streaming error:", errorText);
                    setMessages(prev =>
                        prev.map(msg =>
                            msg.id === tempId ? { ...msg, content: fullAssistantResponse + `\n\n[Error: ${errorText}]` } : msg
                        )
                    );
                },
                (sources: any[]) => {
                    setYoutubeSources(prev => ({
                        ...prev,
                        [messages.length + 1]: sources
                    }));
                }
            );

            // Once stream finishes, save the final complete message to DB
            if (fullAssistantResponse) {
                const finalDbMessage = await conversations.addMessage(activeConversationId, 'assistant', fullAssistantResponse, 'youtube_chat');
                setMessages(prev =>
                    prev.map(msg =>
                        msg.id === tempId ? { ...msg, id: finalDbMessage.id } : msg
                    )
                );
            } else {
                setMessages(prev =>
                    prev.map(msg =>
                        msg.id === tempId ? { ...msg, content: "I apologize, but I could not generate a response." } : msg
                    )
                );
            }

        } catch (error) {
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: `Sorry, there was an error: ${error instanceof Error ? error.message : 'Unknown error'}`,
                timestamp: new Date(),
            }]);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className={cn('flex flex-col h-full relative bg-background', className)}>
            {/* Messages Area */}
            <div ref={scrollContainerRef} className="flex-1 overflow-y-auto">
                <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">

                    {loadingConversation ? (
                        <div className="flex items-center justify-center py-20">
                            <div className="flex gap-1">
                                <span className="w-2 h-2 rounded-full bg-muted-foreground/40 animate-bounce" style={{ animationDelay: '0ms' }} />
                                <span className="w-2 h-2 rounded-full bg-muted-foreground/40 animate-bounce" style={{ animationDelay: '150ms' }} />
                                <span className="w-2 h-2 rounded-full bg-muted-foreground/40 animate-bounce" style={{ animationDelay: '300ms' }} />
                            </div>
                        </div>
                    ) : (
                        messages.map((msg, i) => (
                            <div key={i} className={cn('flex gap-4', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
                                {msg.role === 'assistant' && (
                                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-red-500 to-orange-500 flex items-center justify-center flex-shrink-0 mt-0.5">
                                        <Bot className="h-4 w-4 text-white" />
                                    </div>
                                )}

                                <div className={cn('min-w-0', msg.role === 'user' ? 'max-w-[80%]' : 'flex-1')}>
                                    {msg.role === 'user' ? (
                                        <div className="bg-muted rounded-2xl rounded-tr-sm px-4 py-3 text-sm text-foreground">
                                            {msg.content}
                                        </div>
                                    ) : (
                                        <div className="flex flex-col gap-2">
                                            <div className="text-sm text-foreground leading-relaxed">
                                                {msg.content ? (
                                                    <ReactMarkdown
                                                        remarkPlugins={[remarkGfm]}
                                                        components={{
                                                            code({ node, inline, className, children, ...props }: any) {
                                                                const match = /language-(\w+)/.exec(className || '');
                                                                if (!inline && match) {
                                                                    return (
                                                                        <div className="my-3 rounded-xl overflow-hidden font-mono text-xs">
                                                                            <SyntaxHighlighter
                                                                                {...props}
                                                                                style={vscDarkPlus}
                                                                                language={match[1]}
                                                                                PreTag="div"
                                                                                customStyle={{ margin: 0, padding: '16px', background: '#1e1e1e' }}
                                                                            >
                                                                                {String(children).replace(/\n$/, '')}
                                                                            </SyntaxHighlighter>
                                                                        </div>
                                                                    );
                                                                }
                                                                return (
                                                                    <code className="bg-zinc-200 dark:bg-zinc-700 text-zinc-800 dark:text-zinc-100 px-1.5 py-0.5 rounded text-xs font-mono" {...props}>
                                                                        {children}
                                                                    </code>
                                                                );
                                                            },
                                                            p({ children }: any) { return <p className="mb-2 leading-relaxed">{children}</p>; },
                                                            ul({ children }: any) { return <ul className="list-disc pl-5 mb-2 space-y-0.5">{children}</ul>; },
                                                            ol({ children }: any) { return <ol className="list-decimal pl-5 mb-2 space-y-0.5">{children}</ol>; },
                                                        }}
                                                    >
                                                        {msg.content}
                                                    </ReactMarkdown>
                                                ) : (
                                                    <div className="flex items-center gap-1 py-1 h-[24px]">
                                                        <span className="w-2 h-2 rounded-full bg-foreground/40 animate-bounce" style={{ animationDelay: '0ms' }} />
                                                        <span className="w-2 h-2 rounded-full bg-foreground/40 animate-bounce" style={{ animationDelay: '150ms' }} />
                                                        <span className="w-2 h-2 rounded-full bg-foreground/40 animate-bounce" style={{ animationDelay: '300ms' }} />
                                                    </div>
                                                )}
                                            </div>

                                            {/* Render YouTube Iframe */}
                                            {i > 0 && youtubeSources[i]?.length > 0 && (
                                                <div className="flex flex-col gap-2 mt-3">
                                                    {youtubeSources[i].map((source, idx) => (
                                                        <div key={idx} className="border border-border rounded-xl overflow-hidden shadow-sm">
                                                            <div className="bg-muted px-4 py-2 text-xs font-medium border-b border-border flex items-center gap-2">
                                                                <Video className="h-3.5 w-3.5 text-red-500" />
                                                                {source.video_title || 'YouTube Video'}
                                                                <span className="text-muted-foreground ml-auto">
                                                                    Starting @ {source.timestamp_start}s
                                                                </span>
                                                            </div>
                                                            <div className="aspect-video w-full bg-black">
                                                                <iframe
                                                                    width="100%"
                                                                    height="100%"
                                                                    src={`https://www.youtube.com/embed/${source.video_id}?start=${source.timestamp_start}&autoplay=0`}
                                                                    title="YouTube video player"
                                                                    frameBorder="0"
                                                                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                                                    allowFullScreen
                                                                ></iframe>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>

                                {
                                    msg.role === 'user' && (
                                        <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0 mt-0.5">
                                            <User className="h-4 w-4 text-primary-foreground" />
                                        </div>
                                    )
                                }
                            </div>
                        ))
                    )}
                    <div ref={messagesEndRef} />
                </div>
            </div>

            {/* Scroll to bottom button */}
            {
                showScrollButton && (
                    <button
                        onClick={() => scrollToBottom(true)}
                        className="absolute bottom-32 right-4 z-10 rounded-full border border-border bg-background shadow-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                    >
                        <ChevronDown className="h-4 w-4" />
                    </button>
                )
            }

            {/* Input Area */}
            <div className="flex-shrink-0 border-t border-border bg-background px-4 py-3">
                <div className="max-w-3xl mx-auto space-y-3">

                    {/* Search Mode Toggle */}
                    <div className="flex items-center justify-between px-1">
                        <RadioGroup
                            defaultValue="db"
                            className="flex gap-4"
                            value={searchMode}
                            onValueChange={(val) => setSearchMode(val as 'db' | 'direct')}
                        >
                            <div className="flex items-center space-x-2">
                                <RadioGroupItem value="db" id="mode-db" />
                                <Label htmlFor="mode-db" className="text-xs font-medium cursor-pointer">Search Database</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                                <RadioGroupItem value="direct" id="mode-direct" />
                                <Label htmlFor="mode-direct" className="text-xs font-medium cursor-pointer">Search YouTube Directly</Label>
                            </div>
                        </RadioGroup>
                    </div>

                    <div className="flex items-end gap-3 bg-muted/50 rounded-2xl border border-border px-4 py-3 focus-within:border-ring focus-within:ring-1 focus-within:ring-ring transition-all">
                        <Textarea
                            ref={textareaRef}
                            value={input}
                            onChange={(e) => {
                                setInput(e.target.value);
                                adjustTextareaHeight();
                            }}
                            onKeyDown={handleKeyDown}
                            placeholder="Ask me anything..."
                            disabled={isLoading}
                            rows={1}
                            className="flex-1 resize-none border-0 bg-transparent shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 min-h-[24px] max-h-[180px] py-0 text-sm leading-6"
                        />
                        <Button
                            type="button"
                            size="icon"
                            onClick={handleSubmit}
                            disabled={!input.trim() || isLoading}
                            className={cn(
                                'h-8 w-8 rounded-lg flex-shrink-0 transition-all',
                                input.trim() && !isLoading
                                    ? 'bg-foreground text-background hover:bg-foreground/80'
                                    : 'bg-muted text-muted-foreground cursor-not-allowed'
                            )}
                        >
                            {isLoading ? <Square className="h-3 w-3 fill-current" /> : <ArrowUp className="h-4 w-4" />}
                        </Button>
                    </div>
                </div>
            </div>
        </div >
    );
}
