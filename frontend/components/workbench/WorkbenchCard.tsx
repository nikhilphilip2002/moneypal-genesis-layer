'use client';

import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { SOURCE_BADGE, sourceLabel } from '@/lib/workbench-ui';

// The one card shell every source answer wears. Density is the whole point: the header is a
// single tight row, and anything secondary (SQL, full tables, long context) lives behind the
// collapse so the answer itself fits a viewport. Source is always badged so a glance tells
// you where a number came from.
//
// This shell owns the outer edge — radius, border, clipping and shadow — and nothing inside
// it draws a second one. Children get a nested treatment (lighter border, no shadow) so a
// panel within a card never reads as a card within a card.

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
  const Header = collapsible ? 'button' : 'div';

  return (
    <div
      className={cn(
        'overflow-hidden rounded-2xl border border-border/70 bg-card text-card-foreground shadow-sm shadow-black/[0.025]',
        className,
      )}
    >
      <Header
        {...(collapsible
          ? { type: 'button' as const, onClick: () => setOpen((o) => !o), 'aria-expanded': open }
          : {})}
        className={cn(
          // The colour is stated rather than inherited: a <button> header would otherwise
          // fall back to the UA's `buttontext` and go dark-on-dark in the dark theme.
          'flex min-h-[3.25rem] w-full items-center gap-2.5 bg-gradient-to-r from-muted/35 to-transparent px-4 py-3 text-left text-card-foreground',
          collapsible && 'select-none transition-colors hover:bg-muted/25',
        )}
      >
        <Badge variant="secondary" className={SOURCE_BADGE}>
          {sourceLabel(source)}
        </Badge>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold leading-5">{title}</div>
          {subtitle && <div className="truncate text-xs leading-4 text-muted-foreground">{subtitle}</div>}
        </div>
        {collapsible && (
          <ChevronDown
            aria-hidden
            className={cn('size-4 shrink-0 text-muted-foreground transition-transform', open && 'rotate-180')}
          />
        )}
      </Header>
      {open && <div className="border-t border-border/60 p-4">{children}</div>}
    </div>
  );
}
