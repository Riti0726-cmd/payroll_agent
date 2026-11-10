from nodes.changelist import build_changelist_payload


def test_build_changelist_from_agent_result():
    from models import ChangelistBuildResult, ChangeLineBuild

    build = ChangelistBuildResult(
        changes=[
            ChangeLineBuild.model_validate(
                {
                    "field": "hourly_pay_rate",
                    "from": "20",
                    "to": "22",
                    "incomplete": False,
                    "recommended_system": "prismhr",
                    "recommended_field": "HOURLY_RATE",
                }
            )
        ],
        findings="looked up rate",
    )
    payload = build_changelist_payload(
        {"client_id": "C1", "intent": "rate"},
        build=build,
        title="Pay rate",
        query="update rate",
        snowflake_fetched=True,
    )
    assert payload["status"] == "pending"
    assert payload["changes"][0]["from"] == "20"
    assert payload["changes"][0]["recommended_system"] == "prismhr"
    assert payload["findings"] == "looked up rate"
    assert payload["snowflake_fetched"] is True


def test_build_changelist_blocks_email_only_without_fetch():
    payload = build_changelist_payload(
        {
            "client_id": "12890",
            "employee_id": "10452",
            "change_type": "hourly_pay_rate",
            "new_value": "22",
            "previous_value": None,
            "effective_date": "2026-09-14",
            "intent": "Raise rate",
        },
        query="Please raise rate to 22 due 2026-09-20",
        snowflake_fetched=False,
    )
    assert payload["changes"] == []
    assert payload["status"] == "incomplete"
    assert payload["snowflake_fetched"] is False
