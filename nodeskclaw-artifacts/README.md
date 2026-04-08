# Root-Level NoDeskClaw Artifacts

This directory contains extracted image build assets from `projects/nodeskclaw`
for local customization and standalone iteration.

## Current layout

- `nanobot-image/`: DeskClaw-customized nanobot image build context
  - Includes copied runtime resources (`deskclaw-resources/`)
  - Includes copied webui patches (`patches/nanobot-webui/`)
  - Includes startup/patch scripts (`scripts/`)

## Notes

- This is a copied workspace for packaging/build orchestration.
- Source product code under `projects/` is not modified by using this directory.
