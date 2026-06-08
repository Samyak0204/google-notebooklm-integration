import sys
import os
import subprocess

def main():
    # Print welcome banner
    print("=" * 60)
    print("NotebookLM Streamlit UI Launcher")
    print("=" * 60)

    # Resolve paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ui_script = os.path.join(script_dir, "ui_app.py")

    # Check if ui_app.py exists
    if not os.path.exists(ui_script):
        # We will create it shortly, but print a warning just in case
        pass

    # Check streamlit installation
    try:
        import streamlit
        print("Streamlit dependency found.")
    except ImportError:
        print("Streamlit not found. Installing now...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "streamlit"], check=True)
            print("Successfully installed streamlit.")
        except Exception as e:
            print(f"Error: Failed to install streamlit: {e}")
            sys.exit(1)

    # Run Streamlit
    print("Launching Streamlit Server...")
    print("Please wait, it will automatically open the browser once started.")
    print("-" * 60)
    
    cmd = [sys.executable, "-m", "streamlit", "run", ui_script]
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nLauncher stopped by user.")
    except Exception as e:
        print(f"Error running streamlit: {e}")

if __name__ == "__main__":
    main()
