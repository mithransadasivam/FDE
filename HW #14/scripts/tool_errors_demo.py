"""Day 11, Activity 3: send deliberately bad tool calls through run_tool() and print what the
model would get back. No model is called.

    python -m scripts.tool_errors_demo
"""

from app.tool_loop import run_tool

BAD_CALLS = [
    ("find_tickets", '{"status": "broken"}', "a status that does not exist"),
    ("find_tickets", '{"limit": "ten"}', "a number sent as text"),
    ("find_tickets", '{"limit": 500}', "far too many results"),
    ("find_tickets", '{"status": "open"; DROP TABLE tickets}', "not valid JSON"),
    ("get_ticket", '{"ticket_id": "1017"}', "an id in the wrong format"),
    (
        "update_ticket",
        '{"ticket_id": "INC-1017", "status": "closed"}',
        "a required argument missing",
    ),
    ("service_status", '{"service": "Payroll"}', "a service the tool does not know"),
    ("delete_all_tickets", "{}", "a tool that does not exist"),
    (
        "calculate",
        "{\"expression\": \"__import__('os').remove('x')\"}",
        "code instead of arithmetic",
    ),
]


def main():
    for name, arguments, what in BAD_CALLS:
        print(f"{what}\n  {name}({arguments})\n  -> {run_tool(name, arguments)}\n")


if __name__ == "__main__":
    main()
