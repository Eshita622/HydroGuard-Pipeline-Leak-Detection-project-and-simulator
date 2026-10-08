---
name: HydroGuard simulator ownership
description: Preserve the user's existing pipe-game simulator when handling simulator.html.
---

`artifacts/hydroguard/public/simulator.html` is the user's pipe-and-hammer game, even if it is absent from this checkout or appears untracked elsewhere. Do not create a substitute simulator page. Restore or inspect the user's repository version instead.

**Why:** the user explicitly clarified that this simulator is their existing game and asked that it not be replaced with a plain status/log page.

**How to apply:** Before touching this file, verify the current Git branch and recent remote content. If GitHub access is unavailable, preserve the file and ask the user to connect or sync the correct repository version.
