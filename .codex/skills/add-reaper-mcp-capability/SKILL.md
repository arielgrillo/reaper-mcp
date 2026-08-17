---
name: add-reaper-mcp-capability
description: Add or extend REAPER MCP capabilities while preserving the existing MCP server, TCP/JSON bridge, REAPER API boundary, validation, deployment, commit, and push workflow.
---

# add-reaper-mcp-capability

## Purpose

Add or extend a REAPER MCP capability while preserving the repository's existing runtime boundary, validation workflow, deployment workflow, and Git workflow.

Use this skill when adding a new MCP tool or extending an existing MCP capability that requires REAPER access.

## Before Editing

1. Read `AGENTS.md`.
2. Inspect the current implementation before proposing changes.
3. Identify whether the capability is:

   * read-only;
   * mutating.
4. Identify which existing helpers can be reused.
5. Keep the smallest change that satisfies the requested capability.

Do not rewrite working code merely to make it stylistically different.

## Architecture Boundary

Preserve:

`MCP client -> MCP server -> TCP/JSON -> REAPER bridge -> REAPER API`

Responsibilities:

`src/reaper_mcp/`

* external Python process;
* MCP-facing tool definitions;
* argument typing;
* transport to the REAPER bridge;
* no direct REAPER `RPR_*` calls.

`reaper/mcp_bridge.py`

* executes inside REAPER;
* owns all direct `RPR_*` API usage;
* validates REAPER-specific targets;
* performs REAPER reads and writes;
* returns structured JSON responses.

Do not move REAPER-specific behavior into the MCP layer.

## Implementation Workflow

### 1. Inspect Existing Capabilities

Before editing, inspect:

* existing MCP tools;
* `COMMAND_HANDLERS`;
* bridge helpers;
* track, FX, parameter, or other domain validation helpers;
* response conventions;
* error handling.

Reuse existing helpers when they represent the same responsibility.

Do not duplicate validation or decoding logic unnecessarily.

### 2. Implement Bridge Capability

If REAPER API access is required:

* add or extend a focused handler in `reaper/mcp_bridge.py`;
* register new commands through `COMMAND_HANDLERS`;
* keep `process_request()` generic;
* use one-based indexes in public responses and requests;
* convert to REAPER zero-based indexes only inside the bridge;
* validate all user-provided indexes before using them.

Return structured errors for invalid input or failed REAPER operations.

### 3. Expose MCP Tool

Add or extend the corresponding tool in `src/reaper_mcp/`.

The MCP tool should:

* use typed arguments;
* have a concise, accurate description;
* pass REAPER-specific requests through the existing bridge client;
* avoid duplicating REAPER-specific logic;
* return structured results.

### 4. Preserve Raw and Human-Readable Values

When REAPER exposes raw internal values that are useful for future writes, preserve them.

When useful, add derived human-readable representations separately.

Examples:

* raw volume + dB;
* raw pan + percentage/direction;
* normalized FX parameter + formatted value.

Do not replace raw REAPER values with derived values when both are useful.

## Read-Only Capabilities

For read-only capabilities:

* do not mutate REAPER state;
* do not use APIs that temporarily change state merely to inspect data unless explicitly requested and justified;
* report API limitations instead of fabricating unavailable information.

Prefer focused queries over returning the entire project state unnecessarily.

## Mutation Capabilities

For mutation capabilities:

1. validate the target;
2. validate the requested value;
3. reject malformed or out-of-range input;
4. perform the smallest requested mutation;
5. read the resulting value/state back from REAPER;
6. return both requested and applied state when relevant;
7. report success only when the operation and read-back are valid.

Do not silently clamp values unless the REAPER API explicitly requires that behavior and the capability documents it.

Allow legitimate quantization or discrete parameter behavior when REAPER applies a value different from the exact requested normalized value.

Do not add additional mutations beyond the requested operation.

## Transport

Reuse the existing TCP/JSON bridge client.

Large responses must be read completely rather than assuming a single socket read contains the entire response.

Keep finite timeouts and useful connection failure behavior.

Do not add retries, framing protocols, or transport abstractions unless a demonstrated problem requires them.

## Error Handling

Return clear errors for cases such as:

* invalid track index;
* invalid FX index;
* invalid parameter index;
* invalid input value;
* unsupported operation;
* REAPER API failure;
* bridge connection failure;
* malformed bridge response;
* failed write;
* failed read-back.

Do not hide diagnostic information that is useful to the MCP caller.

## Validation

After changing external MCP code, run:

`uv run python -m compileall src`

If `reaper/mcp_bridge.py` changed, run:

`powershell -ExecutionPolicy Bypass -File scripts/deploy_reaper_bridge.ps1`

The deployment script must validate bridge syntax before copying it into REAPER's Scripts directory.

Do not deploy an invalid bridge.

Do not claim runtime validation against REAPER unless the capability was actually executed against a running REAPER instance.

## Git Completion

Follow `AGENTS.md`.

After successful validation and required deployment:

1. inspect `git status`;
2. stage only files belonging to the current task;
3. do not include unrelated working-tree changes;
4. create a concise commit message from the implementation summary;
5. push to the current branch's configured remote.

Do not invent a remote or upstream.

## Completion Report

Report:

* files changed;
* implementation summary;
* relevant REAPER APIs used;
* validation behavior;
* read-back behavior for mutations;
* known API limitations;
* validation results;
* bridge deployment result when applicable;
* commit hash and message;
* remote and branch;
* push result;
* whether runtime validation against REAPER was actually performed.

## Avoid

Do not introduce:

* unnecessary classes;
* inheritance;
* generic command frameworks;
* new routing systems;
* speculative abstractions;
* unrelated refactors;
* silent mutation;
* fabricated REAPER capabilities;
* broad project-state responses when a focused tool is sufficient.

Prefer the existing architecture and the smallest useful change.

## Backlog Update

Whenever a capability is added, completed, renamed, or materially changed:

* inspect `tasks/backlog.json`;
* update the corresponding task;
* mark it completed only when the implementation exists and validation succeeds;
* preserve stable task IDs;
* do not create duplicate capability entries;
* validate the JSON after editing;
* include the backlog update in the same commit when it belongs to the same capability task.
