# Native desktop design assets

Source: [tiki Figma](https://www.figma.com/design/jfQdgEwHlOaAqwSfHh8MO8?node-id=2011-609), exported 2026-11-01 through the Figma MCP. These files are local and bundled; no temporary asset URLs are used at runtime.

| File | Source node / slot | Display geometry |
|---|---|---|
| header.png | Common/AppHeader `2011:70` | 70 × 21 |
| orb-original-base.png | GenerateButton ellipse `2007:1386` | 196 × 196, source is 2×, layer opacity .72 |
| orb-original-glow.png | GenerateButton ellipse `2007:1414` | 158 × 158, source is 2×, layer opacity .72 |
| orb-face.svg / .png | GenerateButton/Subtract `2011:113` | 84 × 81 including effect bounds |
| settings.svg / .png | Main settings icon `2011:474` | 15 × 15 |
| persona-source.png, persona-mask.svg, persona.png | Persona `2023:1354` | 51 × 48 with the original 50 × 50 mask and crop |

SVG-derived PNGs were rasterized with Edge at device scale 1 on a transparent background using `apps/desktop/packaging/figma_assets.html`; the SVG root dimensions are unchanged. The rasterized sprites occupy `(0,0,84,81)`, `(100,0,115,15)`, `(140,0,191,48)`. Keep source SVG/PNG files in the repository. The installer includes the source SVG/PNG files along with the original app logo SVG.

`apps/desktop/panel.py` retains the two background paints in source order and a separate Glass Effect layer. Tk does not support Figma's live desktop refraction, dispersion, or per-widget backdrop blending. The current renderer composites against a neutral dark backdrop and approximates the glass edge light; it does **not** reproduce the full GLASS optical effect or external shadow. It never takes screenshots to render the background. This limitation is not a change to the Figma source values.
