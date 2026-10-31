from src.live_poll_service import WorkOrderUpdate, should_request_follow_up


def test_dispatched_order_with_photo_review_requests_follow_up_poll() -> None:
    update = WorkOrderUpdate("WO-1042", 2, "dispatched", True)
    assert should_request_follow_up(update) is True


def test_closed_order_does_not_request_follow_up_poll() -> None:
    update = WorkOrderUpdate("WO-1042", 2, "closed", True)
    assert should_request_follow_up(update) is False
