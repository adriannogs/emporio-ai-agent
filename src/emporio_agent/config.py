from pathlib import Path
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("EMPORIO_DATA_DIR", ROOT / "data"))
DB_PATH = Path(os.getenv("EMPORIO_DB_PATH", ROOT / "data" / "emporio.db"))
POLICY_PATH = DATA_DIR / "politicas.md"
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
