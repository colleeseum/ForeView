# Sage UI foundation

UX-03B (#96) supplies opt-in shared primitives for the direction approved in
[UX-03A](ux-03a/index.html). It does not restyle every workspace. Feature migrations
and responsive navigation remain separate UX-03 issues.

## Adoption and precedence

Load `/static/shared/ui.css` **after** `/static/style.css`. Add `fv-ui` to the
smallest cohesive migrated container. Tokens are defined only on that container;
no root, body, legacy class, route or financial model is changed. Every component
class has the `fv-` prefix. Do not copy color/spacing constants into feature CSS.
Use logical properties for direction-sensitive spacing and shared value formatters
for displayed money, dates and numbers. Keep input/storage syntax unchanged.

The component selectors deliberately outrank the old stylesheet's bare element
rules. Tables explicitly reset its sticky, clipped, nowrap cells. Do not nest an
unmigrated workflow inside `fv-ui` without reviewing its element-level inheritance.
The stylesheet can be loaded without opting any element in. Dialogs belong inside
their opted-in ancestor, even though the browser displays them in its top layer.

## Token contract

`static/shared/ui.css` is the authoritative value source. These roles summarize
usage rather than establish an independent theme definition:

| Role | Tokens / treatment |
| --- | --- |
| Typography | `--fv-font`: local system sans-serif; relative `--fv-type-*` roles for body, detail, caption and headings; `fv-number` uses tabular figures |
| Surfaces | `--fv-canvas`, `--fv-surface`, `--fv-surface-subtle`, `--fv-navigation` |
| Text | `--fv-text`, `--fv-muted`; explicit text remains readable, including secondary labels |
| Boundaries | `--fv-border` for decorative divisions; stronger `--fv-control-border` for input/button identification |
| Interactions | `--fv-primary`, `--fv-primary-hover`, `--fv-danger`, `--fv-danger-hover`, `--fv-focus`, `--fv-disabled` |
| Feedback | `--fv-info`, `--fv-success`, `--fv-warning`, `--fv-danger` and paired `*-surface` tokens |
| Spacing | `--fv-space-1/2/3/4/6/8`: quarter-rem scale, not per-feature constants |
| Shape / depth | `--fv-radius-control`, `--fv-radius-panel`, `--fv-shadow-panel`, `--fv-shadow-dialog` |

### Text-size preference

The intended preference is Small / Normal / Large, independently of compact table
density. The current showcase is the Large reference, not an approved final pixel
scale. Exact sizes and the default will be decided during adoption. Retain relative
typography and browser zoom; smaller text must not shrink control hit targets.

The saved Appearance / Text size setting belongs to UX-03J (#104). This foundation
does not implement a selector or persist a text-size preference. Subsequent adopters
must scale headings, labels, tables, dialogs and help consistently rather than
introducing per-feature size constants.

## Component contract

| Component | Usage / semantics |
| --- | --- |
| Buttons | Native `button.fv-button`, optional `--primary` or `--danger`; use actual `disabled`, not styling alone. Busy actions also use `aria-busy="true"`, a translated busy label and native disabled. Links use anchors, not fake buttons. |
| Fields | Visible `label.fv-field`, `fv-input` on native input/select/textarea; descriptions via `aria-describedby`; `aria-invalid="true"` with visible error text after validation. Preserve native constraints. Read-only and disabled remain distinct. |
| Cards / layout | `fv-card`, `fv-stack`, `fv-row`, `fv-grid`; no fixed card widths or clipped financial amounts. |
| Navigation tabs | `nav.fv-tabs` with normal links and `aria-current="page"`; in-page tabs require the consuming feature's full ARIA keyboard/tabpanel contract, not just `aria-selected` styling. |
| Tables | `fv-table` with caption, row/column headers and `fv-number` monetary cells. Optional `fv-table--compact` reduces cell padding, never font size or action targets. Put wide tables in a labelled `fv-table-scroll` region with `tabindex="0"` and a visible translated scrolling hint. |
| Feedback | `fv-feedback` plus `--success`, `--warning`, `--error`. Use `role="status"` for live success/busy updates, `role="alert"` for new blocking errors; do not announce every static informational card as an alert. Prefix states with translated text, not color alone. |
| Provenance | `fv-badge--source`, plain `fv-badge` for corrected values, `fv-badge--assumption`; visible words identify the meaning. Corrections are not errors; scenario assumptions are not facts. |
| Dialogs | Native `dialog.fv-dialog` labelled by a visible heading, autofocus on an appropriate field or heading, visible Cancel, `fv-dialog-actions`. Use `createDialog()`; do not toggle `open` directly or attach global Escape handlers. |
| Help | A short, dismissible tooltip is a quick reference. Contextual `data-help-article` buttons and full help retain the existing help module and searchable hierarchy. Long instructions must not become tooltips. |

Normal controls target 44 CSS pixels, including compact-table actions. This is a
project usability target, not a claim that WCAG AA always requires 44 pixels.
Focus has a visible 3px ring. Text pairs are tested at 4.5:1, and control borders /
focus against the white surface at 3:1. These checks are not a complete WCAG audit.

## Native dialog lifecycle

```javascript
import {createDialog} from '/static/shared/dialog.mjs';
const controller = createDialog(dialog, {fallbackFocus: addButton});
addButton.addEventListener('click', () => controller.open(addButton));
// A descendant type="button" data-dialog-close cancels without submitting.
// After a successful workflow, publish feedback in its originating context:
controller.close();
// On permanent teardown:
controller.destroy();
```

`showModal()` supplies background inertness, initial focus and Escape. The helper
also wraps reverse Tab from an initially focused, non-tabbable heading to the last
enabled control. Give a heading `tabindex="-1" autofocus` when initial focus should
announce its context rather than immediately enter a field. The helper
explicitly wraps Tab/reverse-Tab at the first/last enabled, visible control rather
than letting focus move to browser chrome.
Named radio groups count as one tab stop, using their eligible checked member.
Separate form owners and unnamed radios remain independent; native arrow-key
selection within a group is preserved.
The helper restores the invoker on close, or the supplied logical fallback if the
invoker was removed or disabled, including disabled state inherited from a fieldset.
It verifies that focus actually reached the invoker before accepting it; if focus
fails because the invoker became hidden, inert or otherwise unfocusable, it attempts
the supplied fallback instead. Callers must provide a usable logical fallback.
Tab events already consumed with `preventDefault()` by a descendant widget are left alone.
Computed `visibility: hidden` / `collapse` controls are excluded from tab edges.
Editable roots with empty, `true` or `plaintext-only` contenteditable values count
as native tab stops; nested editors require an explicit nonnegative tabindex.
Callers own validation, saving, dirty-form confirmation if required, and in-context
feedback. A native `cancel` listener may prevent Escape for an explicit workflow
policy; do not make dismissal impossible.
Never mix this controller and a legacy backdrop controller on the same dialog.
Use normal DOM tab order, not positive `tabindex` values. Composite widgets must
retain their own keyboard behavior and be verified in the adopting workflow.
Legacy account/help dialogs are not silently migrated by this foundation.

References: [native dialog](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog),
[W3C dialog interaction](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/),
[contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html),
[target size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html).

## Synthetic reference and verification

From the repository root:

```sh
PYTHONPATH=. .venv/bin/python docs/design/ux-03b/serve.py
```

Open the printed localhost URL. This launcher always creates a new temporary
synthetic runtime, never opens prod/dev, and removes it on exit. The showcase route
is registered only by development/test tooling, not production `create_app()`.
Change language through its Settings link and return to `/_design-system`.
No example action saves financial data. Only the dialog preview produces local
success feedback. Help buttons use the real help catalog and handlers.

`tests/test_ui_primitives.py` runs Chromium against that fixture in English,
French and synthetic RTL (French fallback), at 1280, 390 and 320px. It checks
labels/constraints, focus entry and bidirectional Tab wrapping, Escape/cancel,
focus return after invalid/successful preview, help roles, control size, token
contrast, table density/scrolling, local CSS isolation and unchanged financial
read models. Screenshots are generated in pytest's temporary evidence directory.
Node tests cover helper lifecycle and removed/disabled invokers. Full `make qa`
includes both through existing test discovery, without a separate manual gate.

Before-state evidence is retained in `ux-03a/baseline/`. The showcase demonstrates
the shared components, not a redesigned account, navigation or projection screen.
Feature-specific adoption still requires its own workflow tests and visual review.

Reviewed synthetic examples:

- [English desktop](ux-03b/evidence/en-CA-1280.png)
- [French mobile](ux-03b/evidence/fr-CA-390.png)
- [French mobile dialog with visible focus](ux-03b/evidence/fr-CA-390-dialog.png)
- [Synthetic RTL, French fallback](ux-03b/evidence/ar-XB-390.png)
