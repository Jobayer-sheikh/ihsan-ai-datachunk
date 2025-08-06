# parser.py

import json
from markdown_it import MarkdownIt

def parse_golden_markdown_to_json(golden_md_text: str) -> dict:
    """
    Parses a golden-standard markdown string into a structured JSON dictionary.
    """
    md = MarkdownIt()
    tokens = md.parse(golden_md_text)

    # State machine variables to build the nested structure
    result_json = {"units": []}
    current_unit = None
    current_lesson = None
    current_part = None

    # This helper function saves the completed objects to the structure
    def save_state():
        nonlocal current_unit, current_lesson, current_part
        if current_part and current_lesson:
            current_lesson["parts"].append(current_part)
        if current_lesson and current_unit:
            current_unit["lessons"].append(current_lesson)
        if current_unit and current_unit not in result_json["units"]:
             # This check prevents re-adding if a unit has no lessons
            result_json["units"].append(current_unit)

    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token.type == 'heading_open':
            # Get the heading text from the next token
            heading_text = tokens[i+1].content.strip()

            if token.tag == 'h1': # New Unit
                save_state() # Save the previous unit/lesson/part
                current_unit = {"title": heading_text, "lessons": [], "parts": []}
                current_lesson = None
                current_part = None

            elif token.tag == 'h2': # New Lesson
                if current_part: # Save the previous part
                    current_lesson["parts"].append(current_part)
                current_lesson = {"title": heading_text, "parts": []}
                current_part = None

            elif token.tag == 'h3': # New Part
                if current_part: # Save the previous part
                    # Decide where to save: lesson parts or unit parts
                    if current_lesson:
                        current_lesson["parts"].append(current_part)
                    elif current_unit:
                        current_unit["parts"].append(current_part)
                current_part = {"title": heading_text, "content": ""}
            
            i += 2  # Skip the inline content and heading_close tokens
            continue

        # Reconstruct content for the current part
        # This part could be enhanced to better reconstruct complex markdown like tables
        if current_part and token.content:
            content_to_add = token.content
            if token.markup:
                content_to_add = f"{token.markup} {content_to_add}"
            current_part["content"] += content_to_add + "\n"

        i += 1
    
    # After the loop, save the very last objects that are still in memory
    save_state()

    return result_json