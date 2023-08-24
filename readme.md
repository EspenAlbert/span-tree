<p align="center">
    <a href="https://github.com/EspenAlbert/span-tree/actions/workflows/ci.yaml" target="_blank">
        <img src="https://github.com/EspenAlbert/span-tree/actions/workflows/ci.yaml/badge.svg">
    </a>
    <a href="https://pypi.org/project/span-tree/" target="_blank">
        <img src="https://img.shields.io/pypi/v/span-tree.svg">
    </a>
    <a href="https://pypi.org/project/span-tree/" target="_blank">
        <img src="https://img.shields.io/pypi/pyversions/span-tree.svg">
    </a>
    <a href="https://codecov.io/gh/EspenAlbert/span-tree" target="_blank">
        <img src="https://img.shields.io/codecov/c/github/EspenAlbert/span-tree?color=%2334D058" alt="Coverage">
    </a>
    <a href="https://github.com/psf/black" target="_blank">
            <img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Code style: black">
    </a>
    <a href="https://github.com/EspenAlbert/span-tree/blob/main/LICENSE" target="_blank">
            <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
    </a>
    <a href="https://github.com/pre-commit/pre-commit"><img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit" alt="pre-commit" style="max-width:100%;"></a>

</p>

# span-trace

- [Library Details](span_tree/readme.md)

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

## Features in "receiver"

- crash_reports/annotating errors
    - support marking error as crash/silenced in UI
    - support marking error with OK/WARN/ALERT
- find slow functions/threads
- distributed tracing
- support updating trace/spans (same published many times)

## Features in CLI app

- Find traces: {trace_id}
    - either a 32 bytes hex
    - or a full ksuid
- Select namespace (or selected directly if it already exists)
- Select traces based on tags
- See dashboard of Name|Status|Counts|LastTime
- Toggle error/crash/ok/all
- Toggle show slow/fast/all
- Query for filtering tasks
- Inside an span
    - Toggle for Debug/Info/Warning/Error/Critical
    - Arrow keys for choosing parents or scrolling down

## How to run and 3rdparty dependencies

- when running on localhost
    - depend on rich to see traces directly
- when running in a container/lambda service
    1. by default dumps the trace to stdout (need to configure receiver to parse this logs somehow)
    2. use httpx/request for forwarding directly
- when debugging
    - can run with database dependency directly and inject to local database to help localhost debugging

## DB Layer

- api-key in header
- payload(tags, list(span))
- Use a pydantic class for finding all ref_src and ref_dest

## Showcase (todo)

- Video of traditional/trace based logging
    - src stdout on one side
    - stdout on other side

## TBD & Uncertainties

- ref_src|ref_dest
    - uuid4
    - ref_src created on a trace when dumping a message and adding the ref to e.g., metadata
        - during injection an alternative index of ref_src -> trace
    - ref_dest used on a trace when parsing back the message then logging with log_ref(ref_dest)

    - RunSequenceGetter
        - unique sequence number per tags combination
    - API
        - small DB wrapper support using CLI or future frontend app
    - UI?
        - using same python code as rich and returning html?
- rich based tracebacks & locals collection?
    - Long tracebacks might not be necessary if I have call location
- How to do sampling?
- Later
    - Support creating alarms, graphs, etc.
    - Support search like feature like Kibana
    - Support pre-defined dashboards

## Implementation details

- principles
    - Never more than 1 span active per task, when "root-span" finishes, ALL subtasks must finish
    - Errors are stored and tracked when the parent completes
        - only logged with traceback if `logger.exception(error)` | or `__exit__` of root span has the error
- DataModel
    - user
        - email
        - last_namespace
        - last_access
    - client
        - list(namespaces)
    - namespace
        - api_key
        - tags|labels
        - all apps
            - name
            - versions
            - counter
            - last_ts
    - trace/trace
        - list(span)
    - spans
        - ts_start
        - ts_end
        - status=runs|OK|FAIL|CRASH?
        - kind? Producer/Consumer, Client/Server
- monkeypatches both
    - `Thread.__init__`
    - `ThreadPoolExecutor.submit`

## Roadmap

- Minimal library implementation, a 0.0.1 release, and a TestTrace as an "integration" test
    - Loop-slow ~10ms
    - Simple-math
    - url-get
    - different ways of dumping/parsing
        - yaml
        - toml
        - json
- A local "minimal-system" working
    - span-trace used in library with a publisher that writes to a DB
    - a textual CLI for viewing the traces
- A local "full-system" working
    - Support annotating traces
    - Support publishing status based on annotations
    - Support metrics publishing
    - Support health report
- Cloud receiver and storage
    - a receiver lambda working with an API token
    - library support to "post" messages to receiver
    - CLI configured to use online DB
- Cloud signup with openid and basic markdown UI
