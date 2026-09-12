import logging
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)



from config import llm
from dotenv import load_dotenv
from tools.job_scrapper_tool import JobScraperService
import asyncio
import os


# Import LLM from your existing config
from config import llm

load_dotenv()

logger = logging.getLogger(__name__)

class MarketAnalysisAgent:
    def __init__(self):
        self.scraper = JobScraperService()
        self.llm = llm

    async def summarize_job(self, job_data: dict):
        """Use LLM to summarize a job posting"""
        try:
            # Extract salary info safely
            salary_min = job_data.get('ai_salary_minvalue', 0)
            salary_max = job_data.get('ai_salary_maxvalue', 0)
            salary_currency = job_data.get('ai_salary_currency', 'USD')
            salary_unit = job_data.get('ai_salary_unittext', 'YEAR')
            
            salary_str = "Not specified"
            if salary_min and salary_max:
                salary_str = f"${salary_min:,} - ${salary_max:,} {salary_currency} per {salary_unit}"
            
            # Create a prompt for the LLM.
            #
            # The description budget is 6000 chars, not 500. At 500 the real skills sat past the
            # cut (a 6500-char posting reached the model at 8%) and the model filled the gap from
            # priors — inventing certifications, tool stacks and benefits the posting never named.
            # The fabrication is what makes it expensive, not the length.
            prompt = f"""
            You are the Market Agent for the MindMorph learning platform. Downstream, a Consensus
            agent turns your output into skill nodes for a learning path, so the only thing that
            matters here is which skills, tools and technologies THIS posting actually demands.

            Job Title: {job_data.get('title', 'N/A')}
            Company: {job_data.get('organization', 'N/A')}
            Location: {', '.join(job_data.get('locations_derived', ['N/A']))}
            Salary Range: {salary_str}
            Employment Type: {', '.join(job_data.get('employment_type', ['N/A']))}

            Job Description:
            {job_data.get('description_text', 'N/A')[:6000]}

            Report, from the posting text above and nothing else:
            1. The work the role actually does, in a few lines.
            2. Required skills, tools, languages, platforms and technologies, named exactly as the
               posting names them.
            3. Skills and tools listed as preferred or nice-to-have, kept separate from required.
            4. The seniority signal: years of experience, scope or level, if the posting states one.

            Honesty rules, which override everything above:
            - Report only what this posting states. Never add a skill, tool, certification,
              qualification, benefit or company fact because it is typical for the role. If the
              posting does not name a tool, that tool must not appear in your output at all, not
              even as an example or a parenthetical.
            - If a section has nothing in the posting to fill it, write one line saying the posting
              does not state it, and move on.
            - This is ONE posting, not a market survey. Describe what this employer asks for. Do not
              write that anything is "in demand", "widely required", or common across the market.

            Do not write a benefits/perks section or a company overview. Do not add career advice or
            application tips. Compact bullets; every line names a skill, tool or stated requirement.
            """
            
            # Get response from LLM
            logger.info("Market: summarizing job posting %r", job_data.get("title", "N/A"))
            response = await self.llm.ainvoke(prompt)
            return response.content

        except Exception:
            logger.exception("Market: error summarizing job with LLM")
            return None

    async def extract_job_title(self, query: str) -> str:
        """Distill a learning goal / Scout question into a concise job title.

        The LinkedIn actor's `titleSearch` matches job titles, so a verbose question
        (e.g. "What Python skills are in demand?") returns zero results. We reduce it
        to a 2-4 word role title (e.g. "machine learning engineer").
        """
        prompt = (
            "Extract the single most relevant job title (2-4 words) to search a job board, "
            "based on the request below. Reply with ONLY the title text - no quotes, no punctuation, "
            "no explanation.\n\n"
            f"Request: {query}"
        )
        try:
            resp = await self.llm.ainvoke(prompt)
            title = (resp.content or "").strip().strip('"').splitlines()[0].strip()
            return title or query
        except Exception:
            logger.exception("Market: job-title extraction failed, using raw query")
            return query

    async def run_analysis(self, search_query: str, location: str):
        # 1. Initialize Scraper
        await self.scraper.initialize()

        # 2. Perform Search
        dataset_id = await self.scraper.search_jobs(search_query, location)
        
        if not dataset_id:
            print("No dataset ID returned. Exiting.")
            return

        print(f"Dataset ID found: {dataset_id}")

        # 3. Fetch Raw Data
        jobs_list = await self.scraper.fetch_job_results(dataset_id)
        
        print(f"Successfully parsed {len(jobs_list)} job postings")

        # 4. Process with LLM (Analyze the first job as an example)
        if jobs_list:
            first_job = jobs_list[0]
            
            print(f"\n{'='*60}")
            print(f"ANALYZING FIRST JOB POSTING")
            print(f"{'='*60}\n")
            
            print(f"Job Title: {first_job.get('title')}")
            print(f"Company: {first_job.get('organization')}")
            print(f"Location: {', '.join(first_job.get('locations_derived', []))}")
            print(f"Job URL: {first_job.get('url', 'N/A')}")
            print(f"\n{'='*60}")
            print(f"GENERATING AI SUMMARY...")
            print(f"{'='*60}\n")
            
            summary = await self.summarize_job(first_job)
            
            if summary:
                print(summary)
                print(f"\n{'='*60}\n")
        else:
            print("No jobs found to analyze.")

async def main():
    agent = MarketAnalysisAgent()
    
    # Input parameters
    query = "Senior Machine Learning Engineer"
    loc = "United States"
    
    await agent.run_analysis(query, loc)

if __name__ == "__main__":
    asyncio.run(main())