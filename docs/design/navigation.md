# Responsive navigation

UX-03C (#97) adopts the shared Sage foundation for navigation only. Existing
feature pages retain their own typography, cards, dialogs and workflow layout.

The shared partial uses a native `details` / `summary` disclosure labelled
ForeView Menu, with semantic Financial records, Projection and Administration
groups. Native Enter/Space activation and expanded-state accessibility work
without JavaScript. Active destinations use `aria-current="page"`; transactions
also retain the parent Assets section cue. The disclaimer page retains a visual
About section cue without marking the different About document as the current page.
The previously standalone setup page now includes the same shell without changing
its within-page setup tabs.

On viewports wider than 900 CSS pixels the expanded sidebar is 14rem and the
collapsed control rail is 9rem. Below that threshold it appears above the content
with wrapped groups rather than a horizontal strip. All links remain labelled;
there is no icon-only compact mode, overlay or focus trap. Logical properties
preserve RTL layout. A long desktop menu has local vertical scrolling.
Legacy feature content that still exceeds its available width scrolls within the
content column rather than extending the shared shell or hiding navigation.

The menu starts expanded on every page load, including narrow screens. Users can
collapse it with the disclosure control. Expansion is not persisted and is not
silently changed on resize. This deliberately simple first implementation avoids
introducing settings or a new JavaScript state controller. Future changes to
default expansion or persistence require explicit acceptance and tests.

Routes, query strings, browser history, language selection, top-right full help,
contextual help and About/disclaimer access are retained. No retirement workspace
link or new financial functionality is introduced.

`static/shared/navigation.css` loads after the legacy and foundation styles in
the shared partial. It scopes navigation rules to `fv-navigation` and shell rules
to containers directly containing that disclosure. Feature styles do not receive
the `fv-ui` scope. Token colors and component sizes remain owned by `ui.css`.

Browser acceptance in `tests/browser/navigation.mjs` runs through the existing
disposable bilingual/RTL fixture. It checks all eleven destinations, direct-entry
and refresh active cues, native keyboard disclosure, link traversal and focus
exit, 1280/800/390/320px layouts, local overflow, collapsed/expanded states and help
visibility. Existing workflow acceptance continues to check saved financial facts
and projection behavior. Before-state screenshots are in `ux-03a/baseline/`.
