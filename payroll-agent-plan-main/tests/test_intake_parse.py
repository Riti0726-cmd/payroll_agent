from nodes.intake import parse_triage_command


def test_parse_triage_run_kv():
    cmd = parse_triage_command("TRIAGE_RUN specialist_id=alpha mailbox_id=user@contoso.com")
    assert cmd is not None
    assert cmd["specialist_id"] == "alpha"
    assert cmd["mailbox_id"] == "user@contoso.com"


def test_parse_triage_json():
    cmd = parse_triage_command('{"command":"triage","specialist_id":"beta"}')
    assert cmd is not None
    assert cmd["specialist_id"] == "beta"


def test_parse_non_triage_is_none():
    assert parse_triage_command("Why is my paycheck lower?") is None
