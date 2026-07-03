'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { intel, conversations } from '@/lib/api';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ArrowUp, Square, Bot, User, ChevronDown, MapPin, Briefcase, Calendar, Building2, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { CompanyReport } from '@/components/CompanyReport';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Message {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  intent?: string;
  results?: any[];
  report?: string;
  error?: string;
  timestamp: Date;
  streaming?: boolean;
}

interface IntelAssistantProps {
  className?: string;
  conversationId?: string | null;
  onConversationCreated?: (id: string) => void;
}

const WELCOME_MESSAGE: Message = {
  role: 'assistant',
  content: 'Hello! I can help you find information about clients, job requirements, interview questions, and more. What would you like to know?',
  timestamp: new Date(),
};

// ── Intent-aware result list ──────────────────────────────────────────────────

function isUuid(s: string): boolean {
  return /^[0-9a-f]{24}$|^[0-9a-f-]{36}$/i.test(s);
}

function ClientLabel({ name }: { name: string }) {
  if (!name || isUuid(name)) return null;
  return (
    <span className="inline-flex items-center gap-1 text-muted-foreground">
      <Building2 className="h-3 w-3 shrink-0" />
      {name}
    </span>
  );
}

function RequirementsList({ results }: { results: any[] }) {
  return (
    <div className="w-full space-y-0 rounded-lg border border-border overflow-hidden">
      {results.map((r, idx) => (
        <div key={idx} className={cn('px-4 py-3 bg-card', idx < results.length - 1 && 'border-b border-border/60')}>
          <div className="flex items-start justify-between gap-3">
            <p className="text-sm font-medium leading-snug">{r.position || 'Untitled'}</p>
            {r.experience_level && (
              <span className="shrink-0 text-[10px] text-muted-foreground border border-border rounded px-1.5 py-0.5 whitespace-nowrap">
                {r.experience_level}
              </span>
            )}
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]">
            <ClientLabel name={r.client} />
            {r.location && (
              <span className="inline-flex items-center gap-1 text-muted-foreground">
                <MapPin className="h-3 w-3 shrink-0" />
                {r.location}
              </span>
            )}
            {r.date_posted && (
              <span className="inline-flex items-center gap-1 text-muted-foreground">
                <Calendar className="h-3 w-3 shrink-0" />
                {r.date_posted}
              </span>
            )}
          </div>
          {r.skills && (
            <p className="mt-1.5 text-[11px] text-muted-foreground line-clamp-1">
              <span className="font-medium text-foreground/70">Skills: </span>{r.skills}
            </p>
          )}
          {r.description && (
            <p className="mt-1 text-[11px] text-muted-foreground line-clamp-2">{r.description}</p>
          )}
        </div>
      ))}
    </div>
  );
}

