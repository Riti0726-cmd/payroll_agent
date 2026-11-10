from drafts_mapping import row_to_draft_item


def test_row_to_draft_item_happy():
    item = row_to_draft_item(
        {
            "message_id": "m1",
            "subject": "Pay question",
            "sender_email": "e@x.com",
            "draft_content": "Hello",
            "hitl_status": "pending",
        }
    )
    assert item == {
        "id": "m1",
        "subject": "Pay question",
        "to": "e@x.com",
        "body": "Hello",
        "status": "pending",
        "relatedQueueId": "m1",
    }


def test_row_to_draft_item_fallbacks():
    item = row_to_draft_item(
        {
            "message_id": "m2",
            "subject": None,
            "sender_email": None,
            "draft_content": "",
            "hitl_status": None,
        }
    )
    assert item["subject"] == "(no subject)"
    assert item["to"] == ""
    assert item["status"] == "pending"


def test_row_to_draft_item_unwraps_responses_blob():
    blob = (
        "[{'type': 'reasoning', 'content': [], 'encrypted_content': 'x'}, "
        "{'type': 'text', 'text': 'Clean draft body', 'phase': 'final_answer'}]"
    )
    item = row_to_draft_item(
        {
            "message_id": "m3",
            "subject": "Sub",
            "sender_email": "a@b.com",
            "draft_content": blob,
            "hitl_status": "pending",
        }
    )
    assert item["body"] == "Clean draft body"
    assert "encrypted_content" not in item["body"]
