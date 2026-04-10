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

That keeps generation, repair, and validation separate.
The current repo also includes a blind-regeneration evaluator that scores planned pipeline chains against held-out published workflows.

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

This matters because a workflow can be structurally valid against the runtime catalog and still fail later in Scope's session startup path.

### Regeneration Evaluation

Blind regeneration needs a separate proof loop from workflow compilation.
The useful checks are:

- held-out case evaluation: prompt/name-derived intent in, expected pipeline chain out
- corpus benchmark: run the planner against a published workflow snapshot and compare predicted pipeline chains to the public ground truth

This keeps the question "can the agent regenerate known workflow families?" separate from "can the runtime execute them right now?"

### Blind Regeneration Evaluation

The evaluation layer answers a narrower but important question:

- given only public workflow text fields and source mode
- without using the workflow's actual pipeline chain as planner input
- can the harness regenerate the same pipeline chain

This is the right check for the authoring goal because "valid JSON" is weaker than "agent inferred the same workflow family from intent."

## Why This Shape

Scope workflows are not just prompts.
They are graph-shaped media programs with pipeline stages, port wiring, and execution context.

An agent can be reliable here only if it reasons through the workflow in smaller steps.

The harness therefore uses two evidence layers:

1. offline structure checks against a normalized catalog
2. live runtime checks against the actual Scope server when available

For authoring confidence, there is now a third layer:

3. blind-regeneration scoring against published workflow corpora
