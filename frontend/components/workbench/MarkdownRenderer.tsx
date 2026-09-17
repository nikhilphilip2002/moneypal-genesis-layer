'use client';

import type { ComponentPropsWithoutRef } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/utils';

const components: Components = {
  h1: ({ className, ...props }: ComponentPropsWithoutRef<'h1'>) => (
    <h1 className={cn('pt-2 text-xl font-semibold tracking-tight text-foreground first:pt-0', className)} {...props} />
  ),
  h2: ({ className, ...props }: ComponentPropsWithoutRef<'h2'>) => (
    <h2 className={cn('pt-2 text-lg font-semibold tracking-tight text-foreground first:pt-0', className)} {...props} />
  ),
  h3: ({ className, ...props }: ComponentPropsWithoutRef<'h3'>) => (
    <h3 className={cn('pt-1.5 text-base font-semibold text-foreground first:pt-0', className)} {...props} />
  ),
  h4: ({ className, ...props }: ComponentPropsWithoutRef<'h4'>) => (
    <h4 className={cn('pt-1 text-sm font-semibold text-foreground first:pt-0', className)} {...props} />
  ),
  p: ({ className, ...props }: ComponentPropsWithoutRef<'p'>) => (
    <p className={cn('text-sm leading-7 text-foreground/90', className)} {...props} />
  ),
  ul: ({ className, ...props }: ComponentPropsWithoutRef<'ul'>) => (
    <ul className={cn('ml-5 list-disc space-y-1 text-sm text-foreground/90 marker:text-primary/70', className)} {...props} />
  ),
  ol: ({ className, ...props }: ComponentPropsWithoutRef<'ol'>) => (
    <ol className={cn('ml-5 list-decimal space-y-1 text-sm text-foreground/90 marker:font-medium marker:text-primary/80', className)} {...props} />
  ),
  li: ({ className, ...props }: ComponentPropsWithoutRef<'li'>) => (
    <li className={cn('pl-1 leading-7', className)} {...props} />
  ),
  strong: ({ className, ...props }: ComponentPropsWithoutRef<'strong'>) => (
    <strong className={cn('font-semibold text-foreground', className)} {...props} />
  ),
  em: ({ className, ...props }: ComponentPropsWithoutRef<'em'>) => (
    <em className={cn('italic text-foreground/90', className)} {...props} />
  ),
  a: ({ className, href, ...props }: ComponentPropsWithoutRef<'a'>) => (
    <a
      className={cn('font-medium text-primary underline decoration-primary/35 underline-offset-4 hover:decoration-primary', className)}
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      {...props}
    />
  ),
  blockquote: ({ className, ...props }: ComponentPropsWithoutRef<'blockquote'>) => (
    <blockquote className={cn('border-l-2 border-primary/40 pl-4 text-sm italic text-muted-foreground', className)} {...props} />
  ),
  code: ({ className, ...props }: ComponentPropsWithoutRef<'code'>) => (
    <code className={cn('rounded bg-muted px-1.5 py-0.5 font-mono text-[0.85em] text-foreground', className)} {...props} />
  ),
  pre: ({ className, ...props }: ComponentPropsWithoutRef<'pre'>) => (
    <pre
      className={cn(
        'max-w-full overflow-x-auto rounded-lg border border-border/60 bg-muted/60 p-3 text-xs leading-6',
        '[&_code]:bg-transparent [&_code]:p-0',
        className,
      )}
      {...props}
    />
  ),
  table: ({ className, ...props }: ComponentPropsWithoutRef<'table'>) => (
    <div className="max-w-full overflow-x-auto rounded-lg border border-border/60">
      <table className={cn('w-full border-collapse text-left text-xs', className)} {...props} />
    </div>
  ),
  thead: ({ className, ...props }: ComponentPropsWithoutRef<'thead'>) => (
    <thead className={cn('bg-muted/70 text-foreground', className)} {...props} />
  ),
  th: ({ className, ...props }: ComponentPropsWithoutRef<'th'>) => (
    <th className={cn('border-b border-border/70 px-3 py-2 font-semibold', className)} {...props} />
  ),
  td: ({ className, ...props }: ComponentPropsWithoutRef<'td'>) => (
    <td className={cn('border-b border-border/40 px-3 py-2 align-top last:border-b-0', className)} {...props} />
  ),
  hr: ({ className, ...props }: ComponentPropsWithoutRef<'hr'>) => (
    <hr className={cn('border-border/70', className)} {...props} />
  ),
};

/** Render model-provided Markdown without rewriting its source text. */
export default function MarkdownRenderer({ content, className }: { content: string; className?: string }) {
  return (
    <div className={cn('space-y-3', className)}>
      {/* Raw HTML stays disabled, so tool-like tags remain visible text. */}
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
