'use client';

import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronRight, Maximize2, X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface CompanyReportProps {
  markdown: string;
  loading?: boolean;
}

interface CollapsibleSectionProps {
  title: string;
  children: React.ReactNode;
  isOpen: boolean;
  onToggle: () => void;
}

function CollapsibleSection({ title, children, isOpen, onToggle }: CollapsibleSectionProps) {
  return (
    <div className="border-b border-white/30 dark:border-white/8 last:border-b-0">
      <button
        onClick={onToggle}
        className="flex items-center gap-2 w-full py-2.5 text-left hover:bg-white/30 dark:hover:bg-white/5 transition-all duration-200 rounded-lg px-1"
      >
        {isOpen ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0 transition-transform duration-200" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0 transition-transform duration-200" />
        )}
        <span className="font-semibold text-foreground">{title}</span>
      </button>
      {isOpen && (
        <div className="pb-3 pl-6">
          {children}
        </div>
      )}
    </div>
  );
}

const COMMON_PROSE = `prose prose-slate dark:prose-invert max-w-none
  prose-headings:text-foreground prose-headings:font-bold
  prose-h1:text-lg prose-h1:mb-2 prose-h1:pb-1 prose-h1:border-b prose-h1:border-border
  prose-h2:text-base prose-h2:mt-3 prose-h2:mb-1
  prose-h3:text-sm prose-h3:mt-2 prose-h3:mb-1
  prose-p:text-sm prose-p:text-foreground prose-p:leading-relaxed prose-p:my-1
  prose-a:text-primary prose-a:no-underline hover:prose-a:underline
  prose-blockquote:border-l-2 prose-blockquote:border-primary prose-blockquote:bg-primary/5 prose-blockquote:py-0.5 prose-blockquote:px-2 prose-blockquote:rounded-r prose-blockquote:text-sm
  prose-ul:list-disc prose-ul:pl-4 prose-ul:my-1
  prose-li:text-sm prose-li:text-foreground prose-li:my-0
  prose-table:w-full prose-table:border-collapse prose-table:border prose-table:border-border prose-table:text-xs
  prose-th:bg-muted/50 prose-th:p-1.5 prose-th:text-left prose-th:font-semibold prose-th:text-foreground prose-th:border prose-th:border-border
  prose-td:p-1.5 prose-td:border prose-td:border-border prose-td:text-foreground
  prose-strong:text-foreground prose-strong:font-semibold
  prose-code:bg-muted prose-code:text-foreground prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:font-mono
  prose-pre:bg-muted prose-pre:text-foreground prose-pre:rounded-xl prose-pre:p-4
`;

