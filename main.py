import json
import fitz  
from pathlib import Path
from agents import generate_structure_map_from_pdf

# --- Configuration ---
INPUT_DIR = Path("input")
OUTPUT_DIR = Path("output")
PDF_FILENAME = "11- كتاب الدلائل والشمائل النبوية (1).pdf"
AGENT_MAP_FILENAME = "agent_map_pydantic.json"
FINAL_JSON_FILENAME = "book1_structured_pydantic.json"

# --- Helper Function for Text Extraction ---
def extract_text_from_pages(pdf_doc, start_page: int, end_page: int) -> str:
    """Extracts text from a specified 1-based page range."""
    text = ""
    start_idx, end_idx = start_page - 1, end_page - 1
    start_idx = max(0, start_idx)
    end_idx = min(len(pdf_doc) - 1, end_idx)
    for i in range(start_idx, end_idx + 1):
        page = pdf_doc.load_page(i)
        text += page.get_text("text") + "\n\n"
    return text.strip()

def main():
    print(f"Starting the Pydantic-based PDF processing pipeline for: '{PDF_FILENAME}'")
    OUTPUT_DIR.mkdir(exist_ok=True)
    pdf_path = INPUT_DIR / PDF_FILENAME
    agent_map_path = OUTPUT_DIR / AGENT_MAP_FILENAME
    final_json_path = OUTPUT_DIR / FINAL_JSON_FILENAME

    if not pdf_path.exists():
        print(f"❌ Error: Input PDF file not found at '{pdf_path}'")
        return

    # --- Phase 1: Generate the Structure Map Directly from the PDF ---
    structure_map = generate_structure_map_from_pdf(pdf_path)
    if not structure_map:
        print("Halting process due to failure in generating the structure map.")
        return

    with open(agent_map_path, 'w', encoding='utf-8') as f:
        json.dump(structure_map, f, ensure_ascii=False, indent=2)
    print(f"✅ Agent's validated structural map saved to: '{agent_map_path}'")
    
    # --- Phase 2: Programmatic Assembly using the Map and PDF ---
    print("\n--> Starting programmatic content extraction and assembly...")
    pdf_doc = fitz.open(pdf_path)
    final_json = {"units": []}

    if structure_map and structure_map[0].get("unit_start_page", 1) > 1:
        first_unit_start_page = structure_map[0]["unit_start_page"]
        intro_content = extract_text_from_pages(pdf_doc, 1, first_unit_start_page - 1)
        intro_unit = {
            "title": "المقدمة", "start_page": 1, "end_page": first_unit_start_page - 1,
            "lessons": [], "parts": [{"title": "Introduction Content", "content": intro_content}]
        }
        final_json["units"].append(intro_unit)
        print("✅ Programmatically extracted introduction.")

    for unit_data in structure_map:
        unit_obj = {
            "title": unit_data.get("unit_title"), "start_page": unit_data.get("unit_start_page"),
            "end_page": unit_data.get("unit_end_page"), "lessons": [], "parts": []
        }
        last_processed_page = unit_obj["start_page"] - 1
        for lesson_data in unit_data.get("lessons", []):
            lesson_start = lesson_data.get("lesson_start_page")
            lesson_end = lesson_data.get("lesson_end_page")
            if lesson_start > last_processed_page + 1:
                part_content = extract_text_from_pages(pdf_doc, last_processed_page + 1, lesson_start - 1)
                unit_obj["parts"].append({"title": f"Unit Content (Pages {last_processed_page + 1}-{lesson_start - 1})", "content": part_content})
            lesson_content = extract_text_from_pages(pdf_doc, lesson_start, lesson_end)
            lesson_obj = {
                "title": lesson_data.get("lesson_title"), "start_page": lesson_start,
                "end_page": lesson_end, "content": lesson_content
            }
            unit_obj["lessons"].append(lesson_obj)
            last_processed_page = lesson_end
        if unit_obj["end_page"] > last_processed_page:
            part_content = extract_text_from_pages(pdf_doc, last_processed_page + 1, unit_obj["end_page"])
            unit_obj["parts"].append({"title": f"Unit Conclusion (Pages {last_processed_page + 1}-{unit_obj['end_page']})", "content": part_content})
        final_json["units"].append(unit_obj)
        print(f"✅ Processed Unit: {unit_obj['title']}")

    if structure_map:
        last_mapped_page = structure_map[-1].get("unit_end_page")
        total_pages = len(pdf_doc)
        if last_mapped_page and total_pages > last_mapped_page:
            start_page_after = last_mapped_page + 1
            afterword_content = extract_text_from_pages(pdf_doc, start_page_after, total_pages)
            afterword_unit = {
                "title": "ملحق / خاتمة", "start_page": start_page_after, "end_page": total_pages,
                "lessons": [], "parts": [{"title": "Afterword Content", "content": afterword_content}]
            }
            final_json["units"].append(afterword_unit)
            print("✅ Programmatically extracted afterword/appendix.")
    
    pdf_doc.close()

    with open(final_json_path, 'w', encoding='utf-8') as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)

    print(f"\n✅✅✅ Pipeline complete! Final structured JSON is available at: '{final_json_path}'")


if __name__ == '__main__':
    main()