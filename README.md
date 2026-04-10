# Daydream Workflow Harness

Daydream Workflow Harness is a small, public-ready scaffolding repo for building an AI-assisted workflow authoring tool for Daydream Scope.

The first version is intentionally narrow:

- build a normalized capability catalog
- capture typed user intent
- represent a workflow in an intermediate form
- validate and compile that intermediate form into a Scope workflow artifact
- validate authored workflows against a live Scope runtime

## Current Status

This repo currently contains:

- typed schemas and workflow IR
- a compiler and validator
- workflow reconstruction from real published Scope workflow shapes
- conservative repair and structured validation reporting
- a deterministic planner
- a minimal CLI, including an end-to-end authoring loop
- runtime smoke validation against a running Scope backend
- live runtime catalog extraction from `/api/v1/pipelines/schemas`
- held-out blind-regeneration evaluation
- published workflow corpus benchmarking

Current planner coverage is still deliberate and rule-based:

- `direct-restyle`: `longlive -> rife`
- `depth-conditioned`: `video-depth-anything -> longlive -> rife`
- `pixel-art-restyle`: `longlive`
- `text-generation`: `longlive`
- `text-restyle-with-frame-interpolation`: `longlive -> rife`
- `scribble-logo-restyle`: `scribble -> longlive -> rife`
- `masked-subject-preserving-restyle`: `yolo_mask -> longlive`
- `background-removal`: `video-depth-anything -> transparent`
- `face-swap`: `deeplivecam-faceswap -> rife`
- `flux-experimental`: `flux-klein`
- `grayscale-preview`: `gray`
- `passthrough-preview`: `passthrough`

## Package Layout

- `src/daydream_workflow_harness/schemas.py`: typed intent, catalog, and validation primitives
- `src/daydream_workflow_harness/ir.py`: workflow intermediate representation
- `src/daydream_workflow_harness/cli.py`: terminal entry point for catalog extraction and workflow validation
- `docs/ARCHITECTURE.md`: implementation notes and system shape

## Why This Exists

Scope workflows are easier to author safely when an agent works through an intermediate model instead of generating raw workflow JSON directly.

The harness is meant to make that process:

- inspectable
- testable
- repeatable
- suitable for later public release

## Next Step

Add planner expansion, workflow quality scoring, and deeper runtime checks once the authoring loop is stable.

## Quickstart

Extract a Scope catalog from an installed app bundle:

```bash
daydream-workflow-harness extract-catalog --output catalog.json
```

Extract the live catalog from a running Scope server:

```bash
daydream-workflow-harness extract-catalog --base-url http://127.0.0.1:52178 --output live-catalog.json
```

Validate a workflow JSON file against a catalog:

```bash
daydream-workflow-harness validate-workflow workflow.json --catalog catalog.json
```

Validate a workflow against the exact catalog exposed by a running Scope server:

```bash
daydream-workflow-harness validate-workflow workflow.json --base-url http://127.0.0.1:52178
```

Author a workflow from typed intent:

```bash
daydream-workflow-harness author-workflow intent.json --catalog catalog.json
```

Author a workflow against the exact pipelines exposed by a running Scope server:

```bash
daydream-workflow-harness author-workflow intent.json --base-url http://127.0.0.1:52178
```

Smoke-validate a workflow against a running local Scope server:

```bash
daydream-workflow-harness smoke-validate authored-workflow.json --base-url http://127.0.0.1:8000
```

Score the current planner on a held-out case set:

```bash
daydream-workflow-harness evaluate-regeneration tests/fixtures/blind_regeneration_public_cases.json
```

Benchmark the planner against a published workflow corpus snapshot:

```bash
daydream-workflow-harness benchmark-published published-workflows.json
```

Benchmark blind regeneration against a published workflow corpus:

```bash
daydream-workflow-harness evaluate-regeneration /path/to/published-workflows.json --output regeneration-report.json
```

On the published snapshot captured on `2026-04-10`, the current harness reached `16/16` exact pipeline-chain matches.

Catalog source precedence for `validate-workflow` and `author-workflow` is:

1. `--catalog`
2. `--base-url`
3. `--app-path`
4. no catalog source
