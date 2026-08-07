# Opus

A cold, monospace-forward Obsidian theme with a small, consistent color system. Three palettes drawn from the alchemical *Magnum Opus*, each tuned for light and dark. At home on desktop and mobile.

![Opus](https://raw.githubusercontent.com/opus-oss/obsidian-opus/main/screenshot.png)

## The idea

Color is used sparingly and always means something: one accent for structure and the active item, teal for good, clay for warning, and not much else. Headings are monospace on a fixed type scale, and they carry a tonally leveled color ramp: one hue per level at matched lightness, so a long note scans by structure without turning into a rainbow. Prefer hierarchy by value alone? One toggle brings the monochrome ladder back. The same accent marks the active file, the active tab, and the active table row, so the whole app reads the same way.

- **Monospace headings** on a fixed type scale, with a leveled tint ramp that reads as one family.
- **Consistent semantics:** accent, teal (good), clay (warning), used the same way across callouts, tasks, syntax, canvas, and boards.
- **Readable code in both views:** comments in muted slate, matched between Reading and Live Preview, tuned for light and dark.
- **A canvas that stays sharp** (see below).
- **Kanban as a first-class surface** (see below).
- **Mobile:** bigger touch targets, elevated nav drawers, and reading width and type tuned for a phone.
- **Plugins:** Dataview, Graph, Properties, tables, embeds, and print are all styled to match.

## Canvas and Kanban

Most themes treat Canvas as an afterthought. Opus rebuilds it: nodes are clean rounded cards with a color spine, groups are quiet framed regions with small mono labels, edges are thin with readable connector labels, and the six preset colors are remapped to a muted set where red means warning and green means good. The construction is blur-safe, so card text stays crisp at overview zoom, where most themes go soft. Image, note-embed, and web cards get the same treatment as text cards, and the color picker shows the palette you actually get.

Kanban gets the full board, not just the lanes: calm panels with mono uppercase headers and an amber count badge, cards that lift on hover, and rich card content. Tags render as quiet pills, due dates as small mono eyebrows, embedded images stay rounded and bounded, links and inline code match the rest of the theme. Tag and date colors you set in the plugin's own settings are left alone.

## Flavors

Switch them in Style Settings. Each is a full palette in light and dark, contrast-checked.

| Flavor | Stage | Palette |
| --- | --- | --- |
| **Prima Materia** | the first matter *(default)* | cool slate (dark) / warm latte (light), amber accent |
| **Nigredo** | the blackening | stark true-black, high contrast |
| **Citrinitas** | the yellowing | warm & cozy, Gruvbox-spirited (one accent) |

Each shot below is split diagonally — **light** above, **dark** below.

**Prima Materia** — the default. Cool slate in dark, warm latte in light.

![Prima Materia](https://raw.githubusercontent.com/opus-oss/obsidian-opus/main/screenshot-prima.png)

**Nigredo** — stark true-black, high contrast.

![Nigredo](https://raw.githubusercontent.com/opus-oss/obsidian-opus/main/screenshot-nigredo.png)

**Citrinitas** — warm and cozy, Gruvbox-spirited. The only flavor that colors its headings, tonally leveled so the hues read as one family.

![Citrinitas](https://raw.githubusercontent.com/opus-oss/obsidian-opus/main/screenshot-citrinitas.png)

## Install

**Community store:** Settings → Appearance → Manage themes → search **Opus**.

**Manual:** put `manifest.json` and `theme.css` in `YourVault/.obsidian/themes/Opus/`, then Settings → Appearance → Themes → **Opus**.

## Style Settings

Opus works on its own; the [Style Settings](https://github.com/mgmeyers/obsidian-style-settings) plugin adds a settings panel (Settings → Style Settings → Opus):

- **Flavor** — the three palettes above.
- **Accent color** — one picker for the accent; teal and clay stay fixed. Overrides the current flavor.
- **Layout & motion** — heading spacing, a compact mode, and a motion toggle.
- **Measure** — line width, font size, and line height.
- **Typography:** monochrome headings (the pre-2.8 value ladder); sans-serif headings; body and monospace font overrides.
- **Features** — hide the active-file/tab rails, flat code blocks, dark code in light mode, vivid canvas colors.
- **OLED & contrast** — true black and higher contrast (dark mode).
- **Mobile** — text scale and a leaner note header.

## Compatibility

Obsidian 1.4.0+. Light and dark, Reading and Live Preview, desktop and mobile, all three flavors.

## License

MIT.
