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

## Layer Model

### Capability Catalog

The catalog describes what the harness knows about Scope:

- pipelines
- plugins
- declared ports
- usage role
- media capabilities
- environment constraints

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

## Why This Shape

Scope workflows are not just prompts.
They are graph-shaped media programs with pipeline stages, port wiring, and execution context.

An agent can be reliable here only if it reasons through the workflow in smaller steps.

