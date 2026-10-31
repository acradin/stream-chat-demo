# Tiki desktop design update

Source: user-provided `prompt.zip` (`prompt/css.txt` and seven reference PNGs) and Figma file `jfQdgEwHlOaAqwSfHh8MO8`.

## Scope

- Shared native desktop UI for Windows and macOS; prepare Linux native integration and verify against the available Ubuntu WSL environment.
- Main `2011:609` at 277×347, Settings `2011:610` at 420×491.
- Start `2030:1363`, Start1 `2030:1364`, Start2 `2030:1369`, Start3 `2030:1365`, StartEnd `2030:1366`.
- Component section `2004:981`: preserve original names, imagery, text sizes, padding, gaps, layered backgrounds and separate glass treatment.
- Retain generation, observation, output switching, service connection, hotkeys, settings and usage. Do not modify the web frontend.
- Preserve existing local settings and server credentials. Do not display mock usage as real usage or claim that onboarding grants CHZZK authorization.

## Work sequence

1. Read all screen/component context and retain local copies of original assets; keep screenshots as references only.
2. Extend existing panel/component rendering for compact layouts, gradient strokes and onboarding variants; use shared components across OS adapters.
3. Connect onboarding input, persona choices, broadcast link and completion persistence without blocking local demo mode on CHZZK authorization.
4. Complete Linux runtime/package integration with explicit display-server limits, and fix any actual Mac CI failures.
5. Run behavior tests and source/frozen smoke checks, compare all seven screens, refresh design export and documentation.

## Decisions to preserve

- Backend HTTPS and authenticated usage verified at `https://tiki-chat.duckdns.org`.
- Prior implementation pushed as `1518982`; Mac CI run `41222180932` is a baseline build, not the new design.
- Plus-plan restriction is pending user clarification; retain existing 1–5-person demo behavior unless the user chooses the restriction.
- Tk does not implement Figma's optical GLASS shader. Keep its separate layer/parameters and report actual rendering limits; do not equate ordinary blur with the Figma effect.
- Native Mac capture/permissions and real Linux compositor behavior require host validation beyond mocked contracts.
