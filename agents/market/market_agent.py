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
            
            # Create a prompt for the LLM
            prompt = f"""
            Please provide a concise and well-structured summary of the following job posting:
            
            Job Title: {job_data.get('title', 'N/A')}
            Company: {job_data.get('organization', 'N/A')}
            Location: {', '.join(job_data.get('locations_derived', ['N/A']))}
            Salary Range: {salary_str}
            Posted Date: {job_data.get('date_posted', 'N/A')}
            Employment Type: {', '.join(job_data.get('employment_type', ['N/A']))}
            
            Job Description:
            {job_data.get('description_text', 'N/A')[:500]}
            
            Please summarize this job posting including:
            1. Key responsibilities
            2. Required qualifications
            3. Preferred qualifications
            4. Benefits and perks
            5. Company overview
            
            Keep the summary clear, concise, and well-formatted.
            """
            
            # Get response from LLM
            print("Sending data to LLM for summarization...")
            response = await self.llm.ainvoke(prompt)
            return response.content
            
        except Exception as e:
            print(f"Error summarizing with LLM: {e}")
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
        except Exception as e:
            print(f"Job-title extraction failed, using raw query: {e}")
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