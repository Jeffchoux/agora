# Agora interface

## Direction

A developer or project owner explores a new tool in a daytime browser, then
reads agent contributions for several minutes. Use a light, warm work surface
for reading and a deep green demonstration panel to separate example from live
work. The voice is concrete, questioning and candid. The interface is a working
table, not an autonomous-work claim or a dashboard of decorative metrics.

## System

Keep the system sans-serif family shared with the workspace. Strong size contrast
on the public introduction; compact hierarchy within the private console.
`ui.css` owns the paper, ink, accent, line, surface and muted tokens. `landing.css`
uses these tokens for public presentation and OKLCH for supporting dark-panel
neutrals. Lime identifies actions and selected examples, never fake progress.
Use visible keyboard focus, 44px control targets, wrapping controls and explicit
320/768/1024/1440px checks. Do not use motion to imply calls in static examples.

## Content and language

English is the initial interface regardless of browser locale. French is an
explicit, browser-local preference. Static leaf text stores `data-fr` alongside
English HTML. Dynamic console copy uses `messages.js` and named placeholders.
Never translate user content, source excerpts or historic model contributions.
No HTML injection for translations. A new language needs a complete catalogue,
an accessible selector and a browser regression test, not a DOM text replacer.

Examples are fictional authored scenarios with no model calls, not customer
claims. Repo tests and autonomous task execution must not be described as
implemented. The private console still requires the installation’s operator key.
