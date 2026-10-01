"""Root entry point for Streamlit application.

Ensures the repository root is always on sys.path.
"""

import sys
from pathlib import Path

# Add project root directory to sys.path
file_path = Path(__file__).resolve()
# If inside app/ directory, parent is 'app' and root is parent.parent
if file_path.parent.name == "app":
    repo_root = str(file_path.parent.parent)
elif file_path.parent.name == "streamlit":
    repo_root = str(file_path.parent.parent.parent)
else:
    repo_root = str(file_path.parent)

if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

# Import and run main application
from app.streamlit.app import main

if __name__ == "__main__":
    main()

