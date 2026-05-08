"""WebUI 服务端适配层。"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator


FILENAME_SAFE_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
ALLOWED_PROVIDERS = {"kimi", "qwen", "deepseek"}


class AgentLike(Protocol):
    """服务层依赖的最小 Agent 接口。"""

    def run(
        self,
        user_text: str,
        image_paths: list[str] | None = None,
        on_step: Callable[[dict[str, Any]], None] | None = None,
    ) -> str: ...


class RuntimeLike(Protocol):
    """服务层依赖的最小运行时接口。"""

    agent: AgentLike


class ChatRequest(BaseModel):
    """`POST /api/chat` 的请求体。"""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1)
    image_paths: list[str] = Field(default_factory=list)
    provider: str | None = None

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """拒绝空白文本。"""
        normalized = value.strip()
        if not normalized:
            raise ValueError("text 不能为空")
        return normalized

    @field_validator("image_paths")
    @classmethod
    def validate_image_paths(cls, value: list[str]) -> list[str]:
        """确保 image_paths 是干净的字符串列表。"""
        normalized_paths: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("image_paths 中的每一项都必须是非空字符串")
            normalized_paths.append(item.strip())
        return normalized_paths

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str | None) -> str | None:
        """允许 provider 为空，但不接受纯空白。"""
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return normalized


class ApiError(Exception):
    """对前端暴露的业务错误。"""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def create_app(
    *,
    root_dir: Path,
    build_runtime: Callable[[str | None], RuntimeLike],
    get_provider_statuses: Callable[[], list[dict[str, Any]]],
    logger: logging.Logger | None = None,
) -> FastAPI:
    """创建 FastAPI 应用。"""
    service_logger = logger or logging.getLogger("mini_agent.server")
    resolved_root = Path(root_dir).resolve()
    uploads_dir = (resolved_root / "uploads").resolve()
    index_path = (resolved_root / "webui" / "index.html").resolve()

    app = FastAPI(title="Mini Agent WebUI", docs_url=None, redoc_url=None)

    @app.exception_handler(ApiError)
    def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        """统一输出可预期的业务错误。"""
        service_logger.warning("接口错误: %s", exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    def handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """将 FastAPI 校验错误压平为前端可读消息。"""
        details = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error.get("loc", []))
            message = str(error.get("msg", "请求参数不合法"))
            details.append(f"{location}: {message}" if location else message)

        message = "请求参数不合法"
        if details:
            message = f"{message}: {'; '.join(details)}"

        service_logger.warning("请求校验失败: %s", message)
        return JSONResponse(
            status_code=422,
            content={"error": {"message": message}},
        )

    @app.exception_handler(Exception)
    def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        """兜底处理未捕获异常。"""
        service_logger.exception("未处理的服务端异常: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"message": "服务端内部错误，请查看日志。"}},
        )

    @app.get("/")
    def serve_index() -> Response:
        """提供 WebUI 静态页面入口。"""
        if index_path.is_file() and index_path.stat().st_size > 0:
            return FileResponse(index_path)

        return HTMLResponse(
            """
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Mini Agent WebUI</title>
  </head>
  <body style="font-family: sans-serif; padding: 24px;">
    <h1>Mini Agent WebUI</h1>
    <p>`webui/index.html` 尚未实现，当前只完成了 Phase 3.1 的服务端接口。</p>
  </body>
