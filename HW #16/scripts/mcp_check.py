"""Day 13: check the MCP server the way a real client does: start it as a separate process and talk to
it over stdin/stdout. No model is involved: this script plays the client's part itself.

python -m scripts.mcp_check                                   (lists everything, runs two sample queries)
python -m scripts.mcp_check "SELECT id, summary FROM tickets WHERE severity = 'P1'"
"""

import asyncio
import json
import sys

from mcp import Client, StdioServerParameters

SAMPLES = [
    "SELECT status, COUNT(*) AS tickets FROM tickets GROUP BY status",
    "SELECT full_name, job_title FROM staff WHERE username = 't.sato'",
]


async def main(queries):
    server = StdioServerParameters(command=sys.executable, args=["app/mcp_server.py"])
    async with Client(server) as client:
        tools = await client.list_tools()
        print("Tools:")
        for t in tools.tools:
            print(f"  {t.name}: {' '.join(t.description.split())}")
        resources = await client.list_resources()
        print("Resources:")
        for r in resources.resources:
            print(f"  {r.uri}: {r.description}")
        for sql in queries:
            print(f"\nrun_query: {sql}")
            result = await client.call_tool("run_query", {"sql": sql})
            text = result.content[0].text if result.content else ""
            if result.is_error:
                print(f"  ERROR (the model would see this): {text}")
            else:
                data = json.loads(text)
                print("  " + " | ".join(data["columns"]))
                for row in data["rows"]:
                    print("  " + " | ".join(str(v) for v in row))
                if data["truncated"]:
                    print("  ... more rows were cut off")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or SAMPLES))
