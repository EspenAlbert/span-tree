from __future__ import annotations

from types import TracebackType
from typing import Optional, Type

from typing_extensions import TypeAlias

EXTRA_NAME = "log_trace"
REF_SRC = "__REF_SRC"
REF_DEST = "__REF_DEST"
SPAN_STATUS_FIELD = "span_status"
SPAN_NAME_FIELD = "span_name"

STATUS_CREATED = "created"
STATUS_STARTED = "started"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
VALID_STATUSES = (STATUS_CREATED, STATUS_STARTED, STATUS_SUCCEEDED, STATUS_FAILED)
TS_START_FIELD = "ts_start"
TS_END_FIELD = "ts_end"
CALL_LOCATION = "call_location"

# my own fields
ASYNC_TASK_NAME = "async_task_name"
ON_EXIT = "__on_exit"
PARENT_TASK_ID = "parent_task_id"
CHILDREN_TASK_IDS = "children_task_ids"
ErrorTuple: TypeAlias = tuple[
    Type[BaseException], BaseException, Optional[TracebackType]
]
