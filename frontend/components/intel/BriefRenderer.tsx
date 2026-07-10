'use client';

import { Fragment, type ReactNode } from 'react';
import { FileText } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * Uniform renderer for LLM-generated brief text.
 *
 * Backend prompts enforce a shared shape — `SECTION HEADING:` lines, `-` bullets
 * and inline `(document, p.X)` citations. Fact-vs-interpretation is marked at the
 * section level (see `INTERPRETIVE_HEADING`) rather than with mid-sentence labels.
 * This component parses that shape into consistent typography so every brief on
 * every page looks identical, instead of raw markdown leaking through.
 */

// Section headings that are the analyst's forward-looking judgment / recommendations
// rather than sourced fact — tagged once as "AI interpretation" on the heading.
const INTERPRETIVE_HEADING =
  /\b(SO WHAT|MOVES FOR|STRATEGIC|RECOMMEND|IMPLICATION|OUTLOOK|OBSERVATION|TAKEAWAY|WHAT THIS MEANS)\b/;

// Model output occasionally sprinkles these inline labels; we drop them and mark
// interpretation at the section level instead.
const INLINE_LABEL = /\s*\[(?:FACT|AI INTERPRETATION)\]\s*/g;

// ── inline parsing: **bold**, (document, p.X) ──

const INLINE_TOKEN =
  /(\*\*.+?\*\*|\((?:Source:\s*)?[^()\n]{2,90}?,\s*(?:p\.|page\s+)[\w?]+\))/g;

function renderInline(text: string): ReactNode[] {
  return text.split(INLINE_TOKEN).map((part, i) => {
    if (!part) return null;
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={i} className="font-semibold text-foreground">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (/^\((?:Source:\s*)?[^()\n]+,\s*(?:p\.|page\s+)[\w?]+\)$/.test(part)) {
      return (
        <span
          key={i}
          className="mx-0.5 inline-flex max-w-full items-center gap-1 truncate rounded-md border border-border/60 bg-muted/60 px-1.5 py-px align-middle text-[10px] font-medium text-muted-foreground"
          title={part}
        >
          <FileText className="h-2.5 w-2.5 shrink-0" />
          {part.replace(/^\((?:Source:\s*)?/, '').replace(/\)$/, '')}
        </span>
      );
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}

// ── block parsing: sections, bullets, paragraphs ──

type Block =
  | { kind: 'heading'; text: string }
  | { kind: 'paragraph'; text: string }
  | { kind: 'bullets'; items: string[] };

const HEADING_RE = /^(?:\*\*)?([A-Z][A-Z0-9 &/'()\-]{2,48})(?:\*\*)?\s*:?\s*(?:\*\*)?\s*(.*)$/;
const MD_HEADING_RE = /^(?:#{1,4}\s+|\*\*)(.+?)(?:\*\*)?\s*$/;

function isHeadingLine(line: string): { title: string; rest: string } | null {
  // ALL-CAPS section labels ("RISK WATCH:", "**Executive Summary**", "### Applicability")
  const caps = line.match(HEADING_RE);
  if (caps && caps[1] === caps[1].toUpperCase() && caps[1].length >= 4) {
    return { title: caps[1].trim(), rest: caps[2]?.trim() ?? '' };
  }
  const md = line.match(MD_HEADING_RE);
  if (md && line.length < 60 && !line.includes(':') && (line.startsWith('#') || (line.startsWith('**') && line.endsWith('**')))) {
    return { title: md[1].trim(), rest: '' };
  }
  return null;
}

function parseBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  let bullets: string[] | null = null;

  const flushBullets = () => {
    if (bullets?.length) blocks.push({ kind: 'bullets', items: bullets });
    bullets = null;
  };

  for (const raw of text.split('\n')) {
    const line = raw.trim();
    if (!line) {
      flushBullets();
      continue;
    }
    const bullet = line.match(/^(?:[-*•]|\d{1,2}\.)\s+(.*)$/);
    if (bullet) {
      bullets = bullets ?? [];
      bullets.push(bullet[1]);
      continue;
    }
    flushBullets();
    const heading = isHeadingLine(line);
    if (heading) {
      blocks.push({ kind: 'heading', text: heading.title });
      if (heading.rest) blocks.push({ kind: 'paragraph', text: heading.rest });
      continue;
    }
    blocks.push({ kind: 'paragraph', text: line });
  }
  flushBullets();
  return blocks;
}

export default function BriefRenderer({ content, className }: { content: string; className?: string }) {
  const blocks = parseBlocks(content.replace(INLINE_LABEL, ' '));
  return (
    <div className={cn('space-y-2.5', className)}>
      {blocks.map((block, i) => {
        if (block.kind === 'heading') {
          return (
            <p
              key={i}
              className="flex flex-wrap items-center gap-2 pt-1.5 text-[11px] font-bold uppercase tracking-[0.14em] text-primary first:pt-0"
            >
              {block.text}
              {INTERPRETIVE_HEADING.test(block.text) && (
                <span className="inline-flex items-center rounded-full bg-primary/10 px-1.5 py-px text-[9px] font-semibold normal-case tracking-normal text-primary">
                  AI interpretation
                </span>
              )}
            </p>
          );
        }
        if (block.kind === 'bullets') {
          return (
            <ul key={i} className="space-y-1.5">
              {block.items.map((item, j) => (
                <li key={j} className="flex items-start gap-2 text-sm leading-relaxed text-foreground/90">
                  <span className="mt-[8px] h-1.5 w-1.5 shrink-0 rounded-full bg-primary/70" />
                  <span className="min-w-0">{renderInline(item)}</span>
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={i} className="text-sm leading-relaxed text-foreground/90">
            {renderInline(block.text)}
          </p>
        );
      })}
    </div>
  );
}