</html>
            """.strip()
        )

    @app.get("/api/providers")
    def list_providers() -> list[dict[str, Any]]:
        """返回 provider 的前端展示信息。"""
        providers: list[dict[str, Any]] = []
        for item in get_provider_statuses():
            providers.append(
                {
                    "name": str(item.get("name", "")),
                    "supports_vision": bool(item.get("supports_vision", False)),
                    "configured": bool(item.get("configured", False)),
                }
            )
        return providers

    @app.post("/api/upload")
    def upload_file(file: UploadFile = File(...)) -> dict[str, str]:
        """接收单个上传文件并落盘到 uploads/。"""
        uploads_dir.mkdir(parents=True, exist_ok=True)
        original_name = file.filename or "upload"
        safe_name = _make_unique_filename(uploads_dir, original_name)
        target_path = uploads_dir / safe_name

        try:
            content = file.file.read()
            target_path.write_bytes(content)
        except OSError as exc:
            service_logger.exception("保存上传文件失败: %s", original_name)
            raise ApiError(500, f"保存上传文件失败: {exc}") from exc
        finally:
            file.file.close()

        relative_path = target_path.relative_to(resolved_root).as_posix()
        return {"path": f"/{relative_path}"}

    @app.post("/api/chat")
    def chat(payload: ChatRequest) -> dict[str, Any]:
        """执行一次无状态 agent 请求。"""
        if payload.provider is not None and payload.provider not in ALLOWED_PROVIDERS:
            raise ApiError(
                400,
                f"不支持的 provider: {payload.provider}. 仅支持 kimi、qwen、deepseek。",
            )

        try:
            runtime = build_runtime(provider_override=payload.provider)
        except ValueError as exc:
            raise ApiError(400, str(exc)) from exc

        steps: list[dict[str, Any]] = []
        image_paths = [
            _resolve_client_path(resolved_root, image_path)
            for image_path in payload.image_paths
        ]
        try:
            reply = runtime.agent.run(
                user_text=payload.text,
                image_paths=image_paths or None,
                on_step=steps.append,
            )
        except Exception as exc:
            status_code, message = _classify_chat_error(exc)
            raise ApiError(status_code, message) from exc
        return {"reply": reply, "steps": steps}

    return app


def run_webui_server(
    *,
    root_dir: Path,
    host: str,
    port: int,
    build_runtime: Callable[[str | None], RuntimeLike],
    get_provider_statuses: Callable[[], list[dict[str, Any]]],
    logger: logging.Logger | None = None,
) -> None:
    """启动 WebUI 服务。"""
    service_logger = logger or logging.getLogger("mini_agent.server")
    app = create_app(
        root_dir=root_dir,
        build_runtime=build_runtime,
        get_provider_statuses=get_provider_statuses,
        logger=service_logger,
    )
    service_logger.info("启动 WebUI 服务: http://%s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")


def _sanitize_filename(filename: str) -> str:
    """将上传文件名清洗为安全格式。"""
    raw_path = Path(filename).name
    raw_suffix = Path(raw_path).suffix
    raw_stem = raw_path[: -len(raw_suffix)] if raw_suffix else raw_path

    safe_stem = FILENAME_SAFE_PATTERN.sub("_", raw_stem).strip("._")
    if not safe_stem:
        safe_stem = "upload"

    safe_suffix = ""
    if raw_suffix and re.fullmatch(r"\.[A-Za-z0-9]{1,20}", raw_suffix):
        safe_suffix = raw_suffix.lower()

    return f"{safe_stem[:100]}{safe_suffix}"


def _make_unique_filename(upload_dir: Path, original_name: str) -> str:
    """生成不冲突的上传文件名。"""
    safe_name = _sanitize_filename(original_name)
    safe_path = Path(safe_name)
    stem = safe_path.stem or "upload"
    suffix = safe_path.suffix[:20]

    while True:
        candidate = f"{stem}-{uuid4().hex[:12]}{suffix}"
        if not (upload_dir / candidate).exists():
            return candidate


def _resolve_client_path(root_dir: Path, path_value: str) -> str:
    """将前端传回的路径解析成可供 Agent 使用的绝对路径。"""
    if not isinstance(path_value, str) or not path_value.strip():
        raise ApiError(400, "非法图片路径: 路径不能为空")

    normalized = path_value.strip().replace("\\", "/")
    uploads_dir = (root_dir / "uploads").resolve()

    if normalized.startswith("uploads/"):
        normalized = f"/{normalized}"
    if not normalized.startswith("/uploads/"):
        raise ApiError(400, f"非法图片路径: {path_value}")

    resolved_path = (root_dir / normalized.lstrip("/")).resolve()
    try:
        resolved_path.relative_to(uploads_dir)
    except ValueError as exc:
        raise ApiError(400, f"非法图片路径: {path_value}") from exc

    if not resolved_path.exists() or not resolved_path.is_file():
        raise ApiError(400, f"图片文件不存在: {path_value}")

    return str(resolved_path)


def _classify_chat_error(exc: Exception) -> tuple[int, str]:
    """把运行时异常转换成对前端更清晰的响应。"""
    raw_message = str(exc).strip()
    lowered = raw_message.lower()
    status_code = getattr(exc, "status_code", None)

    if status_code == 400 or "maximum context length" in lowered:
        return (
            400,
            "请求内容过长。请换更小的图片、减少附件，或切换支持视觉输入的 provider。",
        )
    if status_code == 401 or "api key" in lowered or "authentication" in lowered:
        return (400, "当前 provider 的 API Key 无效或未配置。")
    if status_code == 403:
        return (400, "当前 provider 拒绝了这次请求，请检查模型权限或账户状态。")
    if status_code == 404:
        return (400, "当前 provider 或模型配置不可用，请检查 provider/model 设置。")
    if status_code == 429 or "rate limit" in lowered:
        return (429, "请求过于频繁或额度不足，请稍后重试。")

    if raw_message:
        preview = raw_message if len(raw_message) <= 240 else raw_message[:240] + "..."
        return (500, f"服务端调用模型失败：{preview}")

    return (500, "服务端内部错误，请查看日志。")
