import os
from datetime import datetime

# Notebook configuration
# Reuses this name; can be made dynamic by appending current date if desired
current_date = datetime.now().strftime("%Y-%m-%d")
NOTEBOOK_NAME = f"Research Notebook - {current_date}"
REUSE_NOTEBOOK = True

# Directories
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_DIR = os.path.join(WORKSPACE_DIR, "sources")
LOGS_DIR = os.path.join(WORKSPACE_DIR, "logs")

# Ingestion Sources
# Local files within the sources/ folder
LOCAL_FILES = [
    os.path.join(SOURCES_DIR, "notes.txt"),
    os.path.join(SOURCES_DIR, "sample.pdf"),
    os.path.join(SOURCES_DIR, "Techno-Economic Analysis of Green Hydrogen Production through Electrolysis.pdf")
]

# Web URL sources
URLS = [
    "https://example.com"
]

# Queries to execute against the notebook
QUESTIONS = [
    "Summarize the main ideas from the uploaded sources.",
    "List key action items or future implications discussed in the sources."
]

# Query retry settings (for waiting for sources to index)
MAX_QUERY_RETRIES = 10
RETRY_DELAY_SECONDS = 5
