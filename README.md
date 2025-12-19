# MindMorph Learning Platform

## Environment Setup

### 1. Prerequisites

Ensure you have [Conda](https://docs.conda.io/en/latest/) installed (Anaconda or Miniconda).

### 2. Create and Activate Virtual Environment

Open your terminal or command prompt and run the following commands:

```bash
# Create a new conda environment named 'mindmorph' with Python 3.11
conda create -n mindmorph python=3.11 -y

# Activate the environment
conda activate mindmorph
```

### 3. Install Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration

1.  Create a `.env` file in the root directory.
2.  Add your Groq API key (required for the LLM):

```env
GROQ_API_KEY=your_api_key_here
```

## Running the Content Generator

The Content Generator Agent allows you to generate educational content in different formats (Boost, Builder, Sprint).

To run the interactive agent:

```bash
python agents/content_generator/content_agent.py 
```

### Usage

1.  Open `agents/content_generator/content_agent.py` in your editor.
2.  Scroll to the bottom of the file to the `__main__` block.
3.  Manually modify the `generate_content` call with your **Topic** and **Format** ("A", "B", or "C"):

    ```python
    # Format Options:
    # "A": 5-min Boost (Quick summary)
    # "B": 20-min Builder (Standard lesson)
    # "C": 2-hour Sprint (Deep dive)

    lesson = agent.generate_content("Your Topic Here", "A")
    ```

4.  Run the script:

    ```bash
    python agents/content_generator/content_agent.py
    ```
