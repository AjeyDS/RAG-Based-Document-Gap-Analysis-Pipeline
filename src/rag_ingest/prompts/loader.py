"""Loader module for Document Gap Analysis pipeline."""
from pathlib import Path

def load_prompt(prompt_name: str) -> str:
    path = Path(__file__).parent / prompt_name
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file not found at {path}")
    
    content = path.read_text(encoding="utf-8")
    
    # If the file contains Python variable assignments (like GAP_ANALYSIS_PROMPT = """), strip them
    # so the raw string is cleanly given to the LLM. Wait, if we just strip the first occurrence:
    if '"""' in content:
        parts = content.split('"""')
        if len(parts) >= 3:
            content = parts[-2]
    return content.strip()
