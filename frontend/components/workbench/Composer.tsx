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
import { workbench, type WorkbenchSource, type WorkbenchTool } from '@/lib/api';
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
}: Props) {
  const [value, setValue] = useState('');
  const [sources, setSources] = useState<WorkbenchSource[]>([]);
  const [toolList, setToolList] = useState<WorkbenchTool[]>([]);
  const [mode, setMode] = useState('local');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const accessInitializedRef = useRef(false);

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
    if (textareaRef.current) textareaRef.current.style.height = '72px';
  };

  const pinnedLabel = sources.find((source) => source.id === pinned)?.label ?? pinned;

  return (
    // Focus is neutral by design: a blue rim around a permanently visible input reads as an
    // alert and competes with the response cards below it. Border width never changes, and
    // the ring is drawn outside the box, so focusing shifts nothing.
    <div className="overflow-hidden rounded-2xl border border-border/80 bg-card shadow-[0_10px_35px_rgba(0,69,129,0.08)] transition-colors focus-within:border-foreground/25 focus-within:ring-2 focus-within:ring-foreground/[0.07]">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(event) => {
          setValue(event.target.value);
          resize();
        }}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
        rows={1}
        placeholder="Ask about the loan book, market, competitors, or regulations..."
        aria-label="Ask Moneypal Workbench"
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