function parseMarkdown(markdown: string) {
  const sections: { title: string; content: string }[] = [];
  let currentSection = { title: '', content: '' };
  let headerContent = '';

  for (const line of markdown.split('\n')) {
    const h1Match = line.match(/^#\s+(.+)$/);
    const h2Match = line.match(/^##\s+(.+)$/);

    if (h1Match) {
      headerContent = line + '\n';
    } else if (h2Match) {
      if (currentSection.title) sections.push({ ...currentSection });
      currentSection = { title: h2Match[1], content: '' };
    } else {
      if (currentSection.title) {
        currentSection.content += line + '\n';
      } else {
        headerContent += line + '\n';
      }
    }
  }
  if (currentSection.title) sections.push(currentSection);
  return { sections, headerContent };
}

const TABLE_COMPONENTS = {
  table: ({ node, ...props }: any) => (
    <div className="overflow-x-auto my-2">
      <table {...props} className="min-w-full" />
    </div>
  )
};

export const CompanyReport = React.memo(function CompanyReport({ markdown, loading }: CompanyReportProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [mounted, setMounted] = useState(false);
  // Stable open-state map stored in a ref — survives re-renders caused by streaming
  const openStateRef = useRef<Record<string, boolean>>({});
  const [renderTick, setRenderTick] = useState(0);

  // Only use createPortal after hydration
  useEffect(() => {
    setMounted(true);
  }, []);

  // Lock body scroll when fullscreen is open
  useEffect(() => {
    if (isFullscreen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [isFullscreen]);

  // Close on Escape key
  useEffect(() => {
    if (!isFullscreen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsFullscreen(false);
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isFullscreen]);

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-24" />
        <Skeleton className="h-6 w-1/4" />
        <Skeleton className="h-48" />
      </div>
    );
  }

  if (!markdown) return null;

  const { sections, headerContent } = parseMarkdown(markdown);

  const getIsOpen = (title: string, idx: number): boolean => {
    if (title in openStateRef.current) return openStateRef.current[title];
    return idx < 2;
  };

  const toggleSection = (title: string, idx: number) => {
    openStateRef.current[title] = !getIsOpen(title, idx);
    setRenderTick(n => n + 1);
  };

  const ReportContent = () => (
    <div className={COMMON_PROSE}>
      {sections.length > 0 && headerContent.trim() && (
        <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
          {headerContent.trim()}
        </ReactMarkdown>
      )}
      {sections.length > 0 ? (
        <div className="mt-2 space-y-0">
          {sections.map((section, idx) => (
            <CollapsibleSection
              key={idx}
              title={section.title}
              isOpen={getIsOpen(section.title, idx)}
              onToggle={() => toggleSection(section.title, idx)}
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkBreaks]}
                components={TABLE_COMPONENTS}
              >
                {section.content.trim()}
              </ReactMarkdown>
            </CollapsibleSection>
          ))}
        </div>
      ) : (
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkBreaks]}
          components={TABLE_COMPONENTS}
        >
          {markdown}
        </ReactMarkdown>
      )}
    </div>
  );

  // ── Fullscreen overlay — rendered via portal to escape backdrop-filter stacking contexts ──
  const fullscreenOverlay = (
    <div
      className="fixed inset-0 z-[200] flex flex-col"
      style={{ isolation: 'isolate' }}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 dark:bg-black/60"
        style={{ backdropFilter: 'blur(4px)', WebkitBackdropFilter: 'blur(4px)' }}
        onClick={() => setIsFullscreen(false)}
        aria-label="Close fullscreen"
      />

      {/* Panel */}
      <div className="relative z-10 flex flex-col m-4 md:m-8 rounded-3xl overflow-hidden max-h-[calc(100vh-4rem)] glass-in"
           style={{
             background: 'rgba(255,255,255,0.82)',
             backdropFilter: 'saturate(200%) blur(28px)',
             WebkitBackdropFilter: 'saturate(200%) blur(28px)',
             border: '1px solid rgba(255,255,255,0.85)',
             borderTopColor: 'rgba(255,255,255,0.98)',
             boxShadow: '0 24px 80px rgba(221,122,58,0.18), 0 8px 32px rgba(221,122,58,0.10), 0 1px 0 rgba(255,255,255,0.95) inset',
           }}>
        {/* in dark mode override */}
        <style>{`
          @media (prefers-color-scheme: dark) { .fullscreen-panel { background: rgba(18,14,12,0.88) !important; border-color: rgba(255,255,255,0.10) !important; box-shadow: 0 24px 80px rgba(0,0,0,0.70), 0 1px 0 rgba(255,255,255,0.07) inset !important; } }
          .dark .fullscreen-panel { background: rgba(18,14,12,0.88) !important; border-color: rgba(255,255,255,0.10) !important; box-shadow: 0 24px 80px rgba(0,0,0,0.70), 0 1px 0 rgba(255,255,255,0.07) inset !important; }
        `}</style>

        {/* Header bar */}
        <div className="flex-shrink-0 flex items-center justify-between px-5 py-3.5"
             style={{
               borderBottom: '1px solid rgba(255,255,255,0.45)',
               background: 'rgba(255,255,255,0.50)',
               backdropFilter: 'saturate(180%) blur(16px)',
               WebkitBackdropFilter: 'saturate(180%) blur(16px)',
             }}>
          <h2 className="font-semibold text-foreground text-sm tracking-tight">Company Report</h2>
          <button
            onClick={() => setIsFullscreen(false)}
            className="flex items-center justify-center w-8 h-8 rounded-full transition-all duration-200"
            style={{
              background: 'rgba(0,0,0,0.08)',
              border: '1px solid rgba(255,255,255,0.50)',
            }}
            aria-label="Close"
          >
            <X className="h-4 w-4 text-foreground/70" />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-6 py-5">
            <ReportContent />
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Portal renders the fullscreen overlay at document.body level,
          escaping any ancestor backdrop-filter stacking contexts */}
      {mounted && isFullscreen && createPortal(fullscreenOverlay, document.body)}

      <Card className="w-full">
        <CardContent className="p-3">
          <div className="flex justify-end mb-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsFullscreen(true)}
              className="h-7 px-2.5 text-xs text-muted-foreground hover:text-foreground gap-1.5"
            >
              <Maximize2 className="h-3.5 w-3.5" />
              Expand
            </Button>
          </div>
          <ReportContent />
        </CardContent>
      </Card>
    </>
  );
});
