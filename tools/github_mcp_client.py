# tools/github_mcp_client.py
"""
This script initializes a Multi-Server MCP client for GitHub using the Model Context Protocol (MCP).
"""
from py_compile import main
from langchain_mcp_adapters.client import MultiServerMCPClient
from dotenv import load_dotenv
import asyncio
import os

load_dotenv()



class MCPClientInitialization:
    def __init__ (self):
        self.client = None
        self.tools = None
        self.token = os.getenv("GITHUB_PERSONAL_TOKEN")
        


    async def initialize(self):
        try:

            print("Connecting to GitHub MCP server...")
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


                            
            print("MCP client created, fetching available tools...")

            tools = await self.client.get_tools()
            print("GitHub MCP client initialized successfully!")
            print(f"Available tools: ")
            
            # Optionally print full tool details
            for tool in tools:
                print(f"\n->   {tool.name}")
                print(f"\n->    Description: {tool.description}")
                print(f"\n->    Args: {tool.args}\n")
                
        except Exception as e:
            print(f"Error initializing MCP client: {e}")
            raise


    async def search_github_repositories(self, query):
        try:
            search_tool = next(tool for tool in await self.client.get_tools() if tool.name == "search_repositories")
            result = await search_tool.ainvoke(
                {
                    "query": query,
                    "prPage": 5
                }
            )
            print(f"Search Results for '{query}':\n{result}")
        except StopIteration:
            print("The 'search_repositories' tool is not available.")
        except Exception as e:
            print(f"Error invoking tool: {e}")
            
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
 


"""
 self.client = MultiServerMCPClient(
                {
                    "github": {
                        "transport": "stdio",
                        "command": "docker",  # Use full path instead of just "npx"
                        "args": ["exec", "-i", "mcp-github-server", "node", "/app/dist/index.js"],
                        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": self.token}
                    }
                }
            )"""
