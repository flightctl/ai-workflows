---
name: bugfix:unattended
description: "Run autonomous bugfix workflow: diagnose, fix, test, review"
---
# /unattended

You MUST read `../skills/unattended.md` now and follow every step in it.

This command runs the autonomous bugfix workflow. It MUST produce artifact
files in `.artifacts/bugfix/{issue}/`. If no artifacts are written, the
workflow has failed.

Context provided by the user:

$ARGUMENTS
