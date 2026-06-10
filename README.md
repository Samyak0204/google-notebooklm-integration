# Google NotebookLM Python Integration

A robust, professional Python integration and CLI wrapper for automating workflows in Google's **NotebookLM**. 

This project utilizes the community-maintained `notebooklm-py` SDK to programmatically interface with NotebookLM's internal RPC endpoints. It supports automated notebook creation, session recovery, source upload deduplication, indexing checks, and RAG chat querying.

---

## Project Structure

```
NLMP/
├── sources/               # Place local files to upload here
│   ├── notes.txt          # Sample text source
│   └── sample.pdf         # Sample PDF source
├── .gitignore             # Excludes venv, logs, credentials, and local ID cache
├── config.py              # Central configurations (notebook name, sources, URLs, queries)
├── notebook_id.txt        # Local cache file (automatically generated, ignored by git)
├── notebooklm_demo.py     # Main Python integration script
└── requirements.txt       # Version-locked package dependencies
```

---

## Setup & Installation

### 1. Prerequisites
- Python 3.10 or higher
- An active Google Account with access to [Google NotebookLM](https://notebooklm.google.com)

### 2. Clone and Setup Environment
Open your terminal in the workspace directory and set up a Python virtual environment:

```bash
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On Windows CMD:
.venv\Scripts\activate.bat
# On macOS/Linux:
source .venv/bin/activate
```

### 3. Install Dependencies
Install the required packages and download Playwright's Chromium browser for authentication:

```bash
# Install package dependencies
pip install -r requirements.txt

# Install the Playwright Chromium engine
playwright install chromium
```

---

## Authentication

NotebookLM does not have a public developer API key. Instead, authentication is managed by logging in via a browser once to capture your session cookies. 

Run the login command in your terminal:
```bash
notebooklm login
```
A browser window (Chromium) will pop up. **Log in to your Google Account** inside that window. Once you successfully log in, the CLI will automatically extract the session cookies, save them to a local configuration folder (`~/.notebooklm/profiles/default/storage_state.json`), and close the browser.

> [!WARNING]
> The saved `storage_state.json` contains your active session cookies. Treat it as sensitive data (like a password). It is excluded from Git via `.gitignore` and should never be committed to version control.

---

## Configuration

You can customize the script's behavior by modifying [config.py](config.py):

- **`NOTEBOOK_NAME`**: The name of the notebook. By default, it generates `"Research Notebook - YYYY-MM-DD"`.
- **`LOCAL_FILES`**: List of paths to local files inside the `sources/` folder to upload.
- **`URLS`**: List of web URLs (or YouTube videos) to ingest.
- **`QUESTIONS`**: Default questions to execute sequentially when running the script without arguments.
- **`MAX_QUERY_RETRIES` / `RETRY_DELAY_SECONDS`**: Query retry settings to handle slow server-side indexing.

---

## How to Run & Ingest

Run the integration script:
```bash
python notebooklm_demo.py
```

### What the script does:
1. **Verifies Session**: Checks if your login cookies are valid. If they are expired, it outputs recovery instructions.
2. **Notebook Reuse**: Checks your NotebookLM account for an existing notebook matching `NOTEBOOK_NAME`. If found, it reuses it; if not, it creates a new one. **It automatically creates and writes the ID to `notebook_id.txt` for faster access on future runs (you do not need to create this file manually).**
3. **Deduplicates Uploads**: Lists the sources already in the notebook. It only uploads files or URLs that aren't already present.
4. **Waits for Indexing**: Polls the status of each source until the server finishes processing them.
5. **Executes Queries**: Automatically runs the questions defined in `config.py` and displays the RAG responses.

---

## How to Query

You can query your notebook in four different ways:

### Option 1: Run with a Custom Argument (Recommended)
You can ask custom questions on the fly by passing the query directly as an argument:
```bash
python notebooklm_demo.py "What is the key architecture of Project Phoenix?"
```
*This will run the script, check for new sources, and answer only your custom question.*

### Option 2: Run in Interactive Session Mode
You can start a dynamic interactive session in your terminal where you can add files, URLs, list sources, and chat continuously:
```bash
python notebooklm_demo.py -i
```
- `/add <path_or_url>`: Upload a local PDF/TXT file or URL dynamically.
- `/list`: Display all ingested sources and their indexing status.
- `/podcast [prompt]`: Generate and download Audio Podcast to `logs/podcast.mp3`.
- `/paper [prompt]`: Generate and download Briefing Paper/Report to `logs/paper.md`.
- `/studyguide`: Generate and download Study Guide to `logs/study_guide.md`.
- `/quiz [prompt]`: Generate and download a Quiz to `logs/quiz.md`.
- `/flashcards`: Generate and download Study Flashcards to `logs/flashcards.md`.
- Type any text: Query the notebook and fetch the RAG response.
- `/exit`: Quit the interactive loop.

### Option 3: Configure Default Questions
Edit the `QUESTIONS` list in `config.py` and run the script:
```bash
python notebooklm_demo.py
```

### Option 4: Use the Native CLI
Since you are logged in, you can query directly using the `notebooklm` command line utility:

1. Target your notebook (copy the ID from `notebook_id.txt`):
   ```bash
   notebooklm use <notebook_id>
   ```
2. Ask your question:
   ```bash
   notebooklm ask "List all action items."
   ```

---

## Troubleshooting & Diagnostics

Run the doctor diagnostic tool to check profile configuration, cookie validity, and directory permissions:
```bash
notebooklm doctor
```
If your session expires or fails, simply rerun:
```bash
notebooklm login
```
