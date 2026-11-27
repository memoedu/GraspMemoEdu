"""Loopback FastAPI adapter for offline Japanese reading."""

from contextlib import closing
import json
from pathlib import Path
import sqlite3

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from graspmemoedu.service import DomainError
from graspmemoedu.topic_structure import point_introductions

from .analysis import MAX_TEXT_LENGTH, POLITE_POINT_ID, POLITE_TOPIC_ID, analyze_reading


class ReadingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)


def _read_lesson_status(topic_file, progress_db):
    try:
        topic = json.loads(topic_file.read_text(encoding="utf-8"))
        if topic.get("id") != POLITE_TOPIC_ID:
            raise ValueError("Unexpected Japanese lesson ID")
        introduction = point_introductions(topic)[POLITE_POINT_ID]
        db_uri = progress_db.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(db_uri, uri=True)) as con:
            if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='topics'").fetchone() is None:
                return False
            row = con.execute(
                "SELECT body FROM topics WHERE learner=? AND topic=? AND version=?",
                ("local", POLITE_TOPIC_ID, topic["version"]),
            ).fetchone()
        if row is None:
            return False
        read = json.loads(row[0]).get("read_introductions")
        return isinstance(read, list) and introduction in read
    except (AttributeError, KeyError, OSError, TypeError, ValueError, sqlite3.Error) as exc:
        raise DomainError("lesson_status_unavailable", "无法读取本机丁寧語课程或进度，请检查启动时指定的文件。", 503) from exc


def create_app(*, topic_file=None, progress_db=None, lesson_port=18782):
    if (topic_file is None) != (progress_db is None):
        raise ValueError("The local topic and progress files must be supplied together")
    lesson_url = None
    if topic_file is not None:
        lesson_url = f"http://127.0.0.1:{int(lesson_port)}/#/topic/{POLITE_TOPIC_ID}"

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.exception_handler(DomainError)
    async def domain_error(_request: Request, exc: DomainError):
        return JSONResponse(status_code=exc.status_code, content={"detail": {"code": exc.code, "message": exc.message}})

    @app.post("/api/reading/analyze")
    def analyze(payload: ReadingPayload):
        ready = _read_lesson_status(topic_file, progress_db) if lesson_url else False
        return {"segments": analyze_reading(payload.text, grammar_ready=ready),
                "lesson_url": lesson_url, "grammar_ready": ready}

    app.mount("/", StaticFiles(directory=Path(__file__).with_name("web"), html=True), name="reader")
    return app