function CandidatesList({ results }: { results: any[] }) {
  return (
    <div className="w-full space-y-0 rounded-lg border border-border overflow-hidden">
      {results.map((r, idx) => (
        <div key={idx} className={cn('px-4 py-3 bg-card flex items-center justify-between gap-4', idx < results.length - 1 && 'border-b border-border/60')}>
          <div className="min-w-0">
            <p className="text-sm font-medium leading-snug truncate">{r.candidate_name || 'Unknown'}</p>
            <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px]">
              {r.role && (
                <span className="inline-flex items-center gap-1 text-muted-foreground">
                  <Briefcase className="h-3 w-3 shrink-0" />
                  {r.role}
                </span>
              )}
              <ClientLabel name={r.client} />
            </div>
          </div>
          {r.interview_date && (
            <span className="shrink-0 text-[11px] text-muted-foreground whitespace-nowrap">
              {r.interview_date}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

function QuestionsList({ results }: { results: any[] }) {
  return (
    <div className="w-full space-y-0 rounded-lg border border-border overflow-hidden">
      {results.map((r, idx) => (
        <div key={idx} className={cn('px-4 py-3 bg-card', idx < results.length - 1 && 'border-b border-border/60')}>
          <div className="flex items-start justify-between gap-3">
            <p className="text-sm font-medium leading-snug">{r.role || 'Interview'}</p>
            {r.interview_date && (
              <span className="shrink-0 text-[10px] text-muted-foreground border border-border rounded px-1.5 py-0.5">
                {r.interview_date}
              </span>
            )}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 text-[11px]">
            <ClientLabel name={r.client} />
            {r.candidate_name && (
              <span className="text-muted-foreground">{r.candidate_name}</span>
            )}
          </div>
          {r.question && (
            <p className="mt-1.5 text-[11px] text-muted-foreground line-clamp-3">{r.question}</p>
          )}
        </div>
      ))}
    </div>
  );
}

function ResultsList({ results, intent }: { results: any[]; intent?: string }) {
  if (!results.length) return null;

  const first = results[0];

  if (intent === 'requirements') {
    return <RequirementsList results={results} />;
  }

  if (intent === 'interviews') {
    if (first.query_type === 'candidate_info') {
      return <CandidatesList results={results} />;
    }
    return <QuestionsList results={results} />;
  }

  if (intent === 'company_overview') {
    return (
      <div className="w-full space-y-0 rounded-lg border border-border overflow-hidden">
        {results.map((r, idx) => (
          <div key={idx} className={cn('px-4 py-3 bg-card text-sm', idx < results.length - 1 && 'border-b border-border/60')}>
            <p className="text-[11px] text-muted-foreground line-clamp-3">{r.content || 'No content available'}</p>
            {r.source && r.source !== 'unknown' && (
              <p className="text-[10px] text-muted-foreground/60 mt-1 truncate">{r.source}</p>
            )}
          </div>
        ))}
      </div>
    );
  }

  // Fallback: generic compact list
  return (
    <div className="w-full space-y-0 rounded-lg border border-border overflow-hidden">
      {results.map((r, idx) => (
        <div key={idx} className={cn('px-4 py-3 bg-card text-sm', idx < results.length - 1 && 'border-b border-border/60')}>
          <p className="font-medium">{r.position || r.name || r.candidate_name || r.role || r.content || 'Result'}</p>
          {r.client && !isUuid(r.client) && <p className="text-[11px] text-muted-foreground mt-0.5">{r.client}</p>}
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

export default function IntelAssistant({
  className,
  conversationId,
  onConversationCreated
}: IntelAssistantProps) {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [showScrollButton, setShowScrollButton] = useState(false);

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
      loadConversation(conversationId);
    } else if (!conversationId) {
      currentConversationId.current = null;
      setMessages([WELCOME_MESSAGE]);
    }
  }, [conversationId]);

  const loadConversation = async (id: string) => {
    try {
      setLoadingConversation(true);
      currentConversationId.current = id;
      const data = await conversations.get(id);
      if (data.messages && data.messages.length > 0) {
        const loadedMessages: Message[] = data.messages.map((msg: any) => ({
          id: msg.id,
          role: msg.role,
          content: msg.content,
          intent: msg.intent,
          report: msg.report,
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

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (input.trim() && !isLoading) {
        handleSubmit();
      }
    }
  };

  const adjustTextareaHeight = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 180) + 'px';
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
    // Scroll after user message
    setTimeout(() => scrollToBottom(true), 50);

    try {
      let activeConversationId: string = currentConversationId.current ?? '';
      if (!activeConversationId) {
        const newConv = await conversations.create();
        activeConversationId = newConv.id;
        currentConversationId.current = activeConversationId;
        onConversationCreated?.(activeConversationId);
      }

      await conversations.addMessage(activeConversationId, 'user', userMessage.content);

      // Add a streaming placeholder
      const streamingMsg: Message = {
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        streaming: true,
      };
      setMessages(prev => [...prev, streamingMsg]);

      let fullReport = '';
      let msgIntent = '';
      let msgResults: any[] = [];
      let msgError = '';

      await intel.queryStream(
        userMessage.content,
        (metadata) => {
          msgIntent = metadata.intent;
          msgResults = metadata.results || [];
          if (metadata.error) msgError = metadata.error;
          setMessages(prev => {
            const rest = prev.slice(0, -1);
            const last = prev[prev.length - 1];
            return [...rest, {
              ...last,
              intent: msgIntent,
              results: msgResults,
              ...(msgError ? { error: msgError } : {}),
            }];
          });
        },
        (chunk) => {
          fullReport += chunk;
          setMessages(prev => {
            const rest = prev.slice(0, -1);
            const last = prev[prev.length - 1];
            return [...rest, { ...last, report: fullReport, streaming: true }];
          });
        },
        (error) => {
          msgError = error;
          setMessages(prev => {
            const rest = prev.slice(0, -1);
            const last = prev[prev.length - 1];
            return [...rest, { ...last, error }];
          });
        }
      );

      // Mark streaming as done
      setMessages(prev => {
        const rest = prev.slice(0, -1);
        const last = prev[prev.length - 1];
        return [...rest, { ...last, streaming: false }];
      });

      let finalContent = '';
      if (!fullReport && !msgError && (!msgResults || msgResults.length === 0)) {
        finalContent = 'No data found for your query.';
        setMessages(prev => {
          const newMessages = [...prev];
          newMessages[newMessages.length - 1].content = finalContent;
          return newMessages;
        });
      }

      await conversations.addMessage(
        activeConversationId,
        'assistant',
        finalContent || 'Report generated',
        msgIntent,
        fullReport
      );

    } catch (error) {
      setMessages(prev => {
        const rest = prev.slice(0, -1);
        const last = prev[prev.length - 1];
        return [...rest, {
          ...last,
          streaming: false,
          error: error instanceof Error ? error.message : 'Something went wrong. Please try again.',
        }];
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={cn('flex flex-col h-full relative bg-transparent', className)}>
      {/* Messages Area */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto"
      >
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
                  <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Bot className="h-4 w-4 text-white" />
                  </div>
                )}

                <div className={cn('flex flex-col gap-2 min-w-0', msg.role === 'user' ? 'items-end max-w-[80%]' : 'items-start flex-1 min-w-0')}>
                  {msg.role === 'user' ? (
                    <div className="bg-white/70 dark:bg-white/10 backdrop-blur-sm border border-white/60 dark:border-white/12 rounded-2xl rounded-tr-sm px-4 py-3 text-sm text-foreground shadow-sm">
                      {msg.content}
                    </div>
                  ) : (
                    <div className="w-full text-sm text-foreground">
                      {msg.intent && (
                        <Badge variant="secondary" className="mb-2 text-[10px] font-mono uppercase tracking-wider">
                          {msg.intent.replace(/_/g, ' ')}
                        </Badge>
                      )}

                      {/* Error block */}
                      {msg.error && (
                        <div className="mb-2 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/8 px-3 py-2.5 text-sm text-destructive">
                          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                          <span>{msg.error}</span>
                        </div>
                      )}

                      {/* Plain text content (e.g. "No data found") */}
                      {msg.content && !msg.error && (
                        <div className="mb-2 text-sm text-muted-foreground">{msg.content}</div>
                      )}

                      {/* Streaming report or full report */}
                      {msg.report ? (
                        <CompanyReport markdown={msg.report} />
                      ) : msg.results && msg.results.length > 0 ? (
                        <ResultsList results={msg.results} intent={msg.intent} />
                      ) : !msg.content && !msg.error && !msg.streaming ? (
                        <div className="text-muted-foreground text-sm">No data found for your query.</div>
                      ) : null}

                      {/* Streaming cursor */}
                      {msg.streaming && !msg.report && !msg.content && (
                        <div className="flex gap-1 py-2">
                          <span className="w-1.5 h-1.5 rounded-full bg-foreground/40 animate-bounce" style={{ animationDelay: '0ms' }} />
                          <span className="w-1.5 h-1.5 rounded-full bg-foreground/40 animate-bounce" style={{ animationDelay: '150ms' }} />
                          <span className="w-1.5 h-1.5 rounded-full bg-foreground/40 animate-bounce" style={{ animationDelay: '300ms' }} />
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {msg.role === 'user' && (
                  <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0 mt-0.5">
                    <User className="h-4 w-4 text-primary-foreground" />
                  </div>
                )}
              </div>
            ))
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Scroll to bottom button */}
      {showScrollButton && (
        <button
          onClick={() => scrollToBottom(true)}
          className="absolute bottom-24 right-4 z-10 rounded-full border border-border bg-background shadow-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          <ChevronDown className="h-4 w-4" />
        </button>
      )}

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
              placeholder="Ask about requirements, interviews, or company details..."
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
    </div>
  );
}