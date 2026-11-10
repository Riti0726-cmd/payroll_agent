import json

from changelists_mapping import row_to_changelist_item


def test_row_to_changelist_empty_lines():
    item = row_to_changelist_item(
        {
            "message_id": "c1",
            "subject": "DD change",
            "sub_content": '{"client_id":"C9"}',
            "changelist_response": None,
            "hitl_status": "pending",
        }
    )
    assert item["id"] == "c1"
    assert item["clientId"] == "C9"
    assert item["title"] == "DD change"
    assert item["lines"] == []


def test_row_to_changelist_parses_lines():
    payload = {
        "lines": [
            {"id": "l1", "field": "bank", "from": "1", "to": "2", "reviewed": False}
        ]
    }
    item = row_to_changelist_item(
        {
            "message_id": "c2",
            "subject": None,
            "sub_content": None,
            "changelist_response": json.dumps(payload),
            "hitl_status": None,
        }
    )
    assert item["clientId"] == "unknown"
    assert item["title"] == "(no subject)"
    assert item["lines"][0]["field"] == "bank"
    assert item["lines"][0]["from"] == "1"


def test_row_to_changelist_maps_changes_when_lines_empty():
    payload = {
        "agent": "changelist",
        "parameters": {"client_id": "12890"},
        "changes": [
            {
                "field": "hourly_pay_rate",
                "from": 20.0,
                "to": 22.0,
                "effective_date": "2026-09-14",
            }
        ],
    }
    item = row_to_changelist_item(
        {
            "message_id": "c3",
            "subject": "Pay rate",
            "sub_content": None,
            "changelist_response": json.dumps(payload),
        }
    )
    assert item["clientId"] == "12890"
    assert item["lines"] == [
        {
            "id": "l0",
            "field": "hourly_pay_rate",
            "from": "20.0",
            "to": "22.0",
            "reviewed": False,
            "effectiveDate": "2026-09-14",
        }
    ]


def test_row_to_changelist_lines_win_over_changes():
    payload = {
        "lines": [{"id": "l1", "field": "bank", "from": "A", "to": "B"}],
        "changes": [{"field": "hourly_pay_rate", "from": 1, "to": 2}],
    }
    item = row_to_changelist_item(
        {
            "message_id": "c4",
            "subject": "x",
            "sub_content": None,
            "changelist_response": json.dumps(payload),
        }
    )
    assert len(item["lines"]) == 1
    assert item["lines"][0]["field"] == "bank"


def test_merge_preserves_rich_changes():
    from changelists_mapping import merge_changelist_payload

    existing = {
        "agent": "changelist",
        "changes": [{"field": "bonus", "from": None, "to": 100}],
        "status": "ready",
    }
    shell = {"clientId": "C1", "title": "T", "lines": [], "status": "pending"}
    out = merge_changelist_payload(existing, shell)
    assert out["changes"] == existing["changes"]
    assert out["status"] == "ready"
    assert out["clientId"] == "C1"
    assert out["title"] == "T"


def test_merge_uses_shell_when_empty():
    from changelists_mapping import merge_changelist_payload

    shell = {"clientId": "C1", "title": "T", "lines": [], "status": "pending"}
    assert merge_changelist_payload({"lines": []}, shell) == shell
    assert merge_changelist_payload(None, shell) == shell
