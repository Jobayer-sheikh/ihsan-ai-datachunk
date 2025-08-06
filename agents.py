import os
import base64
from dotenv import load_dotenv
from typing import List
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI, HarmCategory, HarmBlockThreshold
from langchain_core.messages import HumanMessage

# --- 1. Define the Pydantic Schema ---

class Lesson(BaseModel):
    """Represents a single lesson within a unit of the book."""
    lesson_title: str = Field(description="The clean, full title of the lesson (e.g., 'الدرس الأول: التعريف بعلم مصطلح الحديث').")
    lesson_start_page: int = Field(description="The physical page number (from the PDF viewer, starting at 1) where the lesson begins.")
    lesson_end_page: int = Field(description="The physical page number where the lesson ends.")

class Unit(BaseModel):
    """Represents a single major unit ('الوحدة') of the book."""
    unit_title: str = Field(description="The clean, full title of the unit (e.g., 'الوحدة الأولى: مدخل إلى مصطلح الحديث').")
    unit_start_page: int = Field(description="The physical page number where the unit begins.")
    unit_end_page: int = Field(description="The physical page number where the unit ends.")
    lessons: List[Lesson] = Field(description="A list of all lessons contained within this unit.")

class BookStructure(BaseModel):
    """The complete structural map of the book, consisting of a list of units."""
    units: List[Unit] = Field(description="The list of all units found in the book's main body.")


# --- 2. Setup the LLM and Bind it to the Pydantic Schema ---
load_dotenv()

safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro",
    temperature=0,
    safety_settings=safety_settings
)

structured_llm = llm.with_structured_output(BookStructure)

MAPPER_PROMPT = """
You are a highly accurate document analysis agent specializing in academic books. Your task is to analyze the provided PDF file and create a complete structural map based on its layout and table of contents.

**CRITICAL INSTRUCTION FOR PAGE NUMBER ACCURACY:**
Page numbers in your response MUST be integers corresponding to the **physical page count of the PDF document** (e.g., the number shown in a PDF viewer, starting from page 1). Do NOT use the numbers printed on the pages themselves. This is the most important rule.

**Other Rules:**
- Your output must conform to the requested JSON schema.
- Do not include the introductory pages ('المقدمة') in your map; only map content starting from the first main unit, 'الوحدة األولى'.
- Be meticulous. The accuracy of the physical page numbers is critical for the success of the entire process.
"""

def generate_structure_map_from_pdf(pdf_path: str) -> list[dict] | None:
    """
    Uses the Gemini 1.5 Mapper Agent with Pydantic to generate a validated structural map directly from a PDF file.
    """
    print("-> Running Mapper Agent (PDF Input, Pydantic Output) to generate structure map...")
    
    try:
        with open(pdf_path, "rb") as pdf_file:
            encoded_pdf = base64.b64encode(pdf_file.read()).decode('utf-8')

        message = HumanMessage(
            content=[
                {"type": "text", "text": MAPPER_PROMPT},
                {
                    "type": "file",
                    "source_type": "base64",
                    "mime_type": "application/pdf",
                    "data": encoded_pdf,
                }
            ]
        )

        response_pydantic = structured_llm.invoke([message])
        
        structure_map = response_pydantic.dict()
        
        units_list = structure_map.get("units", [])
        
        print(f"✅ Mapper Agent successfully created a validated map with {len(units_list)} units.")
        return units_list

    except FileNotFoundError:
        print(f"❌ Error: PDF file not found at path: {pdf_path}")
        return None
    except Exception as e:
        print(f"❌ An unexpected error occurred during the Mapper Agent call: {e}")
        return None