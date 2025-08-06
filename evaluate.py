# evaluate_llm.py

import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

# --- 1. Setup the Evaluator Agent ---
load_dotenv()

# We use a powerful model for the nuanced task of semantic comparison.
evaluator_llm = ChatOpenAI(model="gpt-4o", temperature=0)

# Define the structured output we want from the LLM using Pydantic.
# This makes parsing the LLM's response extremely reliable.
class TitleMatch(BaseModel):
    is_match: bool = Field(description="Boolean indicating if a semantic match was found.")
    best_match: str | None = Field(description="The best matching title from the candidate list, or null if no match.")
    confidence: float = Field(description="A confidence score from 0.0 (no match) to 1.0 (perfect match).")
    reasoning: str = Field(description="A brief explanation for the decision.")

# Create the chain with structured output.
structured_llm = evaluator_llm.with_structured_output(TitleMatch)

MATCHER_PROMPT_TEMPLATE = """
You are a meticulous comparison agent specializing in Arabic academic titles. Your task is to determine if a given `ground_truth_title` has a semantic equivalent in a list of `candidate_titles`.

- A semantic match is one where the titles refer to the same chapter or lesson, even if there are minor wording differences, punctuation changes, or variations in diacritics (e.g., 'الـمُنـكـر' vs. 'المنكر').
- If a clear match exists, set `is_match` to true, provide the `best_match` from the candidate list, and set confidence to 0.9 or higher.
- If there is no plausible match, set `is_match` to false and confidence to 0.1 or lower.

Ground Truth Title:
`{ground_truth_title}`

Candidate Titles from Agent:
{candidate_titles}
"""
matcher_prompt = ChatPromptTemplate.from_template(MATCHER_PROMPT_TEMPLATE)
matcher_chain = matcher_prompt | structured_llm

# --- 2. Helper and Core Evaluation Functions ---

def load_json_file(file_path: Path) -> list | None:
    # ... (This function is the same as the previous script) ...
    if not file_path.exists():
        print(f"❌ Error: File not found at '{file_path}'")
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else None
    except Exception as e:
        print(f"❌ Error loading {file_path}: {e}")
        return None

def find_best_semantic_match(gt_title: str, agent_titles: list[str]) -> TitleMatch:
    """Uses the LLM to find the best semantic match for a title."""
    try:
        response = matcher_chain.invoke({
            "ground_truth_title": gt_title,
            "candidate_titles": "\n".join(f"- {t}" for t in agent_titles)
        })
        return response
    except Exception as e:
        print(f"  -- LLM evaluation call failed for title '{gt_title}': {e}")
        return TitleMatch(is_match=False, best_match=None, confidence=0.0, reasoning="API call failed.")

def evaluate_with_llm(ground_truth_units: list, agent_units: list):
    """Performs a semantic evaluation of the agent's map against the ground truth."""
    stats = {
        "gt_units_count": len(ground_truth_units),
        "agent_units_count": len(agent_units),
        "matched_units_count": 0,
        "gt_lessons_count": sum(len(u.get("lessons", [])) for u in ground_truth_units),
        "matched_lessons_count": 0,
        "page_errors": 0, "total_page_comparisons": 0,
        "errors": []
    }

    # Create a list of available agent unit titles to match against.
    # We will remove titles as they are matched to prevent one agent unit matching multiple GT units.
    available_agent_units = {u.get("unit_title", ""): u for u in agent_units}

    print("\n--- Evaluating Units ---")
    for gt_unit in ground_truth_units:
        gt_title = gt_unit.get("unit_title", "")
        print(f"Checking GT Unit: '{gt_title}'...")

        # Use the LLM to find the best match from the available agent titles
        match_result = find_best_semantic_match(gt_title, list(available_agent_units.keys()))

        if not match_result.is_match or match_result.confidence < 0.8:
            stats["errors"].append(f"MISSING UNIT (Semantic): Could not find a confident match for GT Unit '{gt_title}'. Reason: {match_result.reasoning}")
            continue
        
        agent_unit_title = match_result.best_match
        agent_unit = available_agent_units.pop(agent_unit_title) # Find and remove the matched unit
        stats["matched_units_count"] += 1
        print(f"  ✅ Matched with Agent Unit: '{agent_unit_title}' (Confidence: {match_result.confidence:.2f})")

        # Now that we have a semantic match, compare page numbers
        # ... (page comparison logic is the same) ...
        stats["total_page_comparisons"] += 2
        if gt_unit.get("unit_start_page") != agent_unit.get("unit_start_page"):
            stats["page_errors"] += 1
            stats["errors"].append(f"PAGE MISMATCH (Unit Start): '{gt_title}' | GT: {gt_unit.get('unit_start_page')}, Agent: {agent_unit.get('unit_start_page')}")
        if gt_unit.get("unit_end_page") != agent_unit.get("unit_end_page"):
            stats["page_errors"] += 1
            stats["errors"].append(f"PAGE MISMATCH (Unit End): '{gt_title}' | GT: {gt_unit.get('unit_end_page')}, Agent: {agent_unit.get('unit_end_page')}")

        # Evaluate lessons within the matched unit
        available_agent_lessons = {l.get("lesson_title", ""): l for l in agent_unit.get("lessons", [])}
        for gt_lesson in gt_unit.get("lessons", []):
            gt_lesson_title = gt_lesson.get("lesson_title", "")
            
            lesson_match_result = find_best_semantic_match(gt_lesson_title, list(available_agent_lessons.keys()))

            if not lesson_match_result.is_match or lesson_match_result.confidence < 0.8:
                stats["errors"].append(f"MISSING LESSON in Unit '{gt_title}': No match for '{gt_lesson_title}'. Reason: {lesson_match_result.reasoning}")
                continue

            agent_lesson_title = lesson_match_result.best_match
            agent_lesson = available_agent_lessons.pop(agent_lesson_title)
            stats["matched_lessons_count"] += 1

            # Compare lesson page numbers
            stats["total_page_comparisons"] += 2
            if gt_lesson.get("lesson_start_page") != agent_lesson.get("lesson_start_page"):
                stats["page_errors"] += 1
                stats["errors"].append(f"PAGE MISMATCH (Lesson Start): '{gt_lesson_title}' | GT: {gt_lesson.get('lesson_start_page')}, Agent: {agent_lesson.get('lesson_start_page')}")
            if gt_lesson.get("lesson_end_page") != agent_lesson.get("lesson_end_page"):
                stats["page_errors"] += 1
                stats["errors"].append(f"PAGE MISMATCH (Lesson End): '{gt_lesson_title}' | GT: {gt_lesson.get('lesson_end_page')}, Agent: {agent_lesson.get('lesson_end_page')}")

    # Any remaining units in our available map are extras
    for extra_title in available_agent_units:
        stats["errors"].append(f"EXTRA UNIT: Unit '{extra_title}' was found by the agent but has no match in the ground truth.")

    # Calculate final stats and print report
    print_report(stats)

