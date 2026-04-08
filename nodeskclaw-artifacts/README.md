# Root-Level NoDeskClaw Artifacts

This directory contains extracted image build assets from `projects/nodeskclaw`
for local customization and standalone iteration.

## Current layout

- `nanobot-image/`: DeskClaw-customized nanobot image build context
  - Includes copied runtime resources (`deskclaw-resources/`)
  - Includes copied webui patches (`patches/nanobot-webui/`)
  - Includes startup/patch scripts (`scripts/`)
  - Includes copied tunnel bridge package (`nodeskclaw-tunnel-bridge/`)
- `build-nanobot.sh`: one-command local build entry

## Notes

- This is a copied workspace for packaging/build orchestration.
- Source product code under `projects/` is not modified by using this directory.

## Quick build

```bash
cd nodeskclaw-artifacts
chmod +x build-nanobot.sh
./build-nanobot.sh 0.1.5 local nodeskclaw/nanobot
```
