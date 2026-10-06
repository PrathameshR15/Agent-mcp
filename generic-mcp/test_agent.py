import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def test_agent():
    server_url = "http://localhost:8000/mcp/sse"
    print(f"Connecting to MCP Server at {server_url}...")
    
    async with sse_client(server_url) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            print("Successfully connected to the MCP Server!\n")
            
            tools = await session.list_tools()
            print("Available Tools discovered:")
            for tool in tools.tools:
                print(f"- {tool.name}: {tool.description}")
            
            print("\n--- Submitting a test job ---")
            
            result = await session.call_tool(
                "submit_job",
                arguments={
                    "data_type": "application/json",
                    "payload": {"sensor_id": "123", "temp": 105.2},
                    "requirements": ["analyze_temperature"]
                }
            )
            
            print("Response from MCP Server:")
            print(result.content[0].text)

if __name__ == "__main__":
    asyncio.run(test_agent())