def print_report(stats: dict):
    # ... (This function is the same as the previous script, you can copy it here) ...
    # It will now reflect the results of the semantic matching.
    print("\n--- LLM-Powered AGENT MAP EVALUATION REPORT ---")
    gt_u, agent_u, matched_u = stats["gt_units_count"], stats["agent_units_count"], stats["matched_units_count"]
    recall_u = (matched_u / gt_u * 100) if gt_u > 0 else 0
    precision_u = (matched_u / agent_u * 100) if agent_u > 0 else 0
    print("\n[Unit Level Performance (Semantic)]")
    print(f"  - Ground Truth Units: {gt_u}")
    print(f"  - Agent Found Units:  {agent_u}")
    print(f"  - Recall (semantically matched): {recall_u:.2f}% ({matched_u}/{gt_u})")
    print(f"  - Precision (no extra units):    {precision_u:.2f}% ({matched_u}/{agent_u})")
    
    gt_l, matched_l = stats["gt_lessons_count"], stats["matched_lessons_count"]
    agent_l = stats.get("agent_lessons_count", 0) # Use total count
    recall_l = (matched_l / gt_l * 100) if gt_l > 0 else 0
    precision_l = (matched_l / agent_l * 100) if agent_l > 0 else 0
    print("\n[Lesson Level Performance (Semantic)]")
    print(f"  - Ground Truth Lessons: {gt_l}")
    print(f"  - Agent Found Lessons:  {agent_l}")
    print(f"  - Recall (semantically matched): {recall_l:.2f}% ({matched_l}/{gt_l})")
    print(f"  - Precision (no extra lessons):  {precision_l:.2f}% ({matched_l}/{agent_l})")

    total_pages, page_errors = stats["total_page_comparisons"], stats["page_errors"]
    page_accuracy = ((total_pages - page_errors) / total_pages * 100) if total_pages > 0 else 0
    print("\n[Overall Page Number Accuracy]")
    print(f"  - Correct Page Numbers: {total_pages - page_errors} / {total_pages}")
    print(f"  - Accuracy:             {page_accuracy:.2f}%")

    if stats["errors"]:
        print("\n[Detailed Discrepancies]")
        for error in stats["errors"]:
            print(f"  - {error}")
    else:
        print("\n✅ No structural or page number errors found!")
    print("\n--- END OF REPORT ---")

def main():
    parser = argparse.ArgumentParser(description="Evaluate an agent's structural map JSON against a ground truth file using an LLM for semantic title matching.")
    parser.add_argument("ground_truth_path", type=Path, help="Path to the ground truth JSON file.")
    parser.add_argument("agent_map_path", type=Path, help="Path to the agent's generated map JSON file.")
    args = parser.parse_args()

    gt_data = load_json_file(args.ground_truth_path)
    agent_data = load_json_file(args.agent_map_path)

    if not gt_data or not agent_data:
        print("\nEvaluation cannot proceed due to file loading errors.")
        return

    evaluate_with_llm(gt_data, agent_data)

if __name__ == "__main__":
    main()