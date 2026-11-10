from triage.mailbox import MailMessage, MockGraphMailbox


def test_mock_mailbox_preserves_conversation_and_body():
    mb = MockGraphMailbox(
        [
            MailMessage(
                id="m1",
                received_at="2026-09-01T10:00:00Z",
                subject="Pay",
                body_preview="preview",
                body="full body EMP-1",
                conversation_id="conv-1",
            )
        ]
    )
    mb.bind_specialist("s1", "box1")
    msgs = mb.list_messages(
        "box1",
        window_start="2026-09-01T00:00:00Z",
        window_end="2026-09-02T00:00:00Z",
    )
    assert msgs[0].conversation_id == "conv-1"
    assert msgs[0].body == "full body EMP-1"
