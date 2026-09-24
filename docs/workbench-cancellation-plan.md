# Workbench Cancellation Fix and Deployment Verification

## Confirmed defects

- The browser abort catch marks a turn done but leaves running trace steps and query records active, so the trace keeps showing "Model deciding next action".
- Cancelling the backend task during `_select` leaves the model trace step running in the persisted trace. Tool cancellation finalizes query records but can leave tool trace steps running.
- `proxy_ignore_client_abort off` is already Nginx's default. llama.cpp defers slot `erase` while a slot is processing, so neither proposed change is a proven way to stop generation.

## Implementation

1. On browser abort or stream failure, finalize running trace steps, pending query records, and the visible turn state. Preserve completed steps and results.
2. In the agent loop, catch `asyncio.CancelledError` around model selection, emit a terminal trace update, log the cancelled turn and round without prompt content, and re-raise cancellation.
3. On cancellation, finalize every running trace step and pending query record. Log cancellation at the stream driver so deployment logs show whether Stop reached the backend.
4. Add focused regression tests for model cancellation, tool cancellation, and stream shutdown. Run Workbench backend tests, Ruff, frontend tests, lint, and build.

## Deployment proof to collect

1. Start a long Workbench model response and press Stop. The UI should stop all trace animation immediately; refreshed history should contain no running trace steps.
2. Correlate the turn ID in backend logs. A cancellation log proves the browser disconnect reached the backend; a model-round cancellation log proves it reached `_select`.
3. Check llama-server's deployed version and its slot state or logs before and after Stop. If the backend logs cancellation but the slot stays processing, test that server build's disconnect handling and update its cancellation mechanism. If no backend cancellation log appears, investigate browser-to-Nginx-to-ASGI disconnect propagation.
4. Repeat while a database tool is running and confirm both the query registry and tool trace finish as cancelled/interrupted.

## Completion criteria

The UI and saved history contain no running steps after a stopped turn. The backend task ends promptly on disconnect. The deployed llama-server releases its active generation promptly, demonstrated by its own slot state or cancellation log; this last check requires the deployment environment.

## Current status

- Implemented local turn finalization, backend finalization of all running trace steps and unfinished query attempts, and cancellation logs. The model client closes its stream on cancellation; a focused test confirms closure without retry.
- A deployment test still showed animation and prompt processing after Stop. The follow-up adds an explicit authenticated `/workbench/cancel` request, keyed to the server turn ID, so backend cancellation does not depend only on stream disconnection. Saved traces now render unfinished steps as interrupted rather than spinning.
- Verified locally: 422 Workbench and LLM client tests, including ASGI disconnect and explicit cancellation tests, plus Ruff, frontend tests, lint, and production build pass.
- Awaiting deployment check: look for `Workbench cancel requested` with `cancelled=True`, then `Workbench stream task cancelled`, `Workbench model request cancelled`, and `LLM request cancelled`. If all appear while llama-server stays busy, the deployed server's disconnect handling must be investigated using its version and slot logs. If the cancel request is absent or reports `cancelled=False`, inspect the browser request and backend process receiving it.
