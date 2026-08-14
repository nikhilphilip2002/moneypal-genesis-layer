'use client';

import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

// The one card shell every source answer wears. Density is the whole point: the header is a
// single tight row, and anything secondary (SQL, full tables, long context) lives behind the
// collapse so the answer itself fits a viewport. Source is always badged so a glance tells
// you where a number came from.

const SOURCE_LABELS: Record<string, string> = {
  db: 'Loan book',
  macro: 'Macro',
  competitive: 'Competitive',
  regulatory: 'Regulatory',
  knowledge: 'Banking concepts',
  schema: 'Schema',
};

type Props = {
  source: string;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
  collapsible?: boolean;
  className?: string;
};

export default function WorkbenchCard({
  source,
  title,
  subtitle,
  children,
  defaultOpen = true,
  collapsible = true,
  className,
}: Props) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={cn('overflow-hidden rounded-2xl border border-border/70 bg-card text-card-foreground shadow-sm shadow-black/[0.025]', className)}>
      <div
        className={cn(
          'flex items-center gap-2.5 bg-gradient-to-r from-muted/35 to-transparent px-4 py-3',
          collapsible && 'cursor-pointer select-none',
        )}
        onClick={collapsible ? () => setOpen((o) => !o) : undefined}
      >
        <Badge variant="secondary" className="shrink-0 text-[10px] font-medium uppercase tracking-wide">
          {SOURCE_LABELS[source] ?? source}
        </Badge>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold leading-tight">{title}</div>
          {subtitle && <div className="truncate text-xs text-muted-foreground">{subtitle}</div>}
        </div>
        {collapsible && (
          <ChevronDown
            className={cn('size-4 shrink-0 text-muted-foreground transition-transform', open && 'rotate-180')}
          />
        )}
      </div>
      {open && <div className="border-t border-border/60 px-4 py-4">{children}</div>}
    </div>
  );
}
