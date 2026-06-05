import logging
from langchain_mcp_adapters.client import MultiServerMCPClient
from dotenv import load_dotenv
import asyncio
import os

load_dotenv()

logger = logging.getLogger(__name__)



class MCPClientInitialization:
    def __init__ (self):
        self.client = None
        self.tools = None
        self.token = os.getenv("GITHUB_PERSONAL_TOKEN")
        


    async def initialize(self):
        try:

            logger.info("GitHub MCP: connecting to server...")
            # Initialize the MCP client for GitHub
            self.client = MultiServerMCPClient(
                {
                    "github": {
                        "transport": "http",
                        "url": "https://api.githubcopilot.com/mcp/",
                        "headers": {
                            "Authorization": f"Bearer {self.token}"
                        }
                    }
                },
            
            )


                            
            logger.info("GitHub MCP: client created, fetching available tools...")

            tools = await self.client.get_tools()
            logger.info("GitHub MCP: initialized with %d tool(s)", len(tools))

            # Full tool details only at DEBUG level (verbose).
            for tool in tools:
                logger.debug("GitHub MCP tool: %s — %s — args=%s", tool.name, tool.description, tool.args)

        except Exception:
            logger.exception("GitHub MCP: error initializing client")
            raise


    async def search_github_repositories(self, query):
        try:
            search_tool = next(tool for tool in await self.client.get_tools() if tool.name == "search_repositories")
            result = await search_tool.ainvoke(
                {
                    "query": query,
                    "perPage": 5
                }
            )
            logger.info("GitHub MCP: search returned results for %r", query)
            logger.debug("GitHub MCP search results for %r:\n%s", query, result)
            return result
        except StopIteration:
            logger.warning("GitHub MCP: 'search_repositories' tool is not available")
            return None
        except Exception:
            logger.exception("GitHub MCP: error invoking search tool")
            return None
            
    async def run(self):
        await self.initialize()
        await self.search_github_repositories("langchain MCP projects in python")
        print("\n" + "=" * 60 + "\n")

async def main():
    """Main function to run all operations in a single event loop"""
    client = MCPClientInitialization()
    await client.run()


if __name__ == "__main__":
    # Run everything in a single event loop
    asyncio.run(main())
 


