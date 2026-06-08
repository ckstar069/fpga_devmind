"""Desktop Agent Shell — artifact viewer and interaction surface.

T009 scope: minimum viable desktop prototype.
T010 scope: rich concept trace views.

The desktop shell is a VIEWER and INTERACTION SHELL, not a source of
semantic truth.  All claims, evidence, and diagnostics originate from
the CLI pipeline (P1a/P1b).

Constraints:
  - No Web GUI (no browser-accessible URL, no Web server, no Web app).
  - No Vivado / synthesis / implementation / bitstream.
  - No modification of fpga_project_* target projects.
  - No API key loading or external LLM calls.
  - Read-only artifact viewer.
"""

from __future__ import annotations
