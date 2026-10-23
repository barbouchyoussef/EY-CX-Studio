# Accessibility: EY CX Studio

## 1. Accessibility Goal

EY CX Studio should be usable by consultants and stakeholders with diverse abilities. Accessibility should be considered part of product quality, especially for forms, reports, dashboards, and chat workflows.

## 2. Target Standard

Use WCAG 2.1 AA as the practical target for interface behavior and visual readability.

## 3. Requirements

- Text must have sufficient contrast against backgrounds.
- Interactive elements must be keyboard reachable.
- Focus states must be visible.
- Form inputs must have labels or accessible names.
- Buttons and links must have clear purpose.
- Error messages must be associated with relevant inputs where practical.
- Charts should include readable labels and surrounding textual explanation.
- Loading states should not trap keyboard users.

## 4. Module Considerations

| Area | Accessibility Need |
|---|---|
| Authentication | Clear labels, error messages, and keyboard flow. |
| Assessment chat | Keyboard input, readable messages, and clear progress. |
| Reports | Heading hierarchy and readable chart descriptions. |
| Desk research upload | Clear file requirements and upload status. |
| Social listening charts | Labels and non-color-only interpretation. |
| Issue log | Scannable issue cards and accessible export actions. |
| Admin tables | Keyboard-friendly controls and clear table headings. |

## 5. Content Accessibility

- Avoid unexplained acronyms.
- Keep instructions short.
- Use headings to break long reports.
- Do not rely only on color to communicate severity or status.

## 6. Testing Checklist

- Navigate key flows with keyboard only.
- Check visible focus states.
- Check contrast for text and charts.
- Verify form labels.
- Verify buttons have accessible names.
- Review reports for heading order.

## 7. Known Follow-Up

A full automated accessibility audit is not currently documented. It should be added before broader production rollout.
