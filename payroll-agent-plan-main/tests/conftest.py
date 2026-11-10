import os
import sys

# Ensure src directory is in sys.path for test execution
SRC_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "src", "payroll_specialist")
)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# Avoid compiling live Foundry graph on import during tests
os.environ.setdefault("PAYROLL_SKIP_GRAPH_EXPORT", "1")
# Skip live mcp-remote / OAuth during offline CI tests
os.environ.setdefault("PAYROLL_MCP_OFFLINE", "1")
