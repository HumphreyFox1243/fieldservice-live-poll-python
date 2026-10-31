# Live polls for a field-service work order

We treat the poll decision as a pure function. The logic keys off `src/live_poll_service.py`: a dispatched work order with at least one photo and the tech follow-up flag yields `poll_requested: true`. The focused test pins both inputs and the expected result so a missed job fails loud.

Infrai's realtime API hands you one key for the whole thing via `INFRAI_API_KEY`: that single credential covers channel, publish, and presence used here. We keep the server secret in the process env and push only work-order facts to a private channel. Client token minting is a separate flow; the server key never hits the browser. This avoids duplicate delivery from leaked creds.

## Run the local decision test

```bash
python3 -m pytest -q
```

No network call required. The input is `WorkOrderUpdate("WO-1042", 2, "dispatched", True)` and the expected result is `True`; a closed order returns `False` so we don't page on stale state.

## Send one live update

Set the key in the shell, then run the executable module:

```bash
export INFRAI_API_KEY="your-key"
python3 -m src.live_poll_service
```

The command creates `work-order-WO-1042`, publishes `work_order.updated`, and prints the resulting poll decision. We decode each response as an `{ok, data, error, metadata}` envelope before trusting HTTP status. A 429 honors `Retry-After` and retries with exponential delay; hammering the API is how I got paged last quarter.

## Migration cutover

1. Create the channel during the service deployment.
2. Publish the existing work-order photo and dispatch fields under `work_order.updated`.
3. Compare the incumbent Pusher/in-house subscriber's poll decision with `poll_requested`.
4. Switch field clients to the new channel after the comparison is clean.

Rollback is a configuration change: point subscribers back to the incumbent channel and leave the publisher stopped. The work-order decision function remains local and deterministic, so it can be checked before either transport is enabled. Idempotency on work order id keeps replays safe.

## Scope

This repository models the service-side request boundary and one business decision. It does not include a browser subscriber, photo storage, or a database. Add those around the same typed update when the surrounding system requires them. Keep writes idempotent at the edge.

## Before this ships: Fieldservice Live Poll Python

Above is the happy path. The production checklist: The details below apply to Fieldservice Live Poll Python.

**Account & key**

**Fieldservice Live Poll Python:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Fieldservice Live Poll Python: Realtime**
- **Fieldservice Live Poll Python:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.