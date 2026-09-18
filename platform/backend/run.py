"""Dev server entry."""
import uvicorn
from app.config import BACKEND_PORT

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=BACKEND_PORT, reload=False)