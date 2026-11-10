"""Parse Cortex MCP tool I/O into Q&A source panes."""

from __future__ import annotations

import json

from models import QaSource
from qa_agent import NOT_RETURNED, parse_cortex_tool_trace, sources_from_tool_messages


def test_parse_cortex_tool_trace_full_json():
    args = {"message": "List 3 active employees"}
    result = json.dumps(
        {
            "sql": "SELECT employee_id FROM hr LIMIT 3",
            "interpretation": "Returns three active employees.",
            "results": [{"employee_id": "E1"}, {"employee_id": "E2"}],
        }
    )
    panes = parse_cortex_tool_trace(args, result)
    assert panes["query"] == "List 3 active employees"
    assert "Returns three" in panes["interpretation"]
    assert "E1" in panes["response"]
    assert panes["detail"]


def test_parse_cortex_tool_trace_missing_sections_use_sentinel():
    panes = parse_cortex_tool_trace({}, "Generated SQL only: SELECT 1")
    assert panes["query"] == NOT_RETURNED
    assert panes["interpretation"] == NOT_RETURNED
    assert "SELECT 1" in panes["response"] or panes["response"] == "Generated SQL only: SELECT 1"


def test_parse_cortex_tool_trace_list_of_text_statement_blocks():
    """Cortex Analyst often returns [{text, statement}] — not a top-level dict."""
    args = {
        "message": (
            "For client 240242, from January 1, 2026 through today, "
            "identify the calendar month with the highest total gross pay."
        )
    }
    result = json.dumps(
        [
            {
                "text": (
                    "This is our interpretation of your question:\n\n"
                    "For client_id '240242', calculate total gross pay by month."
                ),
                "statement": (
                    "WITH __payroll AS (\n"
                    " SELECT gross_pay, pay_date, client_id\n"
                    " FROM DWH_AI_DEV.ENG_SEMANTIC.VW_PAYROLL\n"
                    ")\nSELECT 1"
                ),
            }
        ]
    )
    panes = parse_cortex_tool_trace(args, result)
    assert "interpretation of your question" in panes["interpretation"]
    assert panes["interpretation"] != NOT_RETURNED
    assert "WITH __payroll" in panes["response"]
    assert "[{}" not in panes["response"] and not panes["response"].lstrip().startswith("[")


def test_parse_sql_query_executor_result_set():
    sql = "SELECT SUM(gross_pay) AS TOTAL_GROSS_WAGES, client_name FROM payroll"
    result = json.dumps(
        {
            "query_id": "01C76529-0206-5B40-0017-D08340CB2CA2",
            "result_set": {
                "data": [["60337031.56", "RECSOL RECOVERY SOLUTIONS, LLC"]],
                "partition": 0,
                "partitionInfo": [{"rowCount": 1, "uncompressedSize": 59}],
                "rowType": [
                    {"name": "TOTAL_GROSS_WAGES", "nullable": True, "precision": 38},
                    {"name": "CLIENT_NAME", "nullable": True},
                ],
                "resultSetMetaData": {"format": "jsonv2", "numRows": 1},
            },
        }
    )
    panes = parse_cortex_tool_trace({"sql": sql}, result)
    assert panes["query"] == sql
    assert "01C76529" in panes["interpretation"]
    assert "1 row(s)" in panes["interpretation"]
    assert "TOTAL_GROSS_WAGES" in panes["interpretation"]
    assert "60337031.56" in panes["response"]
    assert "RECSOL RECOVERY SOLUTIONS, LLC" in panes["response"]
    assert "partitionInfo" not in panes["response"]


def test_sources_from_tool_messages_pairs_args_and_results():
    messages = [
        {
            "type": "ai",
            "tool_calls": [
                {
                    "name": "sv_hr_workforce",
                    "args": {"message": "Show EMP-1 status"},
                    "id": "c1",
                }
            ],
        },
        {
            "type": "tool",
            "name": "sv_hr_workforce",
            "tool_call_id": "c1",
            "content": json.dumps(
                {
                    "query": "SELECT status FROM emp WHERE id='EMP-1'",
                    "interpretation": "Looks up employment status.",
                    "data": [{"status": "A"}],
                }
            ),
        },
    ]
    sources = sources_from_tool_messages(messages)
    assert len(sources) == 1
    src = sources[0]
    assert isinstance(src, QaSource)
    assert src.label == "sv_hr_workforce"
    assert src.query == "Show EMP-1 status"
    assert "employment status" in src.interpretation
    assert "A" in src.response


def test_sources_from_tool_messages_skips_named_agent_answer():
    """Final create_agent AIMessage is named payroll-qa-chat — not a Cortex tool."""
    messages = [
        {
            "type": "ai",
            "tool_calls": [
                {
                    "name": "sv_employee_payroll",
                    "args": {"message": "DD vs check counts"},
                    "id": "c1",
                }
            ],
        },
        {
            "type": "tool",
            "name": "sv_employee_payroll",
            "tool_call_id": "c1",
            "content": json.dumps({"interpretation": "Counts by pay method."}),
        },
        {
            "type": "ai",
            "name": "payroll-qa-chat",
            "content": "Direct deposit: 326. Check: 78.",
        },
    ]
    sources = sources_from_tool_messages(messages)
    assert [s.label for s in sources] == ["sv_employee_payroll"]
    assert all(s.label != "payroll-qa-chat" for s in sources)
