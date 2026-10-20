# Upstream bundle and local overlay

- Source: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
- Installed from `ui-ux-pro-max-cli` version `2.15.0` on 2026-10-16 using
  `uipro init --ai codex`.
- Kept the `ui-ux-pro-max` bundle only; the CLI's unrelated bundled skills were
  removed. Moved this bundle to the repository's `.codex/skills/` root and
  updated command paths in `SKILL.md` accordingly.
- License: upstream MIT license included as `LICENSE`.
- The upstream stack list has no Streamlit-specific entry. Apply its general
  web accessibility, layout, typography and motion guidance to this app.
- `SKILL.md`, `data/` and `scripts/` retain the upstream UI/UX Pro Max catalog
  except for the short link to this repository's overlay.
- `references/grounded-travel-planner.md` is repository-local guidance. It
  records accepted Travel Planner UI constraints and evidence rules; it is not
  upstream material and must not be presented as such.
