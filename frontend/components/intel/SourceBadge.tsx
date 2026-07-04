'use client';

import { ExternalLink } from 'lucide-react';
import type { SourceRef } from '@/lib/api';
import { cn } from '@/lib/utils';

// Inline, always-visible link back to the original source document.
export default function SourceBadge({ source, className }: { source: SourceRef; className?: string }) {
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        'inline-flex max-w-full items-center gap-1 rounded-full border border-border/70 bg-card/80 px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary',
        className
      )}
      title={source.page ? `${source.document} — p.${source.page}` : source.document}
    >
      <span className="truncate">{source.document}{source.page ? ` · p.${source.page}` : ''}</span>
      <ExternalLink className="h-3 w-3 shrink-0" />
    </a>
  );
}
