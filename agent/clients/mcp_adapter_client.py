# clients/mcp_adapter_client.py
from __future__ import annotations

import os
from typing import List

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient # Corrected import


async def load_mcp_tools() -> List[BaseTool]:
    """
    Connects to the MCP server and loads all registered tools as LangChain Tools.
    """
    base_url = os.getenv("MCP_BASE_URL")
    if not base_url:
        raise ValueError("MCP_BASE_URL environment variable is not set.")

    # MultiServerMCPClient is used for all connections.
    # For a remote HTTP server, we provide a URL and transport config.
    # The URL should point to the specific MCP path, typically ending in /mcp/
    mcp_url = base_url.rstrip('/') + "/mcp/"

    client = MultiServerMCPClient({
        "default_server": {
            "url": mcp_url,
            "transport": "streamable_http",
        }
    })

    # Fetches the tools from the server and converts them to LangChain tools
    tools = await client.get_tools()
    
    print(f"\n>> Loaded {len(tools)} tools from MCP Server:")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description}")
        
    return tools