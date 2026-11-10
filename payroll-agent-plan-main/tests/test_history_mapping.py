from history_mapping import row_to_history_item


def test_row_to_history_item():
    item = row_to_history_item(
        {
            "message_id": "m1",
            "subject": "Done item",
            "category": "qa",
            "hitl_status": "done",
            "priority_rate": "high",
            "email_received_dttm": "2026-09-20T10:00:00+05:30",
            "content": "Closed.",
            "sub_content": '{"client_id":"C1"}',
        }
    )
    assert item["id"] == "m1"
    assert item["status"] == "done"
    assert item["category"] == "qa"
    assert item["priority"] == 1
    assert item["clientId"] == "C1"
