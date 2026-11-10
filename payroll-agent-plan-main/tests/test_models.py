from models import ClassificationResult, TriageMessage


def test_classification_result_valid():
    model = ClassificationResult(
        category="qa",
        intent="Variance lookup",
        confidence=0.95,
        employee_id="EMP-1042",
        pay_period="2026-08",
    )
    assert model.category == "qa"
    assert model.employee_id == "EMP-1042"
    assert model.pay_period == "2026-08"
    assert model.oos_destination is None


def test_classification_out_of_scope():
    model = ClassificationResult(
        category="out_of_scope",
        intent="Dental enrollment",
        oos_destination="benefits",
    )
    assert model.category == "out_of_scope"
    assert model.oos_destination == "benefits"


def test_classification_result_defaults():
    model = ClassificationResult(
        category="changelist",
        intent="Update bank account",
    )
    assert model.category == "changelist"
    assert model.confidence == 0.95
    assert model.employee_id is None
    assert model.pay_period is None


def test_classification_core_r1_fields():
    model = ClassificationResult(
        category="changelist",
        intent="Update hourly rate",
        client_id="CLI-9",
        employee_name="Ada Lovelace",
        effective_date="2026-10-01",
        employee_id="EMP-1042",
        pay_period="2026-09",
    )
    assert model.client_id == "CLI-9"
    assert model.employee_name == "Ada Lovelace"
    assert model.effective_date == "2026-10-01"


def test_classification_core_r1_defaults_null():
    model = ClassificationResult(category="qa", intent="Pay variance")
    assert model.client_id is None
    assert model.employee_name is None
    assert model.effective_date is None


def test_triage_message_dataclass():
    msg = TriageMessage(
        category="todo",
        query="Approve timesheets",
        intent="Operational approval",
        confidence=0.99,
    )
    assert msg.category == "todo"
    assert msg.employee_id is None
    assert msg.client_id is None
    assert msg.employee_name is None
    assert msg.effective_date is None
