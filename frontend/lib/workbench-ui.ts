// Shared Workbench chrome tokens.
//
// Every response type — chart, table, KPI, brief, clarification, refusal, error — wears the
// same badge, the same chip and the same inset spacing. Keeping the class strings here is
// what stops one card type from quietly drifting a pixel or two away from the rest.

export const SOURCE_LABELS: Record<string, string> = {
  db: 'Loan book',
  macro: 'Macro',
  competitive: 'Competitive',
  regulatory: 'Regulatory',
  knowledge: 'Banking concepts',
  schema: 'Schema',
};

export const sourceLabel = (source: string) => SOURCE_LABELS[source] ?? source;

/** Source badge: one height, one radius, one type scale wherever a source is named. */
export const SOURCE_BADGE =
  'h-5 shrink-0 rounded-md px-1.5 text-[10px] font-medium uppercase tracking-wide';

/** Follow-up / example question chips under a clarification or refusal. */
export const SUGGESTION_CHIP = 'h-7 rounded-lg px-2.5 text-xs font-medium';

/** Gap between a block and the chips or badges that belong to it. */
export const BLOCK_GAP = 'mt-3';

/** Gap between two major blocks inside one card body. */
export const SECTION_GAP = 'mt-4';
