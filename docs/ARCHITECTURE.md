# Architecture

## Goal

Build a small harness that helps an AI agent author Daydream Scope workflows reliably.

## Core Idea

Do not let the agent write raw workflow JSON first.
Give it a typed intermediate layer:

1. capability catalog
2. intent schema
3. workflow IR
4. compiler
5. validator

That keeps generation, repair, validation, and evaluation separate.
The current repo also includes blind-regeneration and equivalence evaluators against published workflows.

## Layer Model

### Capability Catalog

The catalog describes what the harness knows about Scope:

- pipelines
- plugins
- declared ports
- usage role
- media capabilities
- environment constraints
- current runtime availability when sourced from a live Scope server

### Intent

The intent captures what the user wants in structured form:

- source type
- target effect
- realtime constraint
- local vs remote assumptions
- expected output
- known constraints

### Workflow IR

The IR is the machine-friendly plan for a Scope workflow.
It should represent:

- nodes
- edges
- session parameters
- port wiring
- execution hints

### Compiler

The compiler converts the IR into a Scope-compatible workflow artifact.

### Validator

The validator checks:

- required nodes exist
- ports match
- pipeline roles are sensible
- remote/local assumptions are compatible
- the workflow is structurally valid

### Runtime Probe

The runtime probe is separate from structural validation.
It checks whether a running Scope instance can:

- report healthy status
- load the requested pipeline set
- start a session from the compiled graph
- produce a frame
- optionally inject a `record` node from a sink and download a non-empty MP4

This matters because a workflow can be structurally valid against the runtime catalog and still fail later in Scope's session startup path.

Record validation is stricter than frame smoke validation. A frame capture proves
that Scope can render a current sink image; record validation proves that the
graph can route sink output through Scope's record-node recording path and
produce a portable video artifact for downstream review.

Remote GPU validation uses the same graph/session path through the local Scope
app with `--runtime-mode cloud`. In that mode the probe checks
`/api/v1/cloud/status`, loads the pipeline through the cloud-proxied runtime
API, starts the session, and requires `session_start.cloud_mode=true` before a
frame or recording can count as proof. The harness can initiate and close this
remote path through `cloud-connect` and `cloud-disconnect`, but a bare cloud
connection can report `connected=true` while the proxy API still cannot load a
workflow. Cloud readiness therefore uses proxy preflight checks, not status
alone.

Cloud runs should use a cached catalog unless the goal is to test the remote
schema endpoint. When Scope is connected to cloud, `/api/v1/pipelines/schemas`
is also cloud-proxied, so `--base-url-catalog` can fail before workflow
execution if the remote proxy is unhealthy.

When an input video is supplied, the probe records Scope session metrics around
session start, frame capture, and recording stop. Local Scope can report
`input_source_enabled`, while cloud relay runs can keep that field false even
after relaying video. For cloud relay validation the harness also accepts
`frames_to_cloud > 0` as source-delivery evidence. If both signals are false or
missing, the run should be treated as graph/runtime/record-node proof unless
the visual artifacts are separately reviewed.

### Weave Create Loop

The `weave-create` command packages the first agent-facing tool loop:

1. typed intent
2. rule-based plan and workflow compile
3. structural validation and conservative repair
4. optional live catalog compatibility check
5. runtime record validation
6. MP4 probe and contact-sheet generation
7. single combined report with required and optional checks

The important design choice is that Weave treats evidence as part of the output.
It does not only emit workflow JSON; it also emits the exact report and artifacts
needed to decide whether the generated workflow actually ran.

`--require-input-source` is the strict metric gate for video-to-video claims. It
keeps the public alpha honest by failing when Scope does not report active
source ingestion, while the recording and contact sheet remain the visual review
layer.

### Weave v0.2 Intelligence Layer

Weave v0.2 adds an intelligence layer around the v0.1 evidence wrapper:

1. cloud preflight classification separates disconnected credentials, connecting
   state, cloud proxy failure, and ready remote GPU state
2. visual source proof compares low-resolution grayscale frame samples from the
   input video and recorded output
3. workflow templates describe known Scope families such as `gray`,
   `longlive -> rife`, `video-depth-anything -> longlive -> rife`, and
   `scribble -> longlive -> rife`
4. compatibility analysis checks implicit source/sink/record ports, catalog
   pipeline ports, unknown pipeline references, and role ordering
5. runtime repair retry applies the conservative graph normalizer once before
   returning a final runtime failure
6. candidate evaluation can compile and optionally run multiple template graphs
   for the same intent, then rank them by template match, compatibility,
   runtime success, and source-proof similarity

This is still CLI-first. A UI should wait until the candidate/ranking evidence
contract is stable.

### Regeneration Evaluation

Blind regeneration needs a separate proof loop from workflow compilation.
The useful checks are:

- held-out case evaluation: prompt/name-derived intent in, expected pipeline chain out
- corpus benchmark: run the planner against a published workflow snapshot and compare predicted pipeline chains to the public ground truth

This keeps the question "can the agent regenerate known workflow families?" separate from "can the runtime execute them right now?"

### Published Equivalence Evaluation

Pipeline-chain accuracy is necessary but still incomplete.
The equivalence layer asks:

- given only public workflow text fields and source mode
- without using the workflow's actual pipeline chain as planner input
- can the harness regenerate the same chain
- can it also approximate prompt usage, timeline shape, dimensions, roles, and LoRA envelope

This is the right check for the authoring goal because "valid JSON" is weaker than "agent inferred and shaped the same workflow family from intent."

## Why This Shape

Scope workflows are not just prompts.
They are graph-shaped media programs with pipeline stages, port wiring, and execution context.

An agent can be reliable here only if it reasons through the workflow in smaller steps.

The harness therefore uses four evidence layers:

1. offline structure checks against a normalized catalog
2. live runtime checks against the actual Scope server when available
3. blind-regeneration scoring against published workflow corpora
4. published equivalence scoring across deeper workflow fields
