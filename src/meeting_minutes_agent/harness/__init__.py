"""C10 -- the evaluation/light-off harness.

:mod:`.episode` (the light-off entry point) imports
:mod:`meeting_minutes_agent.controller.loop`, which imports openjiuwen at
module level -- so it is NOT re-exported from this ``__init__``; import it
explicitly (``from meeting_minutes_agent.harness.episode import
run_episode``), the same discipline
:mod:`meeting_minutes_agent.client`/:mod:`meeting_minutes_agent.controller`
already use for their own openjiuwen-dependent modules. This keeps this
package importable with openjiuwen absent (zero-dependency gate: openjiuwen
never enters ``pyproject.toml``).
"""

from __future__ import annotations
