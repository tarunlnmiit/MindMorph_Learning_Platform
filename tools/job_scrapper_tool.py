
import sys
import os
from typing import Optional, List, Dict, Any


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from langchain_mcp_adapters.client import MultiServerMCPClient
from dotenv import load_dotenv
import asyncio
import os
import json
from config import llm
import re

load_dotenv()

class JobScraperService:
    def __init__(self):
        self.client = None
        self.token = os.getenv("APIFY_API_KEY")
        self.tools = []

    async def initialize(self):
        """Initialize the MCP client connection."""
        try:
            print("Connecting to Job Scrapper MCP server...")
            self.client = MultiServerMCPClient(
                {
                    "apify": {
                        "transport": "http",
                        "url": "https://mcp.apify.com/?tools=fantastic-jobs/advanced-linkedin-job-search-api",
                        "headers": {
                            "Authorization": f"Bearer {self.token}"
                        }
                    }
                }
            )
            print("Job Scrapper MCP client initialized successfully!, fetching available tools...")
            self.tools = await self.client.get_tools()
            return self.client
        except Exception as e:
            print(f"Error initializing MCP client: {e}")
            raise

    # Apify actor name for the LinkedIn job-search actor (as exposed by the MCP server).
    SEARCH_TOOL_NAME = "fantastic-jobs--advanced-linkedin-job-search-api"
    OUTPUT_TOOL_NAME = "get-dataset-items"

    async def search_jobs(self, query: str, location: str = "United States") -> Optional[str]:
        """
        Executes the job search actor and returns the resulting Dataset ID.

        The actor returns a run-summary JSON; the dataset id lives at
        storages.datasets.default.id (with an itemCount we use to skip empty runs).
        """
        try:
            job_search_tool = next(
                tool for tool in self.tools
                if tool.name == self.SEARCH_TOOL_NAME
            )

            print(f"\nSearching for: '{query}' in {location}...")
            # `limit` must be >= 10 per the actor's input schema.
            results = await job_search_tool.ainvoke({
                "titleSearch": query,
                "locationSearch": location,
                "limit": 10
            })

            for item in results:
                if item.get('type') != 'text':
                    continue
                run = self._loads_json_object(item['text'])
                if not run:
                    continue
                default_ds = (
                    run.get('storages', {})
                    .get('datasets', {})
                    .get('default', {})
                )
                dataset_id = default_ds.get('id')
                item_count = default_ds.get('itemCount', 0)
                if dataset_id:
                    print(f"Dataset {dataset_id} ready ({item_count} items).")
                    if not item_count:
                        # Run succeeded but matched no postings — nothing to fetch.
                        return None
                    return dataset_id

            return None

        except StopIteration:
            print(f"The '{self.SEARCH_TOOL_NAME}' tool is not available.")
            return None
        except Exception as e:
            print(f"Error searching jobs: {e}")
            return None

    @staticmethod
    def _loads_json_object(text: str) -> Optional[Dict[str, Any]]:
        """Parse a JSON object from MCP text output, tolerant of surrounding noise."""
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end != 0:
                return json.loads(text[start:end], strict=False)
        except Exception:
            return None
        return None

    async def fetch_job_results(self, dataset_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieves the dataset using the ID and parses the JSON text into a list of dictionaries.
        """
        try:
            get_output_tool = next(
                tool for tool in self.tools
                if tool.name == self.OUTPUT_TOOL_NAME
            )

            print(f"\nRetrieving job results from dataset: {dataset_id}...")
            results = await get_output_tool.ainvoke({
                "datasetId": dataset_id,
                "limit": limit
            })
            
            all_jobs = []
            for item in results:
                if item['type'] == 'text':
                    jobs = self._parse_job_data(item['text'])
                    all_jobs.extend(jobs)
            
            return all_jobs

        except StopIteration:
            print(f"The '{self.OUTPUT_TOOL_NAME}' tool is not available.")
            return []
        except Exception as e:
            print(f"Error retrieving job results: {e}")
            return []

    def _parse_job_data(self, text_data: str) -> List[Dict]:
        """Internal helper to parse the text data to extract job postings as JSON"""
        try:
            # Remove markdown code blocks if present
            text_data = re.sub(r'^```json\s*', '', text_data)
            text_data = re.sub(r'\s*```$', '', text_data)
            
            # Extract the JSON part
            start_idx = text_data.find('[')
            end_idx = text_data.rfind(']') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = text_data[start_idx:end_idx]
                return json.loads(json_str, strict=False)
            return []
        except json.JSONDecodeError:
            # Try alternative parsing - split by job objects
            try:
                jobs = []
                depth = 0
                start = -1
                current_job = ""
                
                for i, char in enumerate(text_data):
                    if char == '{':
                        if depth == 0:
                            start = i
                        depth += 1
                    elif char == '}':
                        depth -= 1
                        if depth == 0 and start != -1:
                            current_job = text_data[start:i+1]
                            try:
                                job = json.loads(current_job, strict=False)
                                jobs.append(job)
                            except:
                                pass
                            start = -1
                            current_job = ""
                return jobs
            except Exception:
                return []
        except Exception as e:
            print(f"Error parsing job data: {e}")
            return []






































