'use client';

import { useEffect, useRef, useState } from 'react';
import {
  ArrowUp,
  Check,
  Database,
  Filter,
  Plus,
  ShieldCheck,
  Square,
  Wrench,
  X,
} from 'lucide-react';
import {
  workbench,
  type WorkbenchCompletion,
  type WorkbenchSource,
  type WorkbenchTool,
} from '@/lib/api';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import {
  WORKSPACE_TOOLS,
  type WorkspaceView,
} from '@/components/workbench/WorkbenchWorkspace';

type Props = {
  onAsk: (question: string) => void;
  busy?: boolean;
  onCancel?: () => void;
  pinned: string | null;
  onPin: (source: string | null) => void;
  onRunTool: (tool: WorkbenchTool) => void;
  onOpenWorkspace: (view: WorkspaceView) => void;
  dataAccess: 'direct' | 'mcp';
  onDataAccess: (mode: 'direct' | 'mcp') => void;
  onCompletionHeightChange?: (height: number) => void;
};

export default function Composer({
  onAsk,
  busy,
  onCancel,
  pinned,
  onPin,
  onRunTool,
  onOpenWorkspace,
  dataAccess,
  onDataAccess,
  onCompletionHeightChange,
}: Props) {
  const [value, setValue] = useState('');
  const [sources, setSources] = useState<WorkbenchSource[]>([]);
  const [toolList, setToolList] = useState<WorkbenchTool[]>([]);
  const [mode, setMode] = useState('local');
  const [completions, setCompletions] = useState<WorkbenchCompletion[]>([]);
  const [completionIndex, setCompletionIndex] = useState(0);
  const [focused, setFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const accessInitializedRef = useRef(false);
  const completionRequestRef = useRef(0);
  const listRef = useRef<HTMLUListElement>(null);
  const completionsOpen = focused && completions.length > 0;

  const loadData = () => {
    workbench.sources().then((result) => {
      setSources(result.sources);
      setMode(result.mode);
      if (!accessInitializedRef.current) {
        accessInitializedRef.current = true;
        onDataAccess(result.data_access);
      }
    }).catch(() => {});
    workbench.tools().then((result) => setToolList(result.tools)).catch(() => {});
  };

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    const context = completionContext(value);
    const requestId = ++completionRequestRef.current;
    if (!context || busy) {
      setCompletions([]);
      return;
    }
    const timer = window.setTimeout(() => {
      workbench.completions(context.term, context.kind)
        .then((response) => {
          if (completionRequestRef.current !== requestId) return;
          setCompletions(response.results);
          setCompletionIndex(0);
        })
        .catch(() => {
          if (completionRequestRef.current === requestId) setCompletions([]);
        });
    }, 180);
    return () => window.clearTimeout(timer);
  }, [value, busy]);

  // The list is drawn over the transcript, so the page reserves exactly as much room as
  // it actually occupies. A fixed reserve would leave a blank band under a two-item list
  // and still clip a full one.
  useEffect(() => {
    const height = completionsOpen ? (listRef.current?.offsetHeight ?? 0) + 8 : 0;
    onCompletionHeightChange?.(height);
    return () => onCompletionHeightChange?.(0);
  }, [completionsOpen, completions, onCompletionHeightChange]);

  const resize = () => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = '0px';
    textarea.style.height = `${Math.min(Math.max(textarea.scrollHeight, 72), 200)}px`;
  };

  const submit = () => {
    const question = value.trim();
    if (!question || busy) return;
    onAsk(question);
    setValue('');
    setCompletions([]);
    if (textareaRef.current) textareaRef.current.style.height = '72px';
  };

  const acceptCompletion = (item: WorkbenchCompletion) => {
    const context = completionContext(value);
    if (!context) return;
    const next = value.slice(0, context.start) + item.value + value.slice(context.end);
    setValue(next);
    setCompletions([]);
    requestAnimationFrame(() => {
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(next.length, next.length);
      resize();
    });
  };

  const pinnedLabel = sources.find((source) => source.id === pinned)?.label ?? pinned;

  return (
    // Focus is neutral by design: a blue rim around a permanently visible input reads as an
    // alert and competes with the response cards below it. Border width never changes, and
    // the ring is drawn outside the box, so focusing shifts nothing.
    <div className="relative rounded-2xl border border-border/80 bg-card shadow-[0_10px_35px_rgba(0,69,129,0.08)] transition-colors focus-within:border-foreground/25 focus-within:ring-2 focus-within:ring-foreground/[0.07]">
      {completionsOpen && (
        <ul
          ref={listRef}
          id="workbench-completions"
          role="listbox"
          className="absolute bottom-full left-0 z-50 mb-2 max-h-[min(18rem,calc(100svh-12rem))] w-full overflow-y-auto rounded-xl border border-border bg-popover p-1 shadow-xl"
        >
          {completions.map((item, index) => (
            <li key={`${item.kind}-${item.value}`} role="option" aria-selected={index === completionIndex}>
              <button
                id={`workbench-completion-${index}`}
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => acceptCompletion(item)}
                onMouseEnter={() => setCompletionIndex(index)}
                className={cn(
                  'flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left',
                  index === completionIndex && 'bg-accent text-accent-foreground',
                )}
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium">{item.label}</span>
                  <span className="block truncate text-[11px] text-muted-foreground">{item.detail}</span>
                </span>
                <span className="shrink-0 rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground">
                  Tab
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(event) => {
          setValue(event.target.value);
          setCompletionIndex(0);
          resize();
        }}
        onFocus={() => setFocused(true)}
        onBlur={() => window.setTimeout(() => setFocused(false), 120)}
        onKeyDown={(event) => {
          if (event.key === 'Tab' && completions.length > 0) {
            event.preventDefault();
            acceptCompletion(completions[completionIndex] ?? completions[0]);
            return;
          }
          if (event.key === 'ArrowDown' && completions.length > 0) {
            event.preventDefault();
            setCompletionIndex((current) => (current + 1) % completions.length);
            return;
          }
          if (event.key === 'ArrowUp' && completions.length > 0) {
            event.preventDefault();
            setCompletionIndex((current) => (current - 1 + completions.length) % completions.length);
            return;
          }
          if (event.key === 'Escape' && completions.length > 0) {
            event.preventDefault();
            setCompletions([]);
            return;
          }
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
        rows={1}
        placeholder="Ask about the loan book, market, competitors, or regulations..."
        aria-label="Ask Moneypal Workbench"
        aria-autocomplete="list"
        aria-expanded={completionsOpen}
        aria-controls="workbench-completions"
        aria-activedescendant={
          completionsOpen
            ? `workbench-completion-${completionIndex}`
            : undefined
        }
        className="composer-field block min-h-[72px] max-h-[200px] w-full resize-none bg-transparent px-4 pb-2 pt-4 text-[15px] leading-6 outline-none placeholder:text-muted-foreground/70"
      />

      <div className="flex items-center justify-between gap-3 px-2.5 pb-2.5 pt-1">
        <div className="flex min-w-0 items-center gap-1.5">
          <PlusMenu
            sources={sources}
            tools={toolList}
            pinned={pinned}
            onPin={onPin}
            onRunTool={onRunTool}
            onOpenWorkspace={onOpenWorkspace}
            dataAccess={dataAccess}
            onDataAccess={onDataAccess}
            onOpen={loadData}
          />

          {pinned ? (
            <span className="flex min-w-0 items-center gap-1.5 rounded-lg bg-accent px-2.5 py-1.5 text-xs font-medium text-accent-foreground">
              <Database className="size-3.5 shrink-0" />
              <span className="truncate">{pinnedLabel}</span>
              <button
                type="button"
                onClick={() => onPin(null)}
                className="rounded-sm text-muted-foreground hover:text-foreground"
                aria-label="Unpin source"
              >
                <X className="size-3.5" />
              </button>
            </span>
          ) : (
            <span className="hidden items-center gap-1.5 px-1.5 text-[11px] text-muted-foreground sm:flex">
              <ShieldCheck className="size-3.5 text-primary" />
              {dataAccess === 'mcp'
                ? 'PostgreSQL via MCP'
                : mode === 'local' ? 'Local and private' : mode}
            </span>
          )}
        </div>

        {/* Send and stop are the same control in two states — same 36×36 target, same
            icon-only treatment — so the composer does not reflow when a run starts. */}
        {busy ? (
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="size-9 shrink-0 rounded-full bg-muted text-primary shadow-none hover:bg-muted/80"
            onClick={onCancel}
            aria-label="Stop response"
          >
            <Square className="size-3.5 fill-current" />
          </Button>
        ) : (
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="size-9 shrink-0 rounded-full bg-muted text-primary shadow-none hover:bg-muted/80"
            onClick={submit}
            disabled={!value.trim()}
            aria-label="Send message"
          >
            <ArrowUp className="size-4" />
          </Button>
        )}
      </div>
    </div>
  );
}

type CompletionContext = {
  term: string;
  start: number;
  end: number;
  kind: 'all' | 'borrower' | 'customer' | 'account' | 'agent';
};

function completionContext(input: string): CompletionContext | null {
  const patterns: { pattern: RegExp; kind: CompletionContext['kind'] }[] = [
    {
      pattern: /\b(?:customer|borrower|client)\s*(?:id|number|no\.?|#)\s*([0-9][0-9,]*)$/i,
      kind: 'customer',
    },
    {
      pattern: /\b(?:loan\s+)?account\s*(?:number|no\.?|#)\s*([a-z0-9][a-z0-9,._/-]*)$/i,
      kind: 'account',
    },
    {
      pattern: /\b(?:details?|profile|information|info)\s+(?:of|for)\s+((?:agent|agnt)[-_ ]?\d*)$/i,
      kind: 'agent',
    },
    {
      pattern: /\bagents?\s+(?:name|details?|profile)\s+([a-z][\w .'-]{1,})$/i,
      kind: 'agent',
    },
    {
      pattern: /\b((?:agent|agnt)[-_ ]?\d*)$/i,
      kind: 'agent',
    },
    {
      pattern: /\b(?:repayment|payment)\s+histor(?:y|ies)\s+(?:of|for)\s+([\w .'-]{2,})$/i,
      kind: 'borrower',
    },
    {
      pattern: /\b(?:loan\s+(?:amount|details?)|loans?)\s+(?:of|for|to)\s+([\w .'-]{2,})$/i,
      kind: 'borrower',
    },
  ];

  for (const { pattern, kind } of patterns) {
    const match = pattern.exec(input);
    const term = match?.[1]?.trim();
    if (!match || !term || term.length < 2) continue;
    const offset = match[0].lastIndexOf(match[1]);
    return { term, start: match.index + offset, end: input.length, kind };
  }

  const bare = input.trim();
  const reserved = /\b(?:show|give|what|which|loan|repay|sanction|disburse|agent|customer|account)\b/i;
  if (
    bare.length >= 2 && bare.length <= 60
    && /^[a-z][\w.'-]*(?:\s+[a-z][\w.'-]*){0,3}$/i.test(bare)
    && !reserved.test(bare)
  ) {
    const start = input.indexOf(bare);
    return { term: bare, start, end: start + bare.length, kind: 'all' };
  }
  return null;
}

function PlusMenu({
  sources,
  tools,
  pinned,
  onPin,
  onRunTool,
  onOpenWorkspace,
  dataAccess,
  onDataAccess,
  onOpen,
}: {
  sources: WorkbenchSource[];
  tools: WorkbenchTool[];
  pinned: string | null;
  onPin: (source: string | null) => void;
  onRunTool: (tool: WorkbenchTool) => void;
  onOpenWorkspace: (view: WorkspaceView) => void;
  dataAccess: 'direct' | 'mcp';
  onDataAccess: (mode: 'direct' | 'mcp') => void;
  onOpen: () => void;
}) {
  return (
    <DropdownMenu onOpenChange={(open) => open && onOpen()}>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="size-9 shrink-0 rounded-xl text-muted-foreground shadow-none hover:bg-muted hover:text-foreground"
          aria-label="Open tools"
        >
          <Plus className="size-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" side="top" className="max-h-[420px] w-72 overflow-y-auto bg-card">
        <DropdownMenuLabel className="text-xs text-muted-foreground">Workbench</DropdownMenuLabel>
        {WORKSPACE_TOOLS.map((tool) => (
          <DropdownMenuItem
            key={tool.id}
            className="cursor-pointer items-start gap-2.5 rounded-lg py-2"
            onClick={() => onOpenWorkspace(tool.id)}
          >
            <span aria-hidden className="flex h-5 shrink-0 items-center">
              <tool.icon className="size-4 text-primary" />
            </span>
            <span>
              <span className="block text-sm font-medium text-foreground">{tool.label}</span>
              <span className="block text-[11px] leading-4 text-muted-foreground">{tool.description}</span>
            </span>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />

        {tools.length > 0 && (
          <>
            <DropdownMenuLabel className="flex items-center gap-2 text-xs text-muted-foreground">
              <Wrench className="size-3.5" /> Tools and reports
            </DropdownMenuLabel>
            {tools.map((tool) => (
              <DropdownMenuItem
                key={tool.id}
                className="cursor-pointer flex-col items-start gap-0.5 rounded-lg py-2"
                onClick={() => onRunTool(tool)}
              >
                <span className="text-sm font-medium text-foreground">{tool.label}</span>
                <span className="text-[11px] leading-4 text-muted-foreground">{tool.description}</span>
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
          </>
        )}

        <DropdownMenuSub>
          <DropdownMenuSubTrigger className="gap-2 rounded-lg">
            <Filter className="size-4" /> Choose a source
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent className="w-56 bg-card">
            <DropdownMenuItem className="gap-2 rounded-lg" onClick={() => onPin(null)}>
              <Check className={cn('size-4', pinned ? 'opacity-0' : 'opacity-100')} />
              Automatic routing
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            {sources.map((source) => (
              <DropdownMenuItem
                key={source.id}
                className="gap-2 rounded-lg"
                onClick={() => onPin(source.id)}
              >
                <Check className={cn('size-4', pinned === source.id ? 'opacity-100' : 'opacity-0')} />
                {source.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuSubContent>
        </DropdownMenuSub>
        <DropdownMenuSub>
          <DropdownMenuSubTrigger className="gap-2 rounded-lg">
            <Database className="size-4" /> PostgreSQL connection
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent className="w-56 bg-card">
            <DropdownMenuItem className="gap-2 rounded-lg" onClick={() => onDataAccess('direct')}>
              <Check className={cn('size-4', dataAccess === 'direct' ? 'opacity-100' : 'opacity-0')} />
              Direct adapter
            </DropdownMenuItem>
            <DropdownMenuItem className="gap-2 rounded-lg" onClick={() => onDataAccess('mcp')}>
              <Check className={cn('size-4', dataAccess === 'mcp' ? 'opacity-100' : 'opacity-0')} />
              MCP server
            </DropdownMenuItem>
          </DropdownMenuSubContent>
        </DropdownMenuSub>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
