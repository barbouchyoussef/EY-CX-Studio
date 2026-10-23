# Design System: EY CX Studio

## 1. Design Direction

The interface should reflect an EY internal consulting tool: professional, restrained, data-focused, and easy to scan. Visual design supports analysis and decision-making rather than marketing.

## 2. Brand Foundations

- EY navy and yellow are the primary brand anchors.
- Brand tokens are defined in CSS and TypeScript.
- `npm run check:brand` ensures token consistency.
- Reports and dashboards should use brand colors carefully for emphasis and chart clarity.

## 3. UI Components

Shared components live in `frontend/src/components/ui/`.

Current shared component categories include:

- Navigation.
- Module headers.
- Chat components.
- Buttons and icon buttons.
- Share and add-to-project controls.
- Loading and skeleton states.
- Reusable visual primitives.

## 4. Layout Patterns

- Dashboards should use clear section hierarchy.
- Tables should support scanning and comparison.
- Reports should use structured sections and visual summaries.
- Forms should group related fields and validate early.
- Chat interfaces should distinguish user input, assistant output, and source context.

## 5. Typography and Spacing

- Use consistent heading hierarchy.
- Avoid oversized headings in operational views.
- Keep dense consulting workflows readable.
- Preserve enough spacing for reports and generated outputs.

## 6. Data Visualization

- Chart colors should come from shared brand constants.
- Numbers shown in reports must be computed by backend logic.
- Charts should have clear labels and legends.
- Avoid decorative charts that do not support decisions.

## 7. Interaction States

Every reusable control should account for:

- Default state.
- Hover and focus state.
- Disabled state.
- Loading state.
- Error state where relevant.

## 8. Design-System Acceptance Criteria

- Shared patterns are reused instead of duplicated.
- Brand tokens remain synchronized.
- UI remains readable in English and French.
- Buttons and links are distinguishable.
- Report outputs are client-review friendly.
