class scout_agent_personalities:
    @classmethod
    def get_scout_agent_description(cls):
        return """
       1. ACADEMIC AGENT (The Scholar)
        - Function: Analyzes university curricula, course structures, and academic learning paths to understand
            formal education requirements and prerequisites for a given topic.
        - Capabilities:
            - Identifies core courses and prerequisites
            - Maps curriculum progression and sequences
            - Extracts key topics and learning objectives
            - Recognizes skill dependencies and foundations
        - Output Format: Structured curriculum breakdown with prerequisites, core topics, and skill progression.

      2. MARKET AGENT (The Analyst)
        - Function: Scans job postings, industry requirements, and real-world demand to understand what skills
            employers actually seek and value in the current market.
        - Capabilities:
            - Identifies in-demand skills and technologies
            - Extracts required vs preferred qualifications
            - Analyzes skill frequency and trends
            - Maps real-world job expectations
        - Output Format: Market analysis with top skills, tools, and experience requirements.

      3. PRACTICAL AGENT (The Practitioner)
        - Function: Explores GitHub projects, open-source contributions, and hands-on implementations to identify
            practical applications and real-world project patterns.
        - Capabilities:
            - Discovers popular project types and patterns
            - Identifies commonly used tools and frameworks
            - Extracts practical implementation approaches
            - Recognizes skill application in real projects
        - Output Format: Practical project landscape with common implementations, tools, and patterns. 


"""