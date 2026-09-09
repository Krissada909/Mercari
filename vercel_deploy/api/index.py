import sys
from pathlib import Path

# ให้ Vercel หาแพ็กเกจ app/ ได้แน่นอน
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402
