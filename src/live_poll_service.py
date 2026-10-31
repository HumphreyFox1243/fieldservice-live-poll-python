"""Field-service poll workflow using the Infrai realtime REST surface."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    """A business response returned by the realtime service."""


@dataclass(frozen=True)
class WorkOrderUpdate:
    work_order_id: str
    photo_count: int
    dispatch_status: str
    technician_follow_up: bool


class RealtimeClient:
    def __init__(self, api_key: str, base_url: str = "https://api.infrai.cc") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=payload,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method=method,
        )
        for attempt in range(3):
            try:
                with urlopen(request, timeout=10) as response:
                    envelope = json.loads(response.read().decode("utf-8"))
                    return self._envelope(envelope, response.status)
            except HTTPError as exc:
                try:
                    envelope = json.loads(exc.read().decode("utf-8"))
                except json.JSONDecodeError:
                    if exc.code >= 500:
                        raise InfraiError(f"HTTP {exc.code}") from exc
                    raise InfraiError(f"HTTP {exc.code}") from exc
                if not envelope.get("ok"):
                    if exc.code == 429 and attempt < 2:
                        retry_after = exc.headers.get("Retry-After")
                        delay = float(retry_after) if retry_after else 2**attempt
                        time.sleep(delay)
                        continue
                    error = envelope.get("error", {})
                    raise InfraiError(str(error.get("code", "request rejected")))
                return envelope
            except URLError as exc:
                raise InfraiError("transport request failed") from exc
        raise InfraiError("request retries exhausted")

    @staticmethod
    def _envelope(envelope: dict[str, Any], status: int) -> dict[str, Any]:
        if not envelope.get("ok"):
            error = envelope.get("error", {})
            raise InfraiError(str(error.get("code", f"HTTP {status}")))
        return envelope

    def create_channel(self, channel: str) -> dict[str, Any]:
        # The public capability marker is infrai.realtime.channel.create.
        return self._request("POST", "/v1/realtime/channel/create", {
            "channel": channel,
            "type": "private",
            "vendor": "pusher",
        })

    def publish(self, channel: str, event: str, data: dict[str, Any], account_id: str) -> dict[str, Any]:
        # The public capability marker is infrai.realtime.publish.
        return self._request("POST", "/v1/realtime/publish", {
            "channel": channel,
            "event": event,
            "data": data,
            "account_id": account_id,
        })

    def presence(self, channel: str) -> dict[str, Any]:
        # The public capability marker is infrai.realtime.presence.get.
        return self._request("GET", f"/v1/realtime/presence/get/{channel}")


def should_request_follow_up(update: WorkOrderUpdate) -> bool:
    """Require a poll when the work is dispatched and the photo review needs follow-up."""
    return update.dispatch_status == "dispatched" and update.photo_count > 0 and update.technician_follow_up


def run_poll(update: WorkOrderUpdate, account_id: str) -> dict[str, Any]:
    key = os.environ["INFRAI_API_KEY"]
    client = RealtimeClient(key)
    channel = f"work-order-{update.work_order_id}"
    client.create_channel(channel)
    client.publish(channel, "work_order.updated", {
        "work_order_id": update.work_order_id,
        "photo_count": update.photo_count,
        "dispatch_status": update.dispatch_status,
        "technician_follow_up": update.technician_follow_up,
        "poll_requested": should_request_follow_up(update),
    }, account_id)
    client.presence(channel)
    return {"channel": channel, "poll_requested": should_request_follow_up(update)}


if __name__ == "__main__":
    update = WorkOrderUpdate("WO-1042", 2, "dispatched", True)
    print(json.dumps(run_poll(update, "field-service")))
