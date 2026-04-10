# Daydream Workflow Harness

Daydream Workflow Harness is a small, public-ready scaffolding repo for building an AI-assisted workflow authoring tool for Daydream Scope.

The first version is intentionally narrow:

- build a normalized capability catalog
- capture typed user intent
- represent a workflow in an intermediate form
- validate and compile that intermediate form into a Scope workflow artifact

## Current Status

This repo currently contains the data model and architecture skeleton only.
The next implementation step is the compiler/validator layer.

## Package Layout

- `src/daydream_workflow_harness/schemas.py`: typed intent, catalog, and validation primitives
- `src/daydream_workflow_harness/ir.py`: workflow intermediate representation
- `docs/ARCHITECTURE.md`: implementation notes and system shape

## Why This Exists

Scope workflows are easier to author safely when an agent works through an intermediate model instead of generating raw workflow JSON directly.

The harness is meant to make that process:

- inspectable
- testable
- repeatable
- suitable for later public release

## Next Step

Add the compiler and validator, then wire the harness to real Scope workflow examples.

