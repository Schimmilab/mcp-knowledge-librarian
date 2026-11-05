"""Security regression: the preview server must bind to loopback, whatever the tool call asks for.

The preview server has no authentication and serves full PDFs. If a (prompt-injected) tool call
could choose the bind address, "0.0.0.0" would expose the whole library to the network.
"""
import asyncio

import yaml
from mcp.types import CallToolRequest, CallToolRequestParams, ListToolsRequest

import mcp_knowledge_librarian.http_server as http_server_mod
from mcp_knowledge_librarian.server import KnowledgeLibrarianServer


class _FakePreviewServer:
    instances: list["_FakePreviewServer"] = []

    def __init__(self, index_manager, host, port):
        self.host, self.port = host, port
        _FakePreviewServer.instances.append(self)

    async def start(self):
        await asyncio.sleep(0)

    async def stop(self):
        pass


def _make_server(tmp_path):
    cfg = {
        "library_paths": [str(tmp_path)],
        "index_path": str(tmp_path / "index"),
        "logging": {"level": "WARNING", "format": "%(message)s"},
        "extraction": {"enable_ocr": False, "ocr_language": "eng"},
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg))
    return KnowledgeLibrarianServer(config_path=str(path))


def _call(srv, name, arguments):
    handler = srv.server.request_handlers[CallToolRequest]
    req = CallToolRequest(method="tools/call", params=CallToolRequestParams(name=name, arguments=arguments))
    return asyncio.run(handler(req))


def test_bind_address_is_loopback_even_if_tool_asks_for_all_interfaces(tmp_path, monkeypatch):
    monkeypatch.setattr(http_server_mod, "PDFPreviewServer", _FakePreviewServer)
    _FakePreviewServer.instances.clear()
    srv = _make_server(tmp_path)
    _call(srv, "start_http_server", {"host": "0.0.0.0", "port": 18765})
    assert _FakePreviewServer.instances, "preview server was not started at all"
    assert _FakePreviewServer.instances[-1].host == "127.0.0.1"


def test_tool_schema_does_not_offer_a_host_parameter(tmp_path):
    srv = _make_server(tmp_path)
    handler = srv.server.request_handlers[ListToolsRequest]
    result = asyncio.run(handler(ListToolsRequest(method="tools/list")))
    tool = next(t for t in result.root.tools if t.name == "start_http_server")
    assert "host" not in tool.inputSchema.get("properties", {})
