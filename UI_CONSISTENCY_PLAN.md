# Workbench UI Consistency Plan

## Goal

Make every Workbench response visually consistent across charts, tables, KPIs, clarifications, refusals, errors, descriptive answers, source details, and the composer.

The reference screenshot showed three primary issues:

- Status icons sit slightly below the first line of text.
- Nested borders and separators appear clipped or visually broken near the Loan book card and Source details section.
- The composer gets an unnecessary blue focus treatment, and the send action is rendered as a filled blue tile with a white arrow.

## 1. Standardize status rows

Affected files:

- `frontend/components/workbench/WorkbenchTurn.tsx`
- `frontend/components/nlq/LineagePanel.tsx`

Create one shared status-row pattern for warning, error, refusal, clarification, loading, and informational states.

Requirements:

- Use a fixed icon wrapper with optical vertical centering.
- Remove inconsistent `mt-0.5` offsets.
- Standardize icon size, text size, gap, and line-height.
- Keep multi-line messages aligned from the top while keeping the icon centered against the first text line.
- Preserve accessible color contrast and descriptive labels.

## 2. Establish one border owner per card

Affected files:

- `frontend/components/workbench/WorkbenchCard.tsx`
- `frontend/components/nlq/LineagePanel.tsx`
- `frontend/components/nlq/ChartRenderer.tsx`

Make `WorkbenchCard` the owner of the outer radius, border, clipping, and shadow.

Requirements:

- Keep one continuous outer card border.
- Make the header separator span the full card width.
- Remove overlapping child borders and clipped child shadows.
- Give chart content, warnings, source details, and SQL sections consistent inset spacing.
- Use a consistent nested-panel treatment for LineagePanel without touching the parent card edge.
- Check both collapsed and expanded Source details states.

## 3. Normalize output-card spacing

Affected files:

- `frontend/components/workbench/WorkbenchTurn.tsx`
- `frontend/components/workbench/WorkbenchCard.tsx`
- `frontend/components/nlq/ChartRenderer.tsx`

Apply one spacing scale to all response types.

Requirements:

- Consistent card header height and padding.
- Consistent body padding for chart, table, KPI, refusal, error, and brief cards.
- Consistent source badge dimensions and typography.
- Consistent suggestion-chip height, radius, and spacing.
- No one-off margins that cause cards to drift vertically relative to each other.

## 4. Remove the blue composer focus border

Affected file:

- `frontend/components/workbench/Composer.tsx`

Replace the current blue `focus-within` border and ring with a subtle neutral focus state.

Requirements:

- No permanent blue border while typing.
- Preserve keyboard accessibility with a visible but neutral focus indicator.
- Keep the composer height and layout stable when focused.
- Avoid a focus ring that visually competes with the response cards.

## 5. Simplify the send control

Affected files:

- `frontend/components/workbench/Composer.tsx`
- `frontend/components/ui/button.tsx` if a reusable icon-button variant is needed.

Recommended treatment:

- Transparent background by default.
- Blue arrow icon only.
- Light blue hover surface.
- Slightly darker active surface.
- Muted disabled state.
- Preserve a minimum 36×36 clickable area.
- Keep the stop/cancel action visually consistent with the send action.

The outgoing user message bubble remains blue with readable white text because it clearly distinguishes user-authored messages from assistant responses.

## 6. Verify light, dark, and responsive states

Test the following combinations:

- Light theme and dark theme.
- Desktop, tablet, and mobile widths.
- Short and multi-line warning/error messages.
- Chart, KPI, table, clarification, refusal, error, and knowledge cards.
- Expanded and collapsed SQL/source details.
- Empty, loading, disabled, hover, active, and keyboard-focus states.
- Long user messages and long source labels.

## Acceptance criteria

- Icons align optically with their text in every status row.
- No card border terminates unexpectedly or doubles at nested sections.
- Source details and SQL panels follow the same edge and spacing system as the rest of the card.
- Typing in the composer does not create a distracting blue outline.
- The send action is an icon-first control without a permanent filled blue tile.
- User message bubbles remain readable and visually distinct.
- No layout shift occurs when focus, loading, expansion, or error states change.
- Frontend production build passes.
- Visual checks pass for all listed card types and responsive states.
