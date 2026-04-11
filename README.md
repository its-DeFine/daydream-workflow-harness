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
- Scope record-node validation that downloads an MP4 artifact from the graph path
- explicit remote GPU validation mode for a cloud-connected local Scope app
- Weave create loop that authors a workflow, validates it, records an MP4, and
  packages evidence artifacts
- live runtime catalog extraction from `/api/v1/pipelines/schemas`
- held-out blind-regeneration evaluation
- published workflow corpus benchmarking
- published workflow equivalence scoring beyond chain-only matching

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

Finish remote input-source proof and workflow quality scoring. The current
headless record path can produce MP4/contact-sheet artifacts, but Scope session
metrics may still report `input_source_enabled=false` even when a recorded local
validation visibly reflects the deterministic input video.

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

Smoke-validate a workflow through the local Scope app's remote GPU path:

```bash
daydream-workflow-harness smoke-validate authored-workflow.json \
  --base-url http://127.0.0.1:52178 \
  --runtime-mode cloud \
  --output /tmp/scope-cloud-smoke-report.json
```

`--runtime-mode cloud` checks `/api/v1/cloud/status`, loads the pipeline through
the connected remote backend, starts the graph session, and requires
`session_start.cloud_mode=true`.

Record-validate a workflow by injecting a graph `record` node from the sink and
downloading the resulting MP4:

```bash
daydream-workflow-harness record-validate authored-workflow.json \
  --base-url http://127.0.0.1:52178 \
  --input-video /tmp/scope-input.mp4 \
  --output-recording /tmp/scope-recording.mp4 \
  --output /tmp/scope-recording-report.json
```

`--input-video` rewires the first source node to `source_mode=video_file`, which
makes local validation deterministic without relying on a browser/WebRTC source.
The same command supports `--runtime-mode cloud` when the local Scope app is
already connected to the remote GPU backend with a valid Daydream user session.

Create a packaged Weave run from typed intent:

```bash
daydream-workflow-harness weave-create intent.json \
  --base-url http://127.0.0.1:52178 \
  --base-url-catalog \
  --runtime-mode cloud \
  --input-video /tmp/scope-input.mp4 \
  --output-dir /tmp/weave-run
```

The Weave run writes:

- `workflow.json`: compiled Scope workflow
- `authoring-result.json`: intent, IR, repair, and structural validation report
- `runtime-record-report.json`: runtime session and recording report
- `recording.mp4`: Scope record-node output when runtime validation succeeds
- `contact-sheet.jpg`: sampled visual review sheet when `ffmpeg` is available
- `weave-report.json`: combined pass/fail report and artifact index

Use `--require-input-source` when the claim must be strict video-to-video proof
from Scope metrics. That flag fails the run unless Scope session metrics report
`input_source_enabled=true`. Without that flag, a run with an input video still
counts as graph/runtime/recording proof, and the report warns when metrics do
not verify source ingestion. Visual artifacts remain part of the review contract.

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

Score deeper equivalence on the same published corpus:

```bash
daydream-workflow-harness evaluate-equivalence /path/to/published-workflows.json --output equivalence-report.json
```

Current published-corpus equivalence on the `2026-04-10` snapshot:

- chain exact: `16/16`
- input mode exact: `16/16`
- role exact: `16/16`
- LoRA count exact: `16/16`
- dimensions exact: `15/16`
- timeline entry count exact: `14/16`
- main parameter key set exact: `9/16`

Current live runtime proof on the local Scope server includes successful smoke validation for:

- `passthrough`
- `longlive`
- `longlive -> rife`
- `video-depth-anything -> longlive -> rife`

Current record-node proof also includes `input video file -> passthrough -> sink -> record`
with a non-empty MP4 downloaded from `/api/v1/recordings/headless?node_id=record`.
The remote GPU path has also been validated through the local MacBook Scope app:
pipeline load, graph session start with `cloud_mode=true`, frame capture, record
node start/stop, and MP4 download all completed for `passthrough`.

Catalog source precedence for `validate-workflow` and `author-workflow` is:

1. `--catalog`
2. `--base-url`
3. `--app-path`
4. no catalog source
