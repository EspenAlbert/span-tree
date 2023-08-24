# span-trace
- see context info in [Github Repo](https://github.com/EspenAlbert/span-tree)

## Installation
`pip install span-tree`

## Goals

- Never have to look at log files again!
- Make error debugging easy by capturing context around errors and traces instead of only a traceback and locals
- Make health monitoring happening automatically
- Make performance monitoring easy by automatically tracking and report slow spans
- Support see once, annotate, and forget about it (instead of re-labeling the same error over and over...)

## Features in library

- trace-traces instead of flat log messages
    - a trace trace can have multiple "spans" as nodes
    - on each "node"
        - file_location
        - start and end timestamps
        - status: started|succeeded|failed
        - optional fields:
            - exit_error: if something fails without `except`
            - handled_errors: if we have errors caught with `except` and logged
            - level
    - each trace use a [ksuid](https://github.com/segmentio/ksuid) to ensure it is unique
    - each span has a name which is explicitly set or based on function name/call-context
    - traces are linked together when a new thread/task is started from an existing trace
- Smart printing
    - to terminal when running on localhost
    - only json when running on cloud/only normal logging no stdout/stderr?
    - smart at grouping together tasks and flushing before exit
- "test-mode": record all traces instead of just printing

## How to use the library

Basically, an Enhanced stdlib logger:

```python
from span_tree import get_logger

logger = get_logger(__name__)
logger.log(level,
           msg)  # level=debug|info|warning|error|critical, can also use `logger.info` logs will be attached to current span
logger(name: str, force_new_trace: bool = False, ** kwargs) -> `ContextManager[Span]`  # to start a new span/trace
logger.log_extra(msg: str = "", level: int = INFO, ** kwargs)  # to add attributes to span
```
