import streamlit as st
import asyncio
import sys
import os
import time
import logging
from datetime import datetime
from notebooklm import NotebookLMClient
from notebooklm.types import SourceStatus
import config

# Set page configuration
st.set_page_config(
    page_title="NotebookLM AI Dashboard",
    page_icon="📓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Set Windows asyncio policy
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Setup logging
os.makedirs(config.LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(config.LOGS_DIR, "ui_app.log"), encoding="utf-8")
    ]
)
logger = logging.getLogger("ui_app")

# Ensure temporary source dir exists
os.makedirs(config.SOURCES_DIR, exist_ok=True)

# Define async-run utility
def run_async(coro):
    return asyncio.run(coro)

async def run_client_op(op_func):
    """Context wrapper to resolve and run client operations securely."""
    client_ctx = NotebookLMClient.from_storage()
    async with client_ctx as client:
        return await op_func(client)

# Define CLI runner for generation tasks
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
        env = os.environ.copy()
        env["PAGER"] = "cat"
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, f"Command failed: {e.stderr or e.stdout}"
    except Exception as e:
        return False, f"Process execution failed: {e}"

# Custom CSS for rich premium UI styling
def inject_custom_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Sleek gradient background */
    .stApp {
        background: radial-gradient(circle at 50% 50%, #17162E 0%, #090A0F 100%);
    }
    
    /* Styled headings */
    h1, h2, h3 {
        font-weight: 700 !important;
        background: linear-gradient(135deg, #a855f7 0%, #6c5ce7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* Chat message bubble styling */
    [data-testid="stChatMessage"] {
        background-color: rgba(25, 27, 39, 0.65) !important;
        border: 1px solid rgba(108, 92, 231, 0.15) !important;
        border-radius: 12px !important;
        padding: 1.2rem !important;
        margin-bottom: 0.8rem !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        backdrop-filter: blur(8px);
    }
    
    [data-testid="stChatMessage"][data-test-user="assistant"] {
        border-left: 5px solid #a855f7 !important;
    }
    
    [data-testid="stChatMessage"][data-test-user="user"] {
        border-left: 5px solid #6c5ce7 !important;
    }
    
    /* Styled buttons */
    div.stButton > button {
        background: linear-gradient(135deg, #6c5ce7 0%, #a855f7 100%) !important;
        color: white !important;
        font-weight: 600 !important;
        border: none !important;
        border-radius: 8px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 10px rgba(108, 92, 231, 0.3) !important;
    }
    
    div.stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 15px rgba(108, 92, 231, 0.5) !important;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: rgba(13, 14, 21, 0.95) !important;
        backdrop-filter: blur(12px);
        border-right: 1px solid rgba(108, 92, 231, 0.25);
    }
    
    /* Tab headers styling */
    div[data-testid="stTabs"] button {
        font-size: 16px !important;
        font-weight: 600 !important;
    }
    
    /* Status indicators */
    .status-dot {
        height: 10px;
        width: 10px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 6px;
    }
    
    .status-ready { background-color: #2ecc71; box-shadow: 0 0 6px #2ecc71; }
    .status-indexing { background-color: #f1c40f; box-shadow: 0 0 6px #f1c40f; animation: pulse 1.5s infinite; }
    .status-error { background-color: #e74c3c; box-shadow: 0 0 6px #e74c3c; }
    
    @keyframes pulse {
        0% { opacity: 0.4; }
        50% { opacity: 1; }
        100% { opacity: 0.4; }
    }
    
    /* Expanders styling */
    div[data-testid="stExpander"] {
        background-color: rgba(25, 27, 39, 0.45) !important;
        border: 1px solid rgba(108, 92, 231, 0.1) !important;
        border-radius: 8px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Run CSS injection
inject_custom_css()

# Cache helper functions for notebook_id.txt
def get_cached_notebook_id():
    cache_file = os.path.join(config.WORKSPACE_DIR, "notebook_id.txt")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return None

def set_cached_notebook_id(nb_id):
    cache_file = os.path.join(config.WORKSPACE_DIR, "notebook_id.txt")
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(nb_id)
    except Exception as e:
        logger.warning(f"Could not save cached ID: {e}")

# Check authentication status
if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = None
    st.session_state.auth_error = ""

def check_authentication():
    async def test_auth(client):
        # Listing notebooks is a lightweight way to check session validity
        return await client.notebooks.list()
        
    try:
        run_async(run_client_op(test_auth))
        st.session_state.auth_ok = True
        st.session_state.auth_error = ""
    except Exception as e:
        st.session_state.auth_ok = False
        st.session_state.auth_error = str(e)

if st.session_state.auth_ok is None:
    check_authentication()

# ----------------- AUTHENTICATION ERROR VIEW -----------------
if not st.session_state.auth_ok:
    st.title("📓 NotebookLM AI Dashboard")
    st.markdown("## 🔑 Authentication Required")
    st.warning("Your Google Account session cookies are missing, expired, or invalid.")
    
    st.markdown("""
    ### How to Authenticate:
    1. Open your terminal in the project directory.
    2. Make sure your virtual environment is active:
       ```bash
       .venv\\Scripts\\Activate.ps1
       ```
    3. Run the login command:
       ```bash
       notebooklm login
       ```
    4. A browser window will pop up. **Log in to your Google Account** inside it.
    5. The browser will close automatically. Rerun or check status here.
    """)
    
    if st.button("🔄 Retry Authentication Check"):
        st.session_state.auth_ok = None
        st.rerun()
        
    st.markdown("---")
    st.markdown("#### Diagnostics Log:")
    st.code(st.session_state.auth_error, language="text")
    st.stop()

# ----------------- AUTHENTICATED WORKSPACE -----------------

# Initialize Session States
if "selected_sources" not in st.session_state:
    st.session_state.selected_sources = set()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "active_nb_id" not in st.session_state:
    st.session_state.active_nb_id = get_cached_notebook_id()

# Load Notebooks List
async def fetch_notebooks(client):
    return await client.notebooks.list()

try:
    notebooks = run_async(run_client_op(fetch_notebooks))
    st.session_state.notebooks_cache = notebooks
except Exception as e:
    st.error(f"Failed to fetch notebooks: {e}")
    st.stop()

if not notebooks:
    st.title("NotebookLM AI Dashboard")
    st.info("You don't have any notebooks yet. Let's create your first notebook!")
    new_nb_name = st.text_input("Notebook Name", value="Research Notebook")
    if st.button("Create Notebook", use_container_width=True):
        async def create_nb(client):
            return await client.notebooks.create(new_nb_name)
        try:
            with st.spinner("Creating notebook..."):
                nb = run_async(run_client_op(create_nb))
                set_cached_notebook_id(nb.id)
                st.session_state.active_nb_id = nb.id
                st.success(f"Notebook '{nb.title}' created!")
                st.rerun()
        except Exception as e:
            st.error(f"Failed to create notebook: {e}")
    st.stop()

# Sidebar: Notebook Selector
st.sidebar.markdown("# 📓 NotebookLM Studio")
st.sidebar.markdown("---")

notebook_options = {nb.title: nb.id for nb in notebooks}
notebook_titles = list(notebook_options.keys())

# Determine default notebook selection index
default_idx = 0
cached_id = st.session_state.active_nb_id
if cached_id:
    for idx, nb in enumerate(notebooks):
        if nb.id == cached_id:
            default_idx = idx
            break

selected_nb_title = st.sidebar.selectbox(
    "Select Notebook",
    options=notebook_titles,
    index=default_idx
)

active_nb_id = notebook_options[selected_nb_title]

# If active notebook changed, refresh session states
if active_nb_id != st.session_state.active_nb_id:
    st.session_state.active_nb_id = active_nb_id
    set_cached_notebook_id(active_nb_id)
    st.session_state.selected_sources = set()
    st.session_state.chat_history = []
    st.rerun()

# Sidebar: Create New Notebook
with st.sidebar.expander("➕ Create New Notebook", expanded=False):
    create_nb_name = st.text_input("New Notebook Name", placeholder="e.g. Project Phoenix")
    if st.button("Create", key="create_nb_btn", use_container_width=True):
        if create_nb_name.strip():
            async def create_nb(client):
                return await client.notebooks.create(create_nb_name.strip())
            try:
                with st.spinner("Creating..."):
                    nb = run_async(run_client_op(create_nb))
                    set_cached_notebook_id(nb.id)
                    st.session_state.active_nb_id = nb.id
                    st.success(f"Created '{nb.title}'!")
                    st.rerun()
            except Exception as e:
                st.error(e)
        else:
            st.warning("Please provide a name.")

# Fetch active notebook's sources
async def fetch_sources(client):
    return await client.sources.list(active_nb_id)

try:
    sources = run_async(run_client_op(fetch_sources))
    st.session_state.sources_cache = sources
except Exception as e:
    st.sidebar.error(f"Failed to fetch sources: {e}")
    sources = []

# Sidebar: Source selection list
st.sidebar.markdown("### 📄 Selected Sources")

if sources:
    col_all, col_none = st.sidebar.columns(2)
    if col_all.button("Select All", key="sel_all_btn", use_container_width=True):
        st.session_state.selected_sources = {src.id for src in sources}
        st.rerun()
    if col_none.button("Clear Selection", key="clear_sel_btn", use_container_width=True):
        st.session_state.selected_sources = set()
        st.rerun()
        
    for src in sources:
        # Resolve status label and dot color
        # status codes: 1=processing, 2=ready, 3=error, 5=preparing
        if src.status == 2:
            status_text = "🟢"
            status_desc = "Ready"
        elif src.status in (1, 5):
            status_text = "⏳"
            status_desc = "Indexing"
        else:
            status_text = "🔴"
            status_desc = "Error"
            
        label = f"{status_text} {src.title or src.url} ({status_desc})"
        is_checked = src.id in st.session_state.selected_sources
        
        checked = st.sidebar.checkbox(label, value=is_checked, key=f"check_{src.id}")
        if checked:
            st.session_state.selected_sources.add(src.id)
        else:
            st.session_state.selected_sources.discard(src.id)
else:
    st.sidebar.info("No sources ingested yet.")

# Auto-refresh if any source is still indexing
any_indexing = any(src.status in (1, 5) for src in sources)
if any_indexing:
    st.sidebar.info("⏳ Indexing sources... Auto-refreshing in 5s.")
    time.sleep(5)
    st.rerun()

# Sidebar: Ingest New Sources
with st.sidebar.expander("📥 Ingest New Source", expanded=False):
    # Upload File option
    uploaded_file = st.file_uploader("Upload PDF or TXT file", type=["pdf", "txt"])
    if uploaded_file is not None:
        if st.button("Ingest File", use_container_width=True):
            with st.spinner("Uploading file to Google servers..."):
                # Save locally temporarily
                temp_path = os.path.join(config.SOURCES_DIR, uploaded_file.name)
                try:
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    async def upload_file(client):
                        await client.sources.add_file(active_nb_id, temp_path)
                    
                    run_async(run_client_op(upload_file))
                    st.success(f"Successfully uploaded {uploaded_file.name}!")
                    # Add to selected sources automatically
                    # Note: ID won't be known until we fetch lists again, so we'll just refresh
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to upload: {e}")
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except Exception:
                            pass
                            
    st.markdown("---")
    # Ingest URL option
    url_input = st.text_input("Enter URL (Web page or YouTube link)", placeholder="https://...")
    if url_input:
        if st.button("Ingest URL", use_container_width=True):
            with st.spinner("Ingesting URL source..."):
                async def upload_url(client):
                    await client.sources.add_url(active_nb_id, url_input.strip(), wait=True)
                try:
                    run_async(run_client_op(upload_url))
                    st.success("Successfully ingested URL!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to ingest URL: {e}")

# Sidebar: Delete Sources
if sources:
    with st.sidebar.expander("🗑️ Delete Ingested Source", expanded=False):
        delete_options = {src.title or src.url: src.id for src in sources}
        source_to_delete = st.selectbox("Select source to delete", options=list(delete_options.keys()))
        if st.button("Confirm Delete", key="delete_source_btn", use_container_width=True):
            source_id = delete_options[source_to_delete]
            with st.spinner("Deleting source..."):
                async def delete_source(client):
                    await client.sources.delete(active_nb_id, source_id)
                try:
                    run_async(run_client_op(delete_source))
                    st.success("Successfully deleted source!")
                    st.session_state.selected_sources.discard(source_id)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to delete source: {e}")

# ----------------- MAIN VIEW PANELS -----------------

tab_chat, tab_studio, tab_status = st.tabs(["💬 Chat Interface", "🎙️ Studio & Reports", "🛠️ Diagnostics"])

# Build ID to title maps
source_id_to_title = {src.id: (src.title or src.url) for src in sources}

# ----------------- TAB 1: CHAT INTERFACE -----------------
with tab_chat:
    st.subheader(f"Chatting with: {selected_nb_title}")
    
    # Selected sources status bar
    selected_count = len(st.session_state.selected_sources)
    if selected_count == 0:
        st.info("🔍 Querying **All Ingested Sources** (No checkboxes selected).")
        filter_ids = None
    else:
        st.success(f"🔍 Querying **{selected_count} / {len(sources)} selected source(s)**.")
        filter_ids = list(st.session_state.selected_sources)
        
    # Render chat messages from history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # Display references if they exist
            if msg.get("references"):
                with st.expander("📚 Citations & Sources Used", expanded=False):
                    for ref in msg["references"]:
                        src_title = source_id_to_title.get(ref["source_id"], "Unknown Source")
                        st.markdown(f"**[{ref['citation_number']}] {src_title}**")
                        st.info(f"\"{ref['cited_text']}\"")

    # Chat Input
    if prompt := st.chat_input("Ask a question about your sources..."):
        # Render and append user prompt
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        
        # Execute query
        with st.chat_message("assistant"):
            with st.spinner("Consulting sources..."):
                async def ask_chat(client):
                    return await client.chat.ask(
                        active_nb_id,
                        prompt,
                        source_ids=filter_ids
                    )
                
                try:
                    res = run_async(run_client_op(ask_chat))
                    answer = res.answer if hasattr(res, 'answer') else str(res)
                    st.markdown(answer)
                    
                    references = []
                    if hasattr(res, 'references') and res.references:
                        for r in res.references:
                            references.append({
                                "source_id": r.source_id,
                                "citation_number": r.citation_number,
                                "cited_text": r.cited_text
                            })
                            
                        with st.expander("📚 Citations & Sources Used", expanded=False):
                            for ref in references:
                                src_title = source_id_to_title.get(ref["source_id"], "Unknown Source")
                                st.markdown(f"**[{ref['citation_number']}] {src_title}**")
                                st.info(f"\"{ref['cited_text']}\"")
                    
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": answer,
                        "references": references
                    })
                except Exception as e:
                    st.error(f"Failed to query notebook: {e}")

# ----------------- TAB 2: STUDIO & REPORTS -----------------
with tab_studio:
    st.subheader("🎙️ NotebookLM Studio")
    
    # Resolve selected sources for studio generations
    selected_count = len(st.session_state.selected_sources)
    if selected_count == 0:
        st.info("🔍 Studio generations will use **All Ingested Sources** (No checkboxes selected).")
        filter_ids = None
    else:
        st.success(f"🔍 Studio generations will use **{selected_count} / {len(sources)} selected source(s)**.")
        filter_ids = list(st.session_state.selected_sources)
        
    st.write("Generate Audio Overview Podcasts, Briefing Papers, and Study Guides using selected notebook sources.")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 🎙️ Audio Overview Podcast")
        st.write("Generate a simulated double-host discussion summarizing your sources.")
        podcast_prompt = st.text_area(
            "Focus Guidelines (Optional)", 
            placeholder="e.g. Focus on techno-economic factors and green hydrogen viability.",
            key="podcast_prompt_txt",
            height=100
        )
        if st.button("Generate Audio Podcast", use_container_width=True):
            st.info("Triggering Podcast generation on Google servers... This usually takes 2-4 minutes. Please wait.")
            with st.spinner("Synthesizing audio overview..."):
                async def gen_audio_op(client):
                    instructions = podcast_prompt.strip() if podcast_prompt.strip() else None
                    status = await client.artifacts.generate_audio(
                        active_nb_id, 
                        source_ids=filter_ids, 
                        instructions=instructions
                    )
                    # Poll for completion directly inside the SDK
                    await client.artifacts.wait_for_completion(active_nb_id, status.task_id, timeout=1200.0)
                    output_file = os.path.join(config.LOGS_DIR, "podcast.mp3")
                    await client.artifacts.download_audio(active_nb_id, output_file)
                    return output_file
                
                try:
                    out_file = run_async(run_client_op(gen_audio_op))
                    st.success("Podcast generated and downloaded successfully!")
                    st.audio(out_file)
                    with open(out_file, "rb") as f:
                        st.download_button(
                            label="Download MP3 File",
                            data=f.read(),
                            file_name=f"podcast_{active_nb_id}.mp3",
                            mime="audio/mp3",
                            use_container_width=True
                        )
                except Exception as e:
                    st.error(f"Failed to generate: {e}")

    with col2:
        st.markdown("### 📄 Briefing Paper / Report")
        st.write("Generate a comprehensive briefing document summarizing the insights.")
        report_prompt = st.text_area(
            "Formatting Guidelines (Optional)",
            placeholder="e.g. Summarize key formulas and production costs.",
            key="report_prompt_txt",
            height=100
        )
        if st.button("Generate Briefing Paper", use_container_width=True):
            with st.spinner("Generating briefing paper..."):
                async def gen_report_op(client):
                    custom_prompt = report_prompt.strip() if report_prompt.strip() else None
                    status = await client.artifacts.generate_report(
                        active_nb_id, 
                        source_ids=filter_ids, 
                        custom_prompt=custom_prompt
                    )
                    await client.artifacts.wait_for_completion(active_nb_id, status.task_id, timeout=1200.0)
                    output_file = os.path.join(config.LOGS_DIR, "paper.md")
                    await client.artifacts.download_report(active_nb_id, output_file)
                    return output_file
                    
                try:
                    out_file = run_async(run_client_op(gen_report_op))
                    st.success("Report generated and downloaded successfully!")
                    with open(out_file, "r", encoding="utf-8") as f:
                        report_content = f.read()
                    st.markdown("---")
                    st.markdown(report_content)
                    st.download_button(
                        label="Download Markdown Report",
                        data=report_content,
                        file_name=f"briefing_paper_{active_nb_id}.md",
                        mime="text/markdown",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Failed to generate report: {e}")

    with col3:
        st.markdown("### 📚 Study Guide")
        st.write("Create a study guide complete with key terms, essay questions, and quiz materials.")
        st.write("") # Spacer
        if st.button("Generate Study Guide", use_container_width=True):
            with st.spinner("Generating study guide..."):
                async def gen_guide_op(client):
                    status = await client.artifacts.generate_study_guide(
                        active_nb_id, 
                        source_ids=filter_ids
                    )
                    await client.artifacts.wait_for_completion(active_nb_id, status.task_id, timeout=1200.0)
                    output_file = os.path.join(config.LOGS_DIR, "study_guide.md")
                    await client.artifacts.download_report(active_nb_id, output_file)
                    return output_file
                    
                try:
                    out_file = run_async(run_client_op(gen_guide_op))
                    st.success("Study guide generated and downloaded successfully!")
                    with open(out_file, "r", encoding="utf-8") as f:
                        guide_content = f.read()
                    st.markdown("---")
                    st.markdown(guide_content)
                    st.download_button(
                        label="Download Markdown Study Guide",
                        data=guide_content,
                        file_name=f"study_guide_{active_nb_id}.md",
                        mime="text/markdown",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Failed to generate study guide: {e}")

# ----------------- TAB 3: DIAGNOSTICS & SYSTEM STATUS -----------------
with tab_status:
    st.subheader("🛠️ NotebookLM System Diagnostics")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🔑 Authentication Status")
        st.success("Authentication cookies loaded successfully!")
        
        # Display storage state details
        profile_path = os.path.expanduser("~/.notebooklm/profiles/default/storage_state.json")
        if os.path.exists(profile_path):
            st.info(f"Session cookies located at: `{profile_path}`")
            # Show file modification date
            mtime = os.path.getmtime(profile_path)
            mod_time = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            st.write(f"Last modified: `{mod_time}`")
        else:
            st.warning("Session cookies not found in the default profile folder.")
            
    with col2:
        st.markdown("### 📊 System Information")
        st.write(f"**Python Interpreter**: `{sys.executable}`")
        st.write(f"**Workspace Directory**: `{config.WORKSPACE_DIR}`")
        st.write(f"**Logs Directory**: `{config.LOGS_DIR}`")
        
        if st.button("Clear App Chat History", use_container_width=True):
            st.session_state.chat_history = []
            st.success("Chat history cleared!")
            st.rerun()

    st.markdown("---")
    st.markdown("### 🩺 NotebookLM CLI Doctor Diagnosis")
    if st.button("Run CLI Diagnosis Tool", use_container_width=True):
        with st.spinner("Running diagnostic tool..."):
            success, out = run_cli_command(["doctor"])
            if success:
                st.success("Diagnostic check complete!")
                st.code(out, language="text")
            else:
                st.error("Diagnostic check failed!")
                st.code(out, language="text")
