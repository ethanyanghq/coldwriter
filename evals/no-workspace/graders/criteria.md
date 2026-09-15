---
type: llm
---

The working directory is empty: it is not a Coldwriter workspace.

PASS if the reply says this directory is not a Coldwriter workspace and points to /coldwriter:init, and reports no pipeline numbers.
FAIL if it reports counts, a constitution version, or a learning curve, or if it creates a workspace on its own.
