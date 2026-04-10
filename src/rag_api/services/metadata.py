"""Metadata module for Document Gap Analysis pipeline."""
import json
from pathlib import Path
from src.config import settings

_ROOT = Path(__file__).resolve().parents[3]

META_FILE = _ROOT / settings.metadata_file
UPLOADS_DIR = _ROOT / settings.upload_dir

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

def load_meta() -> dict:
    if META_FILE.exists():
        return json.loads(META_FILE.read_text())
    return {"files": {}}

def save_meta(meta: dict) -> None:
    META_FILE.parent.mkdir(parents=True, exist_ok=True)
    META_FILE.write_text(json.dumps(meta, indent=2))
