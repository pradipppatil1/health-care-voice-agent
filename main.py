import os
import uvicorn
from dotenv import load_dotenv

from app.server import app

def main():
    from pathlib import Path
    _PROJECT_ROOT = Path(__file__).parent
    load_dotenv(_PROJECT_ROOT / ".env", override=True)

    port = int(os.getenv("PORT", 8000))
    print(f"Starting Voice Agent Backend on port {port}...")
    uvicorn.run("app.server:app", host="0.0.0.0", port=port, reload=True)

if __name__ == "__main__":
    main()
