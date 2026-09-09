import sys
from pathlib import Path

# ให้ import แพ็กเกจ app/ ได้บน Vercel
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Vercel ต้องการตัวแปร top-level ชื่อ app / application / handler
from app.main import app

# เผื่อ runtime บางเวอร์ชันเช็คชื่อ application
application = app
