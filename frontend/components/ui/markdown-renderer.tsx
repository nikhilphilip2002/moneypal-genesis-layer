import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { cn } from '@/lib/utils';

interface MarkdownRendererProps {
  content: string;
  variant?: 'light' | 'dark';
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, variant = 'dark' }) => {
  return (
    <div className={cn(
      "prose max-w-none break-words font-sans text-sm leading-relaxed",
      "prose-p:leading-relaxed prose-p:my-1",
      "prose-ul:my-1 prose-li:my-0",
      "prose-headings:my-2",
      variant === 'dark' 
        ? "prose-invert prose-headings:text-steel-100 prose-a:text-steel-blue-400 prose-pre:bg-steel-800/50 prose-code:text-steel-200" 
        : "prose-headings:text-steel-900 prose-p:text-steel-700 prose-a:text-steel-600 hover:prose-a:text-steel-900 prose-pre:bg-steel-50 prose-pre:text-steel-900 prose-code:text-steel-900"
    )}>
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{content}</ReactMarkdown>
    </div>
  );
};
