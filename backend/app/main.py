from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

app = FastAPI(title=settings.PROJECT_NAME)


@app.get("/")
def root():
    return {"message": f"{settings.PROJECT_NAME} API activa"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"database": "conectada correctamente"}