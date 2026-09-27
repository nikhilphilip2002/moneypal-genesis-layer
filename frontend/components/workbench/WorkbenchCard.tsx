'use client';

import { cn } from '@/lib/utils';
import { sourceLabel } from '@/lib/workbench-ui';

type Props = {
  source: string;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
};

export default function WorkbenchCard({ source, title, subtitle, children, className }: Props) {
  return (
    <section className={cn('space-y-3', className)}>
      <header className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        <span className="text-xs text-muted-foreground">{sourceLabel(source)}</span>
        {subtitle && <span className="text-xs text-muted-foreground">· {subtitle}</span>}
      </header>
      {children}
    </section>
  );
}
