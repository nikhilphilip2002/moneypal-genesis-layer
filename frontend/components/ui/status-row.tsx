import type { LucideIcon } from 'lucide-react';

import { cn } from '@/lib/utils';

// One row shape for every warning, error, refusal, clarification, loading note and hint in
// the Workbench.
//
// The alignment rule is the whole reason this exists: the icon lives in a box whose height
// is exactly the first text line (20px at both sizes), so it is optically centred against
// that line while a wrapping message still starts flush at the top. Ad-hoc `mt-0.5` nudges
// only ever land on one font size and drift on every other.

export type StatusTone = 'neutral' | 'info' | 'warning' | 'danger';

const TONES: Record<StatusTone, { text: string; icon: string; surface: string; label?: string }> = {
  neutral: {
    text: 'text-muted-foreground',
    icon: 'text-muted-foreground',
    surface: 'border-border/60 bg-muted/35',
  },
  info: {
    text: 'text-foreground',
    icon: 'text-sky-600 dark:text-sky-400',
    surface: 'border-sky-500/25 bg-sky-500/[0.06]',
  },
  warning: {
    text: 'text-foreground',
    icon: 'text-amber-600 dark:text-amber-400',
    surface: 'border-amber-500/30 bg-amber-500/[0.06]',
    label: 'Warning:',
  },
  danger: {
    text: 'text-foreground',
    icon: 'text-destructive',
    surface: 'border-destructive/30 bg-destructive/[0.06]',
    label: 'Error:',
  },
};

type Props = {
  icon: LucideIcon;
  tone?: StatusTone;
  /** `md` is body copy (14px); `sm` is the dense in-panel note (12px). Both keep a 20px first line. */
  size?: 'sm' | 'md';
  /** Wrap the row in the tinted, bordered container used for standalone notices. */
  surface?: boolean;
  spin?: boolean;
  /** Screen-reader-only prefix. Defaults to the tone's own word so severity is never colour-only. */
  label?: string;
  className?: string;
  children: React.ReactNode;
};

export default function StatusRow({
  icon: Icon,
  tone = 'neutral',
  size = 'md',
  surface = false,
  spin = false,
  label,
  className,
  children,
}: Props) {
  const styles = TONES[tone];
  const srLabel = label ?? styles.label;

  return (
    <div
      className={cn(
        'flex items-start gap-2 leading-5',
        size === 'md' ? 'text-sm' : 'text-xs',
        styles.text,
        surface && cn('rounded-xl border px-3 py-2.5', styles.surface),
        className,
      )}
    >
      <span aria-hidden className={cn('flex h-5 shrink-0 items-center', styles.icon)}>
        <Icon className={cn(size === 'md' ? 'size-4' : 'size-3.5', spin && 'animate-spin')} />
      </span>
      <span className="min-w-0 flex-1">
        {srLabel && <span className="sr-only">{srLabel} </span>}
        {children}
      </span>
    </div>
  );
}
