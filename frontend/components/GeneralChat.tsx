'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { generalChat, conversations } from '@/lib/api';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { ArrowUp, Square, Bot, User, ChevronDown, Download, Loader2, Video } from 'lucide-react';
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

interface GeneralChatProps {
    className?: string;
    conversationId?: string | null;
    onConversationCreated?: (id: string) => void;
}

const WELCOME_MESSAGE: Message = {
    role: 'assistant',
    content: "Hello! I'm your AI assistant. Ask me anything — from coding questions to creative writing, analysis, or general knowledge. How can I help you today?",
    timestamp: new Date(),
};

export default function GeneralChat({
    className,
    conversationId,
    onConversationCreated
}: GeneralChatProps) {
    const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [loadingConversation, setLoadingConversation] = useState(false);
    const [showScrollButton, setShowScrollButton] = useState(false);
    const [downloadingIndex, setDownloadingIndex] = useState<number | null>(null);
    const [downloadingSnippetIndex, setDownloadingSnippetIndex] = useState<number | null>(null);
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

    const handleDownload = async (index: number) => {
        const msg = messages[index];
        if (!msg || msg.role !== 'assistant') return;

        let topic = 'General Topic';
        for (let i = index - 1; i >= 0; i--) {
            if (messages[i].role === 'user') {
                topic = messages[i].content.slice(0, 50);
                break;
            }
        }

        setDownloadingIndex(index);
        try {
            await generalChat.downloadPdf(msg.content, topic);
        } catch (error) {
            console.error('Failed to download PDF:', error);
        } finally {
            setDownloadingIndex(null);
        }
    };

    const handleSnippetDownload = async (index: number) => {
        const sources = youtubeSources[index];
        if (!sources || sources.length === 0) return;

        // Use the highest scoring source for the snippet
        const bestSource = sources[0];

        setDownloadingSnippetIndex(index);
        try {
            await generalChat.downloadSnippet(
                bestSource.video_url,
                bestSource.timestamp_start,
                bestSource.timestamp_end
            );
        } catch (error) {
            console.error('Failed to download snippet:', error);
        } finally {
            setDownloadingSnippetIndex(null);
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
                const newConv = await conversations.create(undefined, 'general');
                activeConversationId = newConv.id;
                currentConversationId.current = activeConversationId;
                onConversationCreated?.(activeConversationId);
            }

            await conversations.addMessage(activeConversationId, 'user', userMessage.content, 'general_chat');

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
            setIsLoading(false); // Enable input again while streaming? Or keep disabled? We'll keep disabled below until done.

            let fullAssistantResponse = '';

            await generalChat.queryStream(
                userMessage.content,
                history,
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
                const finalDbMessage = await conversations.addMessage(activeConversationId, 'assistant', fullAssistantResponse, 'general_chat');
                // Update final message with DB ID
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
        <div className={cn('flex flex-col h-full relative bg-transparent', className)}>
            {/* Messages Area */}
            <div ref={scrollContainerRef} className="flex-1 overflow-y-auto">
                <div className="max-w-3xl mx-auto w-full px-4 py-6 space-y-6">

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
                            <div key={i} className={cn('flex gap-4 msg-enter', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
                                {msg.role === 'assistant' && (
                                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center flex-shrink-0 mt-0.5">
                                        <Bot className="h-4 w-4 text-white" />
                                    </div>
                                )}

                                <div className={cn('min-w-0', msg.role === 'user' ? 'max-w-[80%]' : 'flex-1')}>
                                    {msg.role === 'user' ? (
                                        <div className="bg-white/70 dark:bg-white/10 backdrop-blur-sm border border-white/60 dark:border-white/12 rounded-2xl rounded-tr-sm px-4 py-3 text-sm text-foreground shadow-sm">
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
                                                            pre({ children }: any) {
                                                                return <>{children}</>;
                                                            },
                                                            p({ children }: any) { return <p className="mb-2 leading-relaxed">{children}</p>; },
                                                            ul({ children }: any) { return <ul className="list-disc pl-5 mb-2 space-y-0.5">{children}</ul>; },
                                                            ol({ children }: any) { return <ol className="list-decimal pl-5 mb-2 space-y-0.5">{children}</ol>; },
                                                            blockquote({ children }: any) { return <blockquote className="border-l-2 border-primary/40 pl-3 text-muted-foreground my-2">{children}</blockquote>; },
                                                            strong({ children }: any) { return <strong className="font-semibold text-foreground">{children}</strong>; },
                                                            table({ children }: any) { return <div className="overflow-x-auto my-2"><table className="text-xs border-collapse w-full">{children}</table></div>; },
                                                            th({ children }: any) { return <th className="bg-muted px-3 py-2 text-left font-semibold border border-border">{children}</th>; },
                                                            td({ children }: any) { return <td className="px-3 py-2 border border-border">{children}</td>; },
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
                                            {i > 0 && (!msg.id || !msg.id.toString().startsWith('temp-')) && msg.content && (
                                                <div className="flex justify-start mt-1">
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        className="h-8 text-xs text-muted-foreground gap-1.5 bg-background shadow-sm hover:text-foreground"
                                                        onClick={() => handleDownload(i)}
                                                        disabled={downloadingIndex === i}
                                                    >
                                                        {downloadingIndex === i ? (
                                                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                        ) : (
                                                            <Download className="h-3.5 w-3.5" />
                                                        )}
                                                        Download PDF
                                                    </Button>
                                                </div>
                                            )}
                                            {i > 0 && youtubeSources[i]?.length > 0 && (
                                                <div className="flex justify-start mt-1">
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        className="h-8 text-xs text-muted-foreground gap-1.5 bg-background shadow-sm hover:text-foreground"
                                                        onClick={() => handleSnippetDownload(i)}
                                                        disabled={downloadingSnippetIndex === i}
                                                    >
                                                        {downloadingSnippetIndex === i ? (
                                                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                        ) : (
                                                            <Video className="h-3.5 w-3.5" />
                                                        )}
                                                        Download Snippet
                                                    </Button>
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

                    {/* isLoading bottom indicator removed since we render it inside empty messages */}

                    <div ref={messagesEndRef} />
                </div>
            </div>

            {/* Scroll to bottom button */}
            {
                showScrollButton && (
                    <button
                        onClick={() => scrollToBottom(true)}
                        className="absolute bottom-24 right-4 z-10 rounded-full border border-border bg-background shadow-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                    >
                        <ChevronDown className="h-4 w-4" />
                    </button>
                )
            }

            {/* Input Area */}
            <div className="flex-shrink-0 border-t border-white/40 dark:border-white/8 [border-top-color:rgba(255,255,255,0.60)] dark:[border-top-color:rgba(255,255,255,0.10)] [background:rgba(255,255,255,0.55)] dark:[background:rgba(16,13,11,0.70)] [backdrop-filter:saturate(200%)_blur(24px)] [-webkit-backdrop-filter:saturate(200%)_blur(24px)] px-4 py-3">
                <div className="max-w-3xl mx-auto w-full">
                    <div className="flex items-end gap-3 [background:rgba(255,255,255,0.65)] dark:[background:rgba(255,255,255,0.05)] [backdrop-filter:saturate(180%)_blur(20px)] [-webkit-backdrop-filter:saturate(180%)_blur(20px)] rounded-2xl border border-white/80 dark:border-white/14 [border-top-color:rgba(255,255,255,0.95)] dark:[border-top-color:rgba(255,255,255,0.20)] shadow-[0_4px_16px_rgba(221,122,58,0.08),0_1px_0_rgba(255,255,255,0.85)_inset] dark:shadow-[0_4px_16px_rgba(0,0,0,0.30),0_1px_0_rgba(255,255,255,0.06)_inset] px-4 py-3 focus-within:border-ring/60 focus-within:shadow-[0_4px_20px_rgba(221,122,58,0.18),0_1px_0_rgba(255,255,255,0.85)_inset] transition-all duration-200">
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
                    <p className="text-[10px] text-muted-foreground/50 text-center mt-2">
                        Press Enter to send, Shift+Enter for new line
                    </p>
                </div>
            </div>
        </div >
    );
}
