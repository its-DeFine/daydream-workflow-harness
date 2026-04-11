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
frame or recording can count as proof. The local app must already be connected
to the remote backend with the same Daydream user session the UI uses; a bare
cloud connection can report `connected=true` while still failing signaling.

When an input video is supplied, the probe records Scope session metrics around
session start, frame capture, and recording stop. The current hard signal is
`input_source_enabled`. If that metric is false or missing, the run should be
treated as graph/runtime/record-node proof unless the visual artifacts are
separately reviewed. Local headless validation has produced input-derived
recordings while this metric still reported false, so this field is useful
diagnostic evidence, not a complete oracle.

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

`--require-input-source` is the strict gate for video-to-video claims. That keeps
the public alpha honest while remote cloud source ingestion is still being
debugged.

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
