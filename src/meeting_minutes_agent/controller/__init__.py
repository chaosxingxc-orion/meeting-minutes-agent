"""E7b -- the openJiuwen AgentLoop controller + MinutesTaskManager
(component C7, the true spine).

:mod:`.tasks` (the typed task model + deterministic ``TaskQueue``) and
:mod:`.dispatcher` (pure-logic dispatch: build a request, fold a response)
and :mod:`.assembly` (product assembly: the minutes + attributed-transcript
artifacts) import no openjiuwen and are always importable.

:mod:`.loop` (the openJiuwen episode workflow itself) imports openjiuwen at
module level and is therefore NOT re-exported here -- import it explicitly
(``from meeting_minutes_agent.controller.loop import ...``), exactly the
same discipline :mod:`meeting_minutes_agent.client`'s own ``__init__``
already documents for ``client.component``. This keeps this package (and
the whole repository test suite) importable with openjiuwen absent
(zero-dependency gate: openjiuwen never enters ``pyproject.toml``).
"""

from __future__ import annotations

from .assembly import (
    AttributedTranscriptArtifact,
    MinutesArtifact,
    build_attributed_transcript_artifact,
    build_minutes_artifact,
)
from .dispatcher import (
    GLOSSARY_ARM_CONSTRUCTORS,
    DispatchUnit,
    FoldResult,
    TaskDispatchNotImplementedError,
    build_dispatch_unit,
    find_self_introduction,
    fold_dispatch_result,
)
from .tasks import DEFAULT_TASK_PRIORITY, Task, TaskKind, TaskQueue, TaskQueueEmptyError

__all__ = [
    "DEFAULT_TASK_PRIORITY",
    "Task",
    "TaskKind",
    "TaskQueue",
    "TaskQueueEmptyError",
    "GLOSSARY_ARM_CONSTRUCTORS",
    "DispatchUnit",
    "FoldResult",
    "TaskDispatchNotImplementedError",
    "build_dispatch_unit",
    "find_self_introduction",
    "fold_dispatch_result",
    "MinutesArtifact",
    "build_minutes_artifact",
    "AttributedTranscriptArtifact",
    "build_attributed_transcript_artifact",
]
