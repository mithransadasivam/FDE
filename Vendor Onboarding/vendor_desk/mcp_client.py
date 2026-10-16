"""MCP backend for the agents (Phase 7): starts the procurement MCP server as a child process, lists its tools and calls
them, so the checks live in ONE place (the server). Same two methods as the local Toolbox (`openai_tools`, `call`), so
an agent does not know which one it has: TOOLS_BACKEND=local|mcp switches between them.

Fail closed (decision recorded in docs/DECISIONS.md): if the server cannot be reached the backend raises BackendDown, the
case ends with a clear status and NO decision. There is no silent fallback to the local tools, because a result the
server did not produce is a guess about what the server would have said.
"""
import asyncio
import json
import os
import sys
import threading

from vendor_desk import config
from vendor_desk.tools import BackendDown

CALL_TIMEOUT = 45


class McpBackend:
    def __init__(self, writes: bool = False, extra_env: dict | None = None, command: str | None = None,
                 args: list[str] | None = None, timeout: float = CALL_TIMEOUT):
        self.writes = writes
        self.command = command or sys.executable
        self.args = args if args is not None else ["-m", "vendor_desk.mcp_server"]
        self.extra_env = extra_env or {}
        self.timeout = timeout
        self._loop = None
        self._thread = None
        self._queue = None
        self._ready = threading.Event()
        self._error: str | None = None
        self._tools: list | None = None
        self._closed = False

    # ------------------------------------------------------------------ lifecycle
    def _start(self):
        if self._closed:
            raise BackendDown("The connection to the procurement MCP server was closed.")
        if self._thread is not None:
            if self._error:
                raise BackendDown(self._error)
            return
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=30) and not self._error:
            self._error = "The procurement MCP server did not start in time."
        if self._error:
            raise BackendDown(self._error)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        except BaseException as err:  # the server could not start or died: remember why, never crash the caller
            if not self._error:
                self._error = f"The procurement MCP server is not reachable ({type(err).__name__})."
        finally:
            self._ready.set()

    async def _serve(self):
        from mcp import Client, StdioServerParameters
        env = {**os.environ, "VENDOR_WRITES": "on" if self.writes else "off", **self.extra_env}
        params = StdioServerParameters(command=self.command, args=self.args, env=env, cwd=str(config.ROOT))
        self._queue = asyncio.Queue()
        async with Client(params) as client:
            listed = await client.list_tools()
            self._tools = [{"name": t.name, "description": t.description or "", "schema": t.input_schema}
                           if hasattr(t, "input_schema") else
                           {"name": t.name, "description": t.description or "", "schema": t.inputSchema}
                           for t in listed.tools]
            self._ready.set()
            while True:
                item = await self._queue.get()
                if item is None:
                    break
                fn, fut = item
                try:
                    fut.set_result(await fn(client))
                except BaseException as err:
                    fut.set_exception(err)

    def _submit(self, fn):
        self._start()
        coro = self._enqueue(fn)
        try:
            fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
            return fut.result(timeout=self.timeout)
        except Exception as err:
            coro.close()
            self._error = f"The procurement MCP server stopped answering ({type(err).__name__})."
            raise BackendDown(self._error) from err

    async def _enqueue(self, fn):
        fut = self._loop.create_future()
        await self._queue.put((fn, fut))
        return await fut

    def close(self):
        self._closed = True
        if self._thread is not None and self._queue is not None and self._loop and not self._loop.is_closed():
            try:
                asyncio.run_coroutine_threadsafe(self._queue.put(None), self._loop).result(timeout=5)
                self._thread.join(timeout=10)
            except Exception:
                pass
        self._thread = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ------------------------------------------------------------------ same interface as Toolbox
    def tool_names(self) -> list[str]:
        self._start()
        return [t["name"] for t in self._tools]

    def openai_tools(self, names: list[str] | None = None) -> list[dict]:
        """The server's tools in the agent's tool-list format (the model reads the server's descriptions and schemas)."""
        self._start()
        out = []
        for t in self._tools:
            if names is None or t["name"] in names:
                out.append({"type": "function", "function": {
                    "name": t["name"], "description": t["description"], "parameters": t["schema"]}})
        return out

    def call(self, name: str, args) -> dict:
        async def go(client):
            return await client.call_tool(name, args if isinstance(args, dict) else {})
        result = self._submit(go)
        text = result.content[0].text if result.content else ""
        if result.is_error:
            return {"error": text.replace(f"Error executing tool {name}: ", "") or "The tool reported an error."}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"error": f"{name} returned something that is not JSON."}
