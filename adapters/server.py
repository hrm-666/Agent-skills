import logging
import os
import importlib.util
import json
import queue
import re
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.agent import Agent
from core.llm import PROVIDERS


class ChatRequest(BaseModel):
    text: str
    image_paths: Optional[List[str]] = []
    file_paths: Optional[List[str]] = []
    provider: str = "active"


class MysqlImportRequest(BaseModel):
    url: str
    timeout: int = 30


app = FastAPI(title="Mini Agent")
_agent: Optional[Agent] = None


@app.get("/")
async def index():
    return RedirectResponse(url="/webui/index.html")


def start_server(agent_instance: Agent, host: str, port: int):
    global _agent
    _agent = agent_instance

    app.mount("/webui", StaticFiles(directory="webui"), name="webui")
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

    import uvicorn

    logging.info("Starting WebUI server at http://%s:%s/webui/index.html", host, port)
    uvicorn.run(app, host=host, port=port)


def _split_uploads(paths: Optional[List[str]]):
    paths = paths or []
    image_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    images = [p for p in paths if Path(p).suffix.lower() in image_exts]
    files = [p for p in paths if p not in images]
    return images, files


def _augment_text(text: str, file_paths: Optional[List[str]]):
    if not file_paths:
        return text
    file_list = "\n".join(f"- {p}" for p in file_paths)
    return (
        f"{text}\n\nUploaded files available for tool/skill processing:\n{file_list}\n"
        "Use the relevant skill and bash command to inspect these files when needed."
    )


def _load_env_file():
    env_path = Path(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _mysql_conn():
    try:
        import pymysql
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="Missing dependency: pymysql. Install requirements.txt first.") from exc

    _load_env_file()
    database = os.getenv("MYSQL_DATABASE", "mini_agent_data")
    if not re.fullmatch(r"[A-Za-z0-9_]+", database):
        raise HTTPException(status_code=500, detail="MYSQL_DATABASE may only contain letters, numbers, and underscores.")
    base_cfg = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "charset": "utf8mb4",
        "autocommit": True,
    }
    try:
        bootstrap = pymysql.connect(**base_cfg)
        try:
            with bootstrap.cursor() as cur:
                cur.execute(f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        finally:
            bootstrap.close()
        return pymysql.connect(**base_cfg, database=database)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MySQL connection failed: {exc}") from exc


def _rows_to_dicts(cursor, rows):
    names = [desc[0] for desc in cursor.description]
    return [dict(zip(names, row)) for row in rows]


def _ensure_mysql_tables(conn):
    script = Path("skills/mysql-api-ingestor/scripts/import_url.py")
    if not script.exists():
        return
    spec = importlib.util.spec_from_file_location("mysql_api_ingestor_import_url", script)
    if not spec or not spec.loader:
        return
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with conn.cursor() as cur:
        module.ensure_tables(cur)


@app.post("/api/chat")
async def chat(request: ChatRequest):
    if not _agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")

    steps = []

    def on_step(step_data):
        steps.append(step_data)

    try:
        uploaded_images, uploaded_files = _split_uploads((request.image_paths or []) + (request.file_paths or []))
        reply = _agent.run(
            user_text=_augment_text(request.text, uploaded_files),
            image_paths=uploaded_images,
            on_step=on_step,
        )
        return {"reply": reply, "steps": steps}
    except Exception as exc:
        logging.exception("Chat error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    if not _agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")

    def events():
        event_queue: queue.Queue = queue.Queue()
        uploaded_images, uploaded_files = _split_uploads((request.image_paths or []) + (request.file_paths or []))

        def push(kind, payload):
            event_queue.put(json.dumps({"type": kind, **payload}, ensure_ascii=False) + "\n")

        def run_agent():
            try:
                reply = _agent.run(
                    user_text=_augment_text(request.text, uploaded_files),
                    image_paths=uploaded_images,
                    on_step=lambda step: push("step", {"step": step}),
                )
                push("final", {"reply": reply})
            except Exception as exc:
                logging.exception("Streaming chat error")
                push("error", {"detail": str(exc)})
            finally:
                event_queue.put(None)

        threading.Thread(target=run_agent, daemon=True).start()
        while True:
            item = event_queue.get()
            if item is None:
                break
            yield item

    return StreamingResponse(events(), media_type="application/x-ndjson")


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)

    suffix = Path(file.filename or "").suffix.lower()
    allowed = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".xlsx", ".xlsm", ".pdf", ".docx", ".txt", ".csv"}
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    file_name = f"{uuid.uuid4().hex}{suffix}"
    file_path = uploads_dir / file_name
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"path": f"/uploads/{file_name}"}


@app.get("/api/providers")
async def get_providers():
    result = []
    for name, cfg in PROVIDERS.items():
        result.append(
            {
                "name": name,
                "supports_vision": cfg["supports_vision"],
                "configured": bool(os.getenv(cfg["env_key"])),
            }
        )
    return result


@app.post("/api/mysql/import-url")
async def mysql_import_url(request: MysqlImportRequest):
    script = Path("skills/mysql-api-ingestor/scripts/import_url.py")
    if not script.exists():
        raise HTTPException(status_code=404, detail="mysql-api-ingestor skill script not found.")
    cmd = [sys.executable, str(script), request.url, "--timeout", str(max(5, min(request.timeout, 120)))]
    completed = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "Import failed."
        raise HTTPException(status_code=500, detail=detail[-1200:])
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"status": "completed", "raw": completed.stdout}


@app.get("/api/mysql/jobs/latest")
async def mysql_latest_job():
    conn = _mysql_conn()
    try:
        _ensure_mysql_tables(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM api_import_jobs ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if not row:
                return {"job": None, "counts": {}}
            job = _rows_to_dicts(cur, [row])[0]
            counts = {}
            for table in ("api_orders", "api_order_addresses", "api_order_line_items", "api_order_attributes"):
                cur.execute(f"SELECT COUNT(*) FROM {table} WHERE job_id=%s", (job["id"],))
                counts[table] = cur.fetchone()[0]
            return {"job": job, "counts": counts}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        conn.close()


@app.get("/api/mysql/preview")
async def mysql_preview(job_id: int, table: str = "api_orders", limit: int = 10):
    allowed = {"api_orders", "api_order_addresses", "api_order_line_items", "api_order_attributes", "api_import_jobs"}
    if table not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported preview table.")
    conn = _mysql_conn()
    try:
        _ensure_mysql_tables(conn)
        with conn.cursor() as cur:
            if table == "api_import_jobs":
                cur.execute("SELECT * FROM api_import_jobs ORDER BY id DESC LIMIT %s", (max(1, min(limit, 50)),))
            else:
                cur.execute(f"SELECT * FROM {table} WHERE job_id=%s ORDER BY id LIMIT %s", (job_id, max(1, min(limit, 50))))
            return {"table": table, "rows": _rows_to_dicts(cur, cur.fetchall())}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        conn.close()
