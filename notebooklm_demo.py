import asyncio
import sys
import os
import logging
from datetime import datetime
from notebooklm import NotebookLMClient
import config

# Ensure logs directory exists
os.makedirs(config.LOGS_DIR, exist_ok=True)

# Reconfigure stdout to use UTF-8 on Windows to avoid UnicodeEncodeError for characters like the Rupee symbol (₹)
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Configure Logging
log_file_path = os.path.join(config.LOGS_DIR, "notebooklm_demo.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("notebooklm_demo")

async def get_client():
    """Initializes and returns the NotebookLM client with auth recovery instructions."""
    logger.info("Initializing NotebookLM Client...")
    try:
        # NotebookLMClient.from_storage() looks for the default profile's storage_state.json
        client_ctx = NotebookLMClient.from_storage()
        return client_ctx
    except Exception as e:
        logger.error("Authentication failed or session expired.")
        logger.error(f"Technical error: {e}")
        logger.error("\n" + "="*70)
        logger.error("AUTHENTICATION RECOVERY REQUIRED:")
        logger.error("Your Google session cookies may have expired or your credentials changed.")
        logger.error("Please run the following command in your terminal to authenticate again:")
        logger.error("    notebooklm login")
        logger.error("="*70 + "\n")
        sys.exit(1)

async def get_or_create_notebook(client, notebook_name):
    """
    Finds or creates the notebook. It uses a local cache file (notebook_id.txt)
    first, falls back to searching by name, and creates a new one if not found.
    """
    cache_file = os.path.join(config.WORKSPACE_DIR, "notebook_id.txt")
    cached_id = None

    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_id = f.read().strip()
            logger.info(f"Found cached notebook ID locally: {cached_id}")
        except Exception as e:
            logger.warning(f"Could not read notebook ID cache file: {e}")

    try:
        logger.info("Fetching notebooks list from NotebookLM...")
        notebooks = await client.notebooks.list()
    except Exception as e:
        logger.error("Failed to communicate with NotebookLM server. Please verify your internet connection or run 'notebooklm login'.")
        logger.error(f"Details: {e}")
        sys.exit(1)

    # 1. Try matching with the cached ID
    if cached_id:
        for nb in notebooks:
            if nb.id == cached_id:
                logger.info(f"Successfully matched cached ID. Reusing Notebook: '{nb.title}' (ID: {nb.id})")
                return nb
        logger.info("Cached notebook ID was not found on the server (it may have been deleted).")

    # 2. Try matching by Name
    for nb in notebooks:
        if nb.title == notebook_name:
            logger.info(f"Found existing notebook by name match. Reusing Notebook: '{nb.title}' (ID: {nb.id})")
            # Write/refresh cache
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    f.write(nb.id)
            except Exception as e:
                logger.warning(f"Could not write notebook ID to cache file: {e}")
            return nb

    # 3. Create a new notebook
    logger.info(f"Notebook '{notebook_name}' not found. Creating a new notebook...")
    try:
        nb = await client.notebooks.create(notebook_name)
        logger.info(f"Successfully created notebook: '{nb.title}' (ID: {nb.id})")
        # Save to cache
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(nb.id)
        except Exception as e:
            logger.warning(f"Could not write notebook ID to cache file: {e}")
        return nb
    except Exception as e:
        logger.error(f"Failed to create notebook: {e}")
        sys.exit(1)

async def upload_sources(client, notebook_id):
    """Uploads configured local files and URLs, skipping files that already exist."""
    try:
        existing_sources = await client.sources.list(notebook_id)
        existing_titles = {src.title.lower() for src in existing_sources if src.title}
        existing_urls = {src.url.lower() for src in existing_sources if src.url}
    except Exception as e:
        logger.warning(f"Failed to retrieve existing sources. Duplicate checking will be skipped. Error: {e}")
        existing_titles = set()
        existing_urls = set()

    # Upload local files
    for filepath in config.LOCAL_FILES:
        if not os.path.exists(filepath):
            logger.warning(f"Local file not found, skipping: {filepath}")
            continue

        filename = os.path.basename(filepath)
        if filename.lower() in existing_titles:
            logger.info(f"Local file '{filename}' already exists in notebook. Skipping upload.")
            continue

        logger.info(f"Uploading local file: {filename}...")
        try:
            # client.sources.add_file uploads the file.
            await client.sources.add_file(notebook_id, filepath)
            logger.info(f"Successfully uploaded file: {filename}")
        except Exception as e:
            logger.error(f"Upload failed for file '{filename}': {e}")

    # Upload URLs
    for url in config.URLS:
        url_lower = url.lower()
        # Some URLs might match the title or URL fields in the source list
        if url_lower in existing_urls or url_lower in existing_titles:
            logger.info(f"URL source '{url}' already exists in notebook. Skipping upload.")
            continue

        logger.info(f"Uploading URL: {url}...")
        try:
            # wait=True ensures it is fully submitted
            await client.sources.add_url(notebook_id, url, wait=True)
            logger.info(f"Successfully uploaded URL: {url}")
        except Exception as e:
            logger.error(f"Upload failed for URL '{url}': {e}")

async def wait_for_sources_ready(client, notebook_id):
    """
    Checks processing status of all sources in the notebook.
    Retries/polls until all sources are processed or the timeout is reached.
    """
    logger.info("Waiting for all sources to finish indexing...")
    max_checks = 12  # 12 * 5 seconds = 60 seconds max wait
    
    for attempt in range(1, max_checks + 1):
        try:
            sources = await client.sources.list(notebook_id)
            all_ready = True
            processing_count = 0
            error_count = 0
            
            for src in sources:
                # status: 1=processing, 2=ready, 3=error, 5=preparing
                if src.status in (1, 5):
                    all_ready = True  # We have at least one processing
                    processing_count += 1
                    all_ready = False
                elif src.status == 3:
                    error_count += 1
                    logger.warning(f"Source '{src.title}' (ID: {src.id}) failed to index (status error).")
            
            if all_ready:
                if error_count > 0:
                    logger.info(f"Sources checked. Ready with {error_count} failed indexing error(s).")
                else:
                    logger.info("All sources are fully indexed and ready.")
                return True
                
            logger.info(f"Attempt {attempt}/{max_checks}: {processing_count} source(s) are still indexing. Waiting 5s...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.warning(f"Error checking sources status: {e}. Retrying...")
            await asyncio.sleep(5)
            
    logger.warning("Timeout reached waiting for sources to process. Proceeding to query...")
    return False

async def query_notebook(client, notebook_id, query):
    """
    Queries the notebook. Implements a retry loop to handle potential transient
    errors or slow indexing.
    """
    logger.info(f"Executing Query: '{query}'...")
    
    for attempt in range(1, config.MAX_QUERY_RETRIES + 1):
        try:
            response = await client.chat.ask(notebook_id, query)
            
            # Print response
            answer = response.answer if hasattr(response, 'answer') else str(response)
            logger.info("\n" + "="*70)
            logger.info(f"NotebookLM Response:\n{answer}")
            logger.info("="*70 + "\n")
            return True
            
        except Exception as e:
            logger.warning(f"Query attempt {attempt}/{config.MAX_QUERY_RETRIES} failed: {e}")
            if attempt < config.MAX_QUERY_RETRIES:
                logger.info(f"Retrying query in {config.RETRY_DELAY_SECONDS}s...")
                await asyncio.sleep(config.RETRY_DELAY_SECONDS)
            else:
                logger.error("All query retry attempts exhausted. Query failed.")
                return False

def run_cli_command(args):
    """Executes a notebooklm CLI command using the virtual environment interpreter."""
    import subprocess
    cli_exe = os.path.join(config.WORKSPACE_DIR, ".venv", "Scripts", "notebooklm")
    if sys.platform != 'win32':
        cli_exe = os.path.join(config.WORKSPACE_DIR, ".venv", "bin", "notebooklm")
        
    if not os.path.exists(cli_exe):
        cli_exe = "notebooklm"  # Fallback to system PATH
        
    cmd = [cli_exe] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, f"Command failed: {e.stderr or e.stdout}"
    except Exception as e:
        return False, f"Process execution failed: {e}"

async def interactive_loop(client, notebook_id):
    """Starts an interactive session to query and add sources dynamically."""
    logger.info("\n" + "="*70)
    logger.info("INTERACTIVE NOTEBOOKLM SESSION STARTED")
    logger.info("Commands:")
    logger.info("  /add <path_or_url>  - Ingest a local file path or URL (e.g. YouTube video)")
    logger.info("  /list               - List all ingested sources and their index status")
    logger.info("  /podcast [prompt]   - Generate and download Audio Podcast to logs/podcast.mp3")
    logger.info("  /paper [prompt]     - Generate and download Briefing Paper to logs/paper.md")
    logger.info("  /studyguide         - Generate and download Study Guide to logs/study_guide.md")
    logger.info("  /quiz [prompt]      - Generate and download a Quiz to logs/quiz.md")
    logger.info("  /flashcards         - Generate and download Flashcards to logs/flashcards.md")
    logger.info("  /exit               - Exit the session")
    logger.info("  Or just type your question to query the notebook.")
    logger.info("="*70 + "\n")
    
    # Enable reading input asynchronously in a executor so it doesn't block the loop
    loop = asyncio.get_event_loop()
    
    while True:
        try:
            # Run blocking input() inside a separate thread
            user_input = await loop.run_in_executor(None, input, "[NotebookLM] > ")
            user_input = user_input.strip()
        except (KeyboardInterrupt, EOFError):
            logger.info("\nExiting session...")
            break
            
        if not user_input:
            continue
            
        user_input_lower = user_input.lower()
        if user_input_lower == '/exit':
            logger.info("Exiting session...")
            break
            
        elif user_input_lower == '/list':
            try:
                sources = await client.sources.list(notebook_id)
                logger.info("\nIngested Sources:")
                for src in sources:
                    status_str = "Ready" if src.status == 2 else ("Error" if src.status == 3 else "Indexing")
                    logger.info(f" - {src.title or src.url} [{status_str}]")
                logger.info("")
            except Exception as e:
                logger.error(f"Failed to list sources: {e}")
            continue
            
        elif user_input_lower.startswith('/podcast'):
            prompt = user_input[8:].strip()
            logger.info("Triggering Audio Overview Podcast generation on Google servers (this can take 2-4 minutes)...")
            
            gen_args = ["generate", "audio", "-n", notebook_id, "--wait"]
            if prompt:
                gen_args.append(prompt)
                
            success, out = run_cli_command(gen_args)
            if not success:
                logger.error(f"Failed to generate podcast: {out}")
                continue
                
            logger.info("Audio generation complete. Downloading podcast to logs/podcast.mp3...")
            output_file = os.path.join(config.LOGS_DIR, "podcast.mp3")
            success, out = run_cli_command(["download", "audio", "-n", notebook_id, "--force", output_file])
            if success:
                logger.info(f"Success! Podcast downloaded to: {output_file}")
            else:
                logger.error(f"Failed to download podcast file: {out}")
            continue
            
        elif user_input_lower.startswith('/paper'):
            prompt = user_input[6:].strip()
            logger.info("Generating Briefing Paper/Report on Google servers...")
            
            gen_args = ["generate", "report", "-n", notebook_id, "--wait"]
            if prompt:
                # If they passed specific guidelines, run it custom
                gen_args.extend(["--format", "custom", prompt])
                
            success, out = run_cli_command(gen_args)
            if not success:
                logger.error(f"Failed to generate report: {out}")
                continue
                
            logger.info("Report generation complete. Downloading briefing paper to logs/paper.md...")
            output_file = os.path.join(config.LOGS_DIR, "paper.md")
            success, out = run_cli_command(["download", "report", "-n", notebook_id, "--force", output_file])
            if success:
                logger.info(f"Success! Briefing paper downloaded to: {output_file}")
            else:
                logger.error(f"Failed to download report file: {out}")
            continue
            
        elif user_input_lower == '/studyguide':
            logger.info("Generating Study Guide on Google servers...")
            success, out = run_cli_command(["generate", "report", "-n", notebook_id, "--format", "study-guide", "--wait"])
            if not success:
                logger.error(f"Failed to generate study guide: {out}")
                continue
                
            logger.info("Study guide complete. Downloading to logs/study_guide.md...")
            output_file = os.path.join(config.LOGS_DIR, "study_guide.md")
            success, out = run_cli_command(["download", "report", "-n", notebook_id, "--force", output_file])
            if success:
                logger.info(f"Success! Study guide downloaded to: {output_file}")
            else:
                logger.error(f"Failed to download study guide: {out}")
            continue
            
        elif user_input_lower.startswith('/quiz'):
            prompt = user_input[5:].strip()
            logger.info("Generating Quiz on Google servers...")
            
            gen_args = ["generate", "quiz", "-n", notebook_id, "--wait"]
            if prompt:
                gen_args.append(prompt)
                
            success, out = run_cli_command(gen_args)
            if not success:
                logger.error(f"Failed to generate quiz: {out}")
                continue
                
            logger.info("Quiz complete. Downloading to logs/quiz.md...")
            output_file = os.path.join(config.LOGS_DIR, "quiz.md")
            success, out = run_cli_command(["download", "quiz", "-n", notebook_id, "--force", output_file])
            if success:
                logger.info(f"Success! Quiz downloaded to: {output_file}")
            else:
                logger.error(f"Failed to download quiz: {out}")
            continue

        elif user_input_lower == '/flashcards':
            logger.info("Generating Flashcards on Google servers...")
            success, out = run_cli_command(["generate", "flashcards", "-n", notebook_id, "--wait"])
            if not success:
                logger.error(f"Failed to generate flashcards: {out}")
                continue
                
            logger.info("Flashcards complete. Downloading to logs/flashcards.md...")
            output_file = os.path.join(config.LOGS_DIR, "flashcards.md")
            success, out = run_cli_command(["download", "flashcards", "-n", notebook_id, "--force", output_file])
            if success:
                logger.info(f"Success! Flashcards downloaded to: {output_file}")
            else:
                logger.error(f"Failed to download flashcards: {out}")
            continue
            
        elif user_input_lower.startswith('/add '):
            source_path = user_input[5:].strip()
            if not source_path:
                logger.warning("Please specify a file path or URL after /add")
                continue
                
            # Check if web URL
            if source_path.lower().startswith(('http://', 'https://')):
                logger.info(f"Uploading URL source dynamically: {source_path}...")
                try:
                    await client.sources.add_url(notebook_id, source_path, wait=True)
                    logger.info("URL successfully added and indexed.")
                except Exception as e:
                    logger.error(f"Failed to add URL: {e}")
            else:
                # Local file
                if not os.path.exists(source_path):
                    logger.error(f"Local file not found: {source_path}")
                else:
                    logger.info(f"Uploading file source dynamically: {source_path}...")
                    try:
                        await client.sources.add_file(notebook_id, source_path)
                        logger.info("File successfully uploaded.")
                        await wait_for_sources_ready(client, notebook_id)
                    except Exception as e:
                        logger.error(f"Failed to add file: {e}")
            continue
            
        # Default: Treat as a query
        await query_notebook(client, notebook_id, user_input)

async def main():
    client_ctx = await get_client()
    
    async with client_ctx as client:
        # 1. Fetch or create notebook
        nb = await get_or_create_notebook(client, config.NOTEBOOK_NAME)
        
        # 2. Upload sources (deduplicated)
        await upload_sources(client, nb.id)
        
        # 3. Wait for indexing to complete
        await wait_for_sources_ready(client, nb.id)
        
        # 4. Ask questions
        # If the user passed a custom query in the command line, ask that.
        # Otherwise, ask the default questions in config.py
        if len(sys.argv) > 1:
            if sys.argv[1] in ('-i', '--interactive'):
                await interactive_loop(client, nb.id)
            else:
                custom_query = " ".join(sys.argv[1:])
                await query_notebook(client, nb.id, custom_query)
        else:
            for question in config.QUESTIONS:
                await query_notebook(client, nb.id, question)
            
    logger.info("NotebookLM workflow completed successfully!")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main())
