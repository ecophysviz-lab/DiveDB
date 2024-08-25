import streamlit as st
from pathlib import Path

# Set the page config for the main app
st.set_page_config(page_title="Pyologger", layout="wide")

# Add a title and instructions
st.title("Pyologger Interactive Application")
st.write("Use the sidebar to navigate through different pages of the application.")

# Dynamically load pages
pages_dir = Path(__file__).parent / "pages"
for page in sorted(pages_dir.glob("*.py")):
    with page.open("r") as f:
        code = compile(f.read(), page.name, 'exec')
        exec(code)
