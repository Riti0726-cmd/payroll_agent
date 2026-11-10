from queue_mapping import (
    body_excerpt,
    map_category,
    map_priority_rate,
    parse_extracts,
    row_to_queue_item,
)


def test_map_priority_rate():
    assert map_priority_rate("high") == 1
    assert map_priority_rate("medium") == 3
    assert map_priority_rate("low") == 5
    assert map_priority_rate(None) == 3
    assert map_priority_rate("weird") == 3


def test_priority_to_rate():
    from queue_mapping import priority_to_rate

    assert priority_to_rate(1) == "high"
    assert priority_to_rate(3) == "medium"
    assert priority_to_rate(5) == "low"
    assert priority_to_rate(2) == "medium"


def test_map_category_first_allowed():
    assert map_category("qa,changelist") == "qa"
    assert map_category("todo") == "todo"
    assert map_category("") is None
    assert map_category("unknown") is None


def test_body_excerpt_truncates():
    assert body_excerpt("x" * 300) == ("x" * 280)
    assert body_excerpt(None) is None
    assert body_excerpt("short") == "short"


def test_parse_extracts_json():
    assert parse_extracts('{"client_id":"C1","employee_id":"E9"}') == {
        "client_id": "C1",
        "employee_id": "E9",
    }
    assert parse_extracts(None) == {}
    assert parse_extracts("not-json") == {}


def test_row_to_queue_item_happy_path():
    item = row_to_queue_item(
        {
            "message_id": "m1",
            "subject": "Direct deposit change",
            "category": "changelist",
            "priority_rate": "high",
            "email_received_dttm": "2026-09-20T10:00:00+05:30",
            "content": "Please update bank account.",
            "sub_content": '{"client_id":"C1","employee_id":"E9"}',
        }
    )
    assert item["id"] == "m1"
    assert item["subject"] == "Direct deposit change"
    assert item["category"] == "changelist"
    assert item["priority"] == 1
    assert item["receivedAt"].startswith("2026-09-20")
    assert item["clientId"] == "C1"
    assert item["employeeId"] == "E9"
    assert item["bodyExcerpt"] == "Please update bank account."
    assert item["extracted"]["client_id"] == "C1"


def test_row_to_queue_item_fallbacks():
    item = row_to_queue_item(
        {
            "message_id": "m2",
            "subject": None,
            "category": None,
            "priority_rate": None,
            "email_received_dttm": None,
            "content": None,
            "sub_content": None,
        }
    )
    assert item["subject"] == "(no subject)"
    assert item["category"] == "todo"
    assert item["priority"] == 3
    assert item["receivedAt"] == "1970-01-01T00:00:00+00:00"
    assert item.get("clientId") is None
