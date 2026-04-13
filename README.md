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
- headless cloud lifecycle commands for connect, proxy preflight, and disconnect
- Weave create loop that authors a workflow, validates it, records an MP4, and
  packages evidence artifacts
- Weave v0.2 workflow intelligence:
  - cloud preflight classification for remote GPU failures
  - visual source-similarity proof from input video to recording
  - workflow template candidates from known Scope graph families
  - node/port/role compatibility reports
  - bounded runtime repair retry before final failure
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

Finish live remote GPU retry validation once the Daydream cloud proxy is
responding. The harness can now start and stop the remote path headlessly, but
remote proof still requires the proxy to accept workflow API calls and the
runtime report to show `session_start.cloud_mode=true`.

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
daydream-workflow-harness cloud-connect \
  --base-url http://127.0.0.1:52178 \
  --wait \
  --pipeline-id gray \
  --output /tmp/scope-cloud-connect.json

daydream-workflow-harness smoke-validate authored-workflow.json \
  --base-url http://127.0.0.1:52178 \
  --runtime-mode cloud \
  --output /tmp/scope-cloud-smoke-report.json

daydream-workflow-harness cloud-disconnect \
  --base-url http://127.0.0.1:52178
```

`--runtime-mode cloud` checks `/api/v1/cloud/status`, loads the pipeline through
the connected remote backend, starts the graph session, and requires
`session_start.cloud_mode=true`.

`connected=true` only proves the cloud WebSocket is open. `cloud-connect --wait`
also probes the cloud proxy, including `/api/v1/webrtc/ice-servers` and
`/api/v1/models/status` for any supplied `--pipeline-id`.

For authenticated remote inference, provide credentials through environment
variables instead of command-line flags. `cloud-connect` reads
`DAYDREAM_API_KEY`, `DAYDREAM_SCOPE_CLOUD_API_KEY`, or `SCOPE_CLOUD_API_KEY`
for the API key, and `DAYDREAM_USER_ID`, `DAYDREAM_SCOPE_USER_ID`, or
`SCOPE_CLOUD_USER_ID` for the user id. The Scope desktop app can also supply
its own configured `SCOPE_CLOUD_APP_ID`; otherwise set
`DAYDREAM_SCOPE_CLOUD_APP_ID` or `SCOPE_CLOUD_APP_ID`.

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
  --catalog catalog.json \
  --runtime-mode cloud \
  --input-video /tmp/scope-input.mp4 \
  --output-dir /tmp/weave-run
```

For cloud runtime tests, prefer a cached `--catalog` file. `--base-url-catalog`
fetches `/api/v1/pipelines/schemas`; while cloud is connected, Scope proxies
that endpoint to the remote backend and an unhealthy cloud proxy can fail before
workflow execution starts.

The Weave run writes:

- `workflow.json`: compiled Scope workflow
- `authoring-result.json`: intent, IR, repair, and structural validation report
- `runtime-record-report.json`: runtime session and recording report
- `recording.mp4`: Scope record-node output when runtime validation succeeds
- `contact-sheet.jpg`: sampled visual review sheet when `ffmpeg` is available
- `weave-report.json`: combined pass/fail report and artifact index

Use `--require-input-source` when you want the run to fail unless Scope session
metrics report `input_source_enabled=true`. Treat that as a conservative machine
gate. Without that flag, a run with an input video still counts as
graph/runtime/recording proof, and the report warns when metrics do not verify
source ingestion. Visual artifacts remain part of the review contract.

Rank candidate workflow templates for an intent:

```bash
daydream-workflow-harness weave-evaluate-candidates intent.json \
  --catalog catalog.json \
  --output-dir /tmp/weave-candidates \
  --output /tmp/weave-candidates.json
```

Add `--run-runtime --input-video /tmp/scope-input.mp4` to execute each compatible
candidate and attach runtime/source-proof evidence to the ranking.

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
