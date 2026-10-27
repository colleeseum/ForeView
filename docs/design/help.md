# Full help and contextual guidance

UX-03K (#105) applies the shared Sage foundation to the existing help catalog,
hierarchical category browser, keyword search and quick-reference tooltips.
`static/help/help.css` is loaded by the shared navigation partial. Styling stays
scoped to help surfaces and existing help controls, not the surrounding workspace.

## Interaction boundary

- The top-right help button opens full help with the existing page destination.
  Contextual help retains its article key. Unmapped pages select the first article
  in rendered category order, not the globally lowest article order.
- Full help uses a native modal dialog and the shared dialog controller. Search
  receives initial focus. Escape and the visible close button return focus to
  the invoker, with the top-right help button as fallback. An underlying native
  dialog remains open when help closes.
- Category disclosures retain native keyboard behavior. The active article has
  a visible border/background and `aria-current`. Selecting a topic focuses its
  tabbable article container so narrow-screen users reach the content without
  leaving the dialog controller's forward/reverse Tab cycle.
  Search and Close remain visible while the category/article region scrolls.
  Search results retain category paths; a polite status reports result count or
  no matches without moving focus out of search.
- Short tooltips remain distinct from full articles. Keyboard focus and click
  expose quick references, preserving existing `aria-describedby` values. Escape,
  focus departure and resizing dismiss them. Scrolling keeps them anchored while
  the trigger is visible, or dismisses them when it leaves the viewport. Late
  responses do not reopen dismissed help. Tooltips fit within the viewport.
- Existing feature-owned inline help inside Income and Expense import dialogs
  remains in those dialogs. Import instructions are not reduced to tooltips.

## Data and language contracts

The existing read-only `/api/help` response remains authoritative. No provider
registry, article text, route, financial calculation or persistence schema changes.
Article title, summary, body, category and provider language metadata retain their
per-field fallback. Text is rendered as text, not interpreted as HTML.

The help module retains eager catalog loading and reports errors when opened.
Changes to translation catalogs require restarting long-running application
processes and reloading browser pages, consistent with the shared localization
service cache.

## Acceptance

DOM tests cover category order, contextual selection, mixed-language metadata,
search/no-results, loading failures, stale response suppression, native cancel,
focus fallback, current-article semantics and tooltip descriptions.
The synthetic Chromium acceptance suite covers full help, Expense import
instructions, long provider articles, native dialog stacking, quick references,
keyboard focus/Escape, unchanged financial read models, and desktop/mobile/RTL
layouts. Generated screenshots use only synthetic data.

Reviewed evidence compares the [original help drawer](ux-03a/baseline/en-CA-desktop-contextual-help.png)
with the adopted presentation:

- [English desktop provider article](ux-03k/evidence/en-CA-1280-help-provider.png)
- [French mobile provider article](ux-03k/evidence/fr-CA-390-help-provider.png)
- [Synthetic RTL narrow article](ux-03k/evidence/ar-XB-320-help-provider.png)
- [Narrow quick-reference tooltip](ux-03k/evidence/en-CA-320-help-tooltip.png)
