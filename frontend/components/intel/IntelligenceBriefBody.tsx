'use client';

import type { ReactNode } from 'react';

import BriefRenderer from '@/components/intel/BriefRenderer';
import SourceBadge from '@/components/intel/SourceBadge';
import type { IntelligenceResponse } from '@/lib/api';

export default function IntelligenceBriefBody({
  data,
  rendererClassName,
  footerAction,
}: {
  data: IntelligenceResponse;
  rendererClassName?: string;
  footerAction?: ReactNode;
}) {
  return (
    <>
      <BriefRenderer content={data.summary} className={rendererClassName} />

      {data.key_points?.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-t border-border/50 pt-3">
          {data.key_points.map((point, index) => (
            <span
              key={`${point}-${index}`}
              className="rounded-full border border-border/60 bg-muted/50 px-2.5 py-1 text-[11px] font-medium text-foreground/80"
            >
              {point}
            </span>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 pt-1">
        <SourceBadge source={data.source} />
        <span className="text-[11px] text-muted-foreground">Updated {data.last_updated}</span>
      </div>

      {footerAction && data.ai_note ? (
        <div className="flex items-start justify-between gap-3 border-t border-border/50 pt-3">
          <p className="text-xs italic text-muted-foreground">{data.ai_note}</p>
          {footerAction}
        </div>
      ) : footerAction ? (
        <div className="flex justify-end border-t border-border/20 pt-2">
          {footerAction}
        </div>
      ) : data.ai_note ? (
        <p className="border-t border-border/50 pt-3 text-xs italic text-muted-foreground">
          {data.ai_note}
        </p>
      ) : null}
    </>
  );
}
