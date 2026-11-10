from triage.thread import assemble_current_request


def test_assemble_includes_subject_and_current():
    text = assemble_current_request(
        subject="Rate change",
        current_body="Please update EMP-9 to $50 effective 2026-10-01",
        prior_bodies=["Old question about August pay"],
    )
    assert "Rate change" in text
    assert "EMP-9" in text
    assert "Old question" in text


def test_assemble_caps_prior():
    priors = [f"msg-{i}" for i in range(20)]
    text = assemble_current_request(
        subject="S",
        current_body="latest",
        prior_bodies=priors,
        max_prior=3,
    )
    assert "msg-17" in text
    assert "msg-0" not in text
