'use client';

import { useEffect, useRef, useState } from 'react';
import { Plus, ArrowUp, Square, Paperclip, Wrench, Filter, Cpu, Check } from 'lucide-react';
import { workbench, type WorkbenchSource, type WorkbenchTool } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuSub, DropdownMenuSubContent, DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';

// The composer. Beyond free text it carries the "+" — the extensible surface for every use
// case that is not a typed question: tools/actions, attachments, pinning a source, and the
// model/privacy mode. Phase 1 wires the source list and the live mode badge; the action and
// attachment handlers are stubbed with a clear "soon" so the surface is real but honest.

type Props = {
  onAsk: (question: string) => void;
  busy?: boolean;
  onCancel?: () => void;
  pinned: string | null;
  onPin: (source: string | null) => void;
  onRunTool: (tool: WorkbenchTool) => void;
};

export default function Composer({ onAsk, busy, onCancel, pinned, onPin, onRunTool }: Props) {
  const [value, setValue] = useState('');
  const [sources, setSources] = useState<WorkbenchSource[]>([]);
  const [toolList, setToolList] = useState<WorkbenchTool[]>([]);
  const [mode, setMode] = useState<string>('local');
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    workbench.sources().then((r) => { setSources(r.sources); setMode(r.mode); }).catch(() => {});
    workbench.tools().then((r) => setToolList(r.tools)).catch(() => {});
  }, []);

  const submit = () => {
    const q = value.trim();
    if (!q || busy) return;
    onAsk(q);
    setValue('');
    if (ref.current) ref.current.style.height = 'auto';
  };

  const grow = () => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  };

  return (
    <div className="rounded-xl border bg-background shadow-sm">
      {pinned && (
        <div className="flex items-center gap-1.5 px-3 pt-2">
          <Badge variant="secondary" className="gap-1 text-[10px]">
            {sources.find((s) => s.id === pinned)?.label ?? pinned}
            <button className="ml-0.5 opacity-60 hover:opacity-100" onClick={() => onPin(null)}>×</button>
          </Badge>
        </div>
      )}
      <div className="flex items-end gap-1.5 p-2">
        <PlusMenu sources={sources} tools={toolList} mode={mode} pinned={pinned} onPin={onPin} onRunTool={onRunTool} />
        <textarea
          ref={ref}
          value={value}
          onChange={(e) => { setValue(e.target.value); grow(); }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
          }}
          rows={1}
          placeholder="Ask anything about the book, the market, or the regulations…"
          className="max-h-[200px] flex-1 resize-none bg-transparent px-1 py-1.5 text-sm outline-none placeholder:text-muted-foreground"
        />
        {busy ? (
          <Button size="icon" variant="ghost" className="size-8 shrink-0" onClick={onCancel} aria-label="Stop">
            <Square className="size-4" />
          </Button>
        ) : (
          <Button size="icon" className="size-8 shrink-0" onClick={submit} disabled={!value.trim()} aria-label="Send">
            <ArrowUp className="size-4" />
          </Button>
        )}
      </div>
    </div>
  );
}

function PlusMenu({
  sources, tools, mode, pinned, onPin, onRunTool,
}: {
  sources: WorkbenchSource[];
  tools: WorkbenchTool[];
  mode: string;
  pinned: string | null;
  onPin: (s: string | null) => void;
  onRunTool: (t: WorkbenchTool) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size="icon" variant="ghost" className="size-8 shrink-0" aria-label="Add">
          <Plus className="size-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" side="top" className="w-56">
        <DropdownMenuLabel className="text-xs">Add to this question</DropdownMenuLabel>

        {tools.length > 0 ? (
          <DropdownMenuSub>
            <DropdownMenuSubTrigger className="gap-2 text-sm">
              <Wrench className="size-4" /> Tools & actions
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent className="w-60">
              {tools.map((t) => (
                <DropdownMenuItem key={t.id} className="flex-col items-start gap-0.5 text-sm"
                                  onClick={() => onRunTool(t)}>
                  <span>{t.label}</span>
                  <span className="text-[10px] text-muted-foreground">{t.description}</span>
                </DropdownMenuItem>
              ))}
            </DropdownMenuSubContent>
          </DropdownMenuSub>
        ) : (
          <DropdownMenuItem disabled className="gap-2 text-sm">
            <Wrench className="size-4" /> Tools & actions <SoonTag />
          </DropdownMenuItem>
        )}

        <DropdownMenuItem disabled className="gap-2 text-sm">
          <Paperclip className="size-4" /> Attach a file <SoonTag />
        </DropdownMenuItem>

        <DropdownMenuSub>
          <DropdownMenuSubTrigger className="gap-2 text-sm">
            <Filter className="size-4" /> Pin a source
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent className="w-52">
            <DropdownMenuItem className="gap-2 text-sm" onClick={() => onPin(null)}>
              <Check className={cn('size-4', pinned ? 'opacity-0' : 'opacity-100')} /> Auto (let it route)
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            {sources.map((s) => (
              <DropdownMenuItem key={s.id} className="gap-2 text-sm" onClick={() => onPin(s.id)}>
                <Check className={cn('size-4', pinned === s.id ? 'opacity-100' : 'opacity-0')} /> {s.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuSubContent>
        </DropdownMenuSub>

        <DropdownMenuSeparator />
        <DropdownMenuLabel className="flex items-center gap-2 text-xs font-normal text-muted-foreground">
          <Cpu className="size-3.5" /> Model: <span className="font-medium capitalize text-foreground">{mode}</span>
        </DropdownMenuLabel>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function SoonTag() {
  return <span className="ml-auto text-[9px] uppercase tracking-wide text-muted-foreground">soon</span>;
}
