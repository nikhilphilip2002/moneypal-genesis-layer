'use client';

import Link from 'next/link';
import {
  Zap, MessageCircle, Building, Briefcase, Mail,
  Network, BarChart3, ClipboardCheck, ArrowRight, Lightbulb,
} from 'lucide-react';
import { APP_SECTIONS, type AppSection } from '@/lib/guide-content';
import type { UserRole } from '@/lib/useUserRole';
import { cn } from '@/lib/utils';
import { useState } from 'react';

const ICON_MAP: Record<string, React.ElementType> = {
  Zap, MessageCircle, Building, Briefcase, Mail, Network, BarChart3, ClipboardCheck,
};

const ROLE_BADGE: Record<string, string> = {
  admin:    'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300',
  manager:  'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300',
  standard: 'bg-muted text-muted-foreground',
};

function SectionCard({ section, onNavigate }: { section: AppSection; onNavigate: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const Icon = ICON_MAP[section.icon] ?? Zap;
  const restricted = section.roles.length === 1 && section.roles[0] !== 'standard';

  return (
    <div className="rounded-xl border border-border bg-card transition-colors hover:border-primary/40">
      <button
        onClick={() => setExpanded(v => !v)}
        className="flex w-full items-start gap-3 px-4 py-3 text-left"
      >
        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="h-4 w-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-foreground">{section.title}</span>
            {restricted && (
              <span className={cn('rounded-full px-1.5 py-0.5 text-[10px] font-medium', ROLE_BADGE[section.roles[0]])}>
                {section.roles[0]}
              </span>
            )}
          </div>
          <p className={cn('mt-0.5 text-xs text-muted-foreground leading-snug', !expanded && 'line-clamp-2')}>
            {section.description}
          </p>
        </div>
        <span className={cn('mt-1 shrink-0 text-muted-foreground transition-transform', expanded && 'rotate-90')}>
          <ArrowRight className="h-3.5 w-3.5" />
        </span>
      </button>

      {expanded && (
        <div className="border-t border-border px-4 pb-4 pt-3 space-y-3">
          {section.tips.length > 0 && (
            <ul className="space-y-1.5">
              {section.tips.map((tip, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
                  <Lightbulb className="mt-0.5 h-3 w-3 shrink-0 text-amber-500" />
                  {tip}
                </li>
              ))}
            </ul>
          )}
          <Link
            href={section.path}
            onClick={onNavigate}
            className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            Open {section.title}
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
      )}
    </div>
  );
}

interface Props {
  role: UserRole | null;
  onNavigate: () => void;
}

export function AppWalkthrough({ role, onNavigate }: Props) {
  const visible = APP_SECTIONS.filter(s =>
    role ? s.roles.includes(role) : s.roles.includes('standard')
  );

  return (
    <div className="space-y-3 pb-6">
      <p className="text-xs text-muted-foreground leading-relaxed">
        Tap any section to learn more and jump directly to it.
        {role && role !== 'standard' && (
          <> Sections marked <strong>admin</strong> or <strong>manager</strong> are role-restricted.</>
        )}
      </p>
      {visible.map((section, i) => (
        <SectionCard key={i} section={section} onNavigate={onNavigate} />
      ))}
    </div>
  );
}
