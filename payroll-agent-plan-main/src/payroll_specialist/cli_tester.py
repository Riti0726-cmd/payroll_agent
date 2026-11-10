# Copyright (c) Microsoft & EngageAI. All rights reserved.

import asyncio
import logging
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(message)s")
for name in ("azure", "azure.core", "azure.identity", "httpx", "httpx2", "openai"):
    logging.getLogger(name).setLevel(logging.WARNING)

from langchain_core.messages import HumanMessage

from config import require_foundry_settings
from graph import build_chat_model, create_payroll_graph
from nodes.intake import parse_triage_command
from qa_agent import run_qa_chat
from triage.email_graph import build_email_processing_graph_from_model, run_email_graph

load_dotenv()

SAMPLE_SCENARIOS = {
    "1": (
        "QA via POST /qa agent",
        "Why was my August 2026 paycheck lower than July? EMP-1042",
        "qa",
    ),
    "2": (
        "Email subgraph — Changelist",
        "Hi, I need to change my direct deposit bank account for my upcoming paycheck.",
        "email",
    ),
    "3": (
        "Email subgraph — Todo",
        "Please approve contractor timesheets for Project Falcon before the payroll cutoff.",
        "email",
    ),
    "4": (
        "Email subgraph — Out of scope",
        "I need help enrolling in the dental benefits plan for next year.",
        "email",
    ),
    "5": (
        "Triage run (Foundry graph)",
        "TRIAGE_RUN specialist_id=demo-specialist",
        "triage",
    ),
}


async def run_interactive():
    print("=" * 70)
    print("    LANGGRAPH PAYROLL SPECIALIST ENGINE - CLI TESTER")
    print("=" * 70)
    print("Initializing…\n")

    try:
        _, model_deployment = require_foundry_settings()
    except Exception as exc:
        print(f"[ERROR] Missing Foundry configuration: {exc}")
        return

    try:
        foundry_graph = create_payroll_graph()
        email_graph = build_email_processing_graph_from_model(build_chat_model(disable_streaming=True))
        print(f"[OK] Graphs ready. Model: {model_deployment}")
        print("     Foundry /responses = TRIAGE_RUN only; Q&A = POST /qa; classify = email subgraph")
    except Exception as exc:
        print(f"[ERROR] Failed to compile workflows: {exc}")
        return

    print("-" * 70)

    while True:
        print("\nChoose a testing option:")
        print("  1. Q&A (standalone /qa agent)")
        print("  2. Email subgraph — Changelist")
        print("  3. Email subgraph — Todo")
        print("  4. Email subgraph — Out of scope")
        print("  5. Triage run (Foundry graph)")
        print("  6. Custom (TRIAGE_RUN → Foundry; else → /qa agent)")
        print("  q. Quit")

        choice = input("\nSelect option (1-6, q): ").strip().lower()

        if choice in ("q", "quit", "exit"):
            print("\nExiting CLI tester. Goodbye!")
            break

        query = ""
        path = "qa"
        if choice in SAMPLE_SCENARIOS:
            label, query, path = SAMPLE_SCENARIOS[choice]
            print(f"\n[Running Scenario {choice}: {label}]")
            print(f"Query: \"{query}\"")
        elif choice == "6":
            query = input("\nEnter your payroll question or TRIAGE_RUN:\n> ").strip()
            if not query:
                print("Query cannot be empty.")
                continue
            path = "triage" if parse_triage_command(query) else "qa"
        else:
            print("Invalid option. Please choose 1-6 or q.")
            continue

        print("\nExecuting...")
        print("-" * 70)
        try:
            if path == "triage":
                result = await foundry_graph.ainvoke({"messages": [HumanMessage(content=query)]})
                messages = result.get("messages", [])
                output_text = messages[-1].content if messages else str(result)
            elif path == "email":
                out = await run_email_graph(email_graph, query)
                output_text = (
                    f"category={out.get('triage', {}).get('category')}\n"
                    f"draft={out.get('draft')}\n"
                    f"qa_findings={out.get('qa_findings')}\n"
                    f"routing={out.get('triage')}"
                )
            else:
                qa = await run_qa_chat([{"role": "user", "content": query}])
                output_text = f"{qa.answer}\n\nSources: {qa.sources}"

            print("\n" + "=" * 70)
            print("                   RESPONSE")
            print("=" * 70)
            print(output_text)
            print("=" * 70)
        except Exception as exc:
            print(f"\n[ERROR] Execution failed: {exc}")


if __name__ == "__main__":
    asyncio.run(run_interactive())
