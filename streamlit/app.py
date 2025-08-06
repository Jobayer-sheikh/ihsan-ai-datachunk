# app.py

import streamlit as st
import json
from pathlib import Path

# Import the dedicated PDF viewer component
from streamlit_pdf_viewer import pdf_viewer

# --- 1. Configuration and Data Loading ---

st.set_page_config(layout="wide", page_title="Book Navigator")

DATA_DIR = Path("data")
BOOKS = {
    "Book 1": {
        "pdf_path": DATA_DIR / "book.pdf",
        "json_path": DATA_DIR / "book_structured_pydantic.json"
    },
    "Book 2": {
        "pdf_path": DATA_DIR / "book1.pdf",
        "json_path": DATA_DIR / "book1_structured_pydantic.json"
    }
}

@st.cache_data
def load_book_structure(json_path: Path) -> dict | None:
    """Loads the structured JSON file for a selected book."""
    if not json_path.exists():
        st.error(f"Error: JSON file not found at {json_path}")
        return None
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Failed to load or parse JSON file: {e}")
        return None

# --- NEW: Updated PDF function to use `pages_to_render` ---
def show_pdf_with_component(pdf_path: Path, pages: list[int]):
    """
    Displays a specific range of pages from a PDF using the streamlit_pdf_viewer component.
    """
    if not pdf_path.exists():
        st.error(f"Error: PDF file not found at {pdf_path}")
        return
        
    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        
        pdf_viewer(
            input=pdf_bytes,
            height=1000,
            pages_to_render=pages
        )
    except Exception as e:
        st.error(f"An error occurred while trying to display the PDF: {e}")


# --- 2. State Management and Callbacks ---

# Initialize session state with a list for the page range
if 'pages_to_show' not in st.session_state:
    st.session_state.pages_to_show = [1] 
if 'selected_book' not in st.session_state:
    st.session_state.selected_book = list(BOOKS.keys())[0]
if 'selected_unit' not in st.session_state:
    st.session_state.selected_unit = "Select a Unit..."

def on_book_change():
    """Callback to reset state when the book selection changes."""
    st.session_state.selected_book = st.session_state.book_selector
    st.session_state.selected_unit = "Select a Unit..."
    st.session_state.pages_to_show = [1]

def on_unit_change():
    """Callback to set the page range for the selected unit."""
    selected_unit_title = st.session_state.unit_selector
    st.session_state.selected_unit = selected_unit_title

    if selected_unit_title == "Select a Unit...":
        return
        
    book_data = load_book_structure(BOOKS[st.session_state.selected_book]["json_path"])
    for unit in book_data.get("units", []):
        if unit["title"] == selected_unit_title:
            start_page = unit.get("start_page", 1)
            end_page = unit.get("end_page", start_page)
            st.session_state.pages_to_show = list(range(start_page, end_page + 1))
            break

def on_lesson_change():
    """Callback to set the page range for the selected lesson."""
    selected_lesson_title = st.session_state.lesson_selector
    if selected_lesson_title == "Select a Lesson...":
        return
        
    book_data = load_book_structure(BOOKS[st.session_state.selected_book]["json_path"])
    for unit in book_data.get("units", []):
        for lesson in unit.get("lessons", []):
            if lesson["title"] == selected_lesson_title:
                start_page = lesson.get("start_page", 1)
                end_page = lesson.get("end_page", start_page)
                st.session_state.pages_to_show = list(range(start_page, end_page + 1))
                return

# --- 3. Main App Layout ---

st.title("📖 Interactive Book Navigator")

with st.sidebar:
    st.header("Navigation Controls")
    st.selectbox(
        label="Select a Book",
        options=list(BOOKS.keys()),
        key="book_selector",
        on_change=on_book_change
    )
    
    selected_book_name = st.session_state.selected_book
    book_data = load_book_structure(BOOKS[selected_book_name]["json_path"])

    if book_data:
        unit_titles = ["Select a Unit..."] + [unit["title"] for unit in book_data.get("units", [])]
        st.selectbox(
            label="Select a Unit",
            options=unit_titles,
            key="unit_selector",
            on_change=on_unit_change
        )
        
        lesson_titles = ["Select a Lesson..."]
        if st.session_state.selected_unit != "Select a Unit...":
            for unit in book_data.get("units", []):
                if unit["title"] == st.session_state.selected_unit:
                    lesson_titles.extend([lesson["title"] for lesson in unit.get("lessons", [])])
                    break
        st.selectbox(
            label="Select a Lesson",
            options=lesson_titles,
            key="lesson_selector",
            on_change=on_lesson_change
        )
    
    page_range_str = "All"
    if st.session_state.pages_to_show:
        start = st.session_state.pages_to_show[0]
        end = st.session_state.pages_to_show[-1]
        page_range_str = f"{start} - {end}" if start != end else str(start)

    st.info(f"**Current View**\n\nBook: `{selected_book_name}`\n\nDisplaying Pages: `{page_range_str}`")

# --- 4. PDF Viewer in the Main Area ---

st.subheader(f"Displaying: {selected_book_name}")

show_pdf_with_component(
    pdf_path=BOOKS[selected_book_name]["pdf_path"],
    pages=st.session_state.pages_to_show
)