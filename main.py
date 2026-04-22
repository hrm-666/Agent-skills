"""项目统一入口。

Phase 0.4 先约定一个轻量 bootstrap 流程，后续实现时严格沿用：

1. 加载 `.env`
2. 读取 `config.yaml`
3. 初始化日志
4. 初始化 `SkillLoader` 并扫描 `skills/`
5. 初始化 `ToolRegistry` 并注册 4 个内置工具
6. 根据当前 provider 创建 `LLM`
7. 创建 `Agent`

约定：
- `cli` 和 `webui` 都必须复用同一个运行时装配入口
- bootstrap 只负责“装配对象”，不承载业务逻辑
- `setup` 只复用配置和日志，不强依赖 `Agent`
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Sequence

import yaml
from adapters import run_cli_once, run_cli_repl, run_webui_server
from core import (
    Agent,
    LLM,
    PROVIDERS,
    SkillLoader,
    ToolRegistry,
    get_provider_env_key,
    is_provider_configured,
    list_provider_statuses,
)
from data.seed_sample_db import create_sample_db
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from rich.logging import RichHandler
from tools_builtin import (
    ACTIVATE_SKILL_TOOL,
    BASH_TOOL,
    READ_TOOL,
    WRITE_TOOL,
    create_activate_skill_handler,
    create_bash_handler,
    create_read_handler,
    create_write_handler,
)


ProviderName = Literal["kimi", "qwen", "deepseek"]
_LOGGING_STATE: dict[str, object] | None = None


class ProviderConfig(BaseModel):
    """单个 provider 的配置。"""

    model: str | None = None


class SkillsConfig(BaseModel):
    """Skills 目录与启用规则。"""

    dir: str = "./skills"
    enabled: list[str] | None = None


class AgentConfig(BaseModel):
    """Agent 基础配置。"""

    max_iterations: int = 15


class WebUIConfig(BaseModel):
    """WebUI 启动配置。"""

    host: str = "127.0.0.1"
    port: int = 8000


class AppConfig(BaseModel):
    """项目主配置。"""

    model_config = ConfigDict(extra="forbid")

    active_provider: ProviderName = "kimi"
    providers: dict[str, ProviderConfig] = Field(
        default_factory=lambda: {
            "kimi": ProviderConfig(model="kimi-k2.5"),
            "qwen": ProviderConfig(model="qwen-vl-max"),
            "deepseek": ProviderConfig(model="deepseek-chat"),
        }
    )
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    webui: WebUIConfig = Field(default_factory=WebUIConfig)

    @model_validator(mode="after")
    def validate_active_provider(self) -> "AppConfig":
        """确保 active_provider 在 providers 中存在。"""
        if self.active_provider not in self.providers:
            raise ValueError(
                f"active_provider '{self.active_provider}' 未在 providers 中定义"
            )
        return self


@dataclass
class BootstrapContext:
    """Phase 1.1 的基础上下文。

    后续 Phase 会在这个上下文上继续扩展 skill_loader、tool_registry、
    llm、agent 等运行时对象。
    """

    root_dir: Path
    env_path: Path
    config_path: Path
    log_path: Path
    config: AppConfig
    logger: logging.Logger


@dataclass
class RuntimeContext(BootstrapContext):
    """完整运行时上下文。"""

    skill_loader: SkillLoader
    tool_registry: ToolRegistry
    llm: LLM
    agent: Agent


def get_project_root() -> Path:
    """返回项目根目录。"""
    return Path(__file__).resolve().parent


def configure_console_streams() -> None:
    """尽量避免 Windows 控制台因编码问题导致日志崩溃。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                continue


def load_env_file(root_dir: Path) -> Path:
    """加载项目根目录下的 .env 文件。"""
    env_path = root_dir / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
    return env_path


def load_config(config_path: Path) -> AppConfig:
    """读取并校验 config.yaml。"""
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    raw_text = config_path.read_text(encoding="utf-8")
    raw_data = yaml.safe_load(raw_text) or {}
    if not isinstance(raw_data, dict):
        raise ValueError("config.yaml 顶层必须是 YAML mapping")

    try:
        return AppConfig.model_validate(raw_data)
    except ValidationError as exc:
        raise ValueError(f"config.yaml 校验失败:\n{exc}") from exc


def setup_logging(root_dir: Path) -> tuple[logging.Logger, Path]:
    """初始化文件日志与富文本控制台日志。"""
    global _LOGGING_STATE

    resolved_root = root_dir.resolve()
    logs_dir = root_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_path = logs_dir / f"agent-{datetime.now().date().isoformat()}.log"
    root_logger = logging.getLogger()
    logger = logging.getLogger("mini_agent.bootstrap")

    if (
        _LOGGING_STATE is not None
        and _LOGGING_STATE.get("root_dir") == resolved_root
        and _LOGGING_STATE.get("log_path") == log_path
        and root_logger.handlers
    ):
        logger.debug("日志系统已初始化，复用现有 handlers: %s", log_path)
        return logger, log_path

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root_logger.setLevel(logging.DEBUG)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = RichHandler(
        show_time=False,
        show_level=False,
        show_path=False,
        rich_tracebacks=True,
        markup=False,
    )
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # 压低第三方 SDK 的噪音日志，避免淹没 CLI 输出。
    for logger_name in ("openai", "httpx", "httpcore"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    _LOGGING_STATE = {
        "root_dir": resolved_root,
        "log_path": log_path,
    }
    logger.debug("日志初始化完成: %s", log_path)
    return logger, log_path


def log_request_received(
    logger: logging.Logger, user_text: str, image_paths: list[str] | None = None
) -> None:
    """记录收到的一次请求。"""
    logger.info("收到请求: text=%s, image_count=%d", user_text, len(image_paths or []))


def log_llm_call(
    logger: logging.Logger, iteration: int, provider: str, model: str | None
) -> None:
    """记录一次 LLM 调用。"""
    logger.info(
        "开始第 %d 轮 LLM 调用: provider=%s, model=%s",
        iteration,
        provider,
        model or "default",
    )


def log_tool_execution(
    logger: logging.Logger, tool_name: str, arguments: dict | None = None
) -> None:
    """记录一次工具执行。"""
    logger.info("执行工具: %s, args=%s", tool_name, arguments or {})


def log_messages_payload(logger: logging.Logger, messages: list) -> None:
    """记录完整的 messages payload。"""
    logger.debug("messages payload: %s", messages)


def log_tool_calls_payload(logger: logging.Logger, tool_calls: list) -> None:
    """记录完整的 tool_calls payload。"""
    logger.debug("tool_calls payload: %s", tool_calls)


def log_exception(logger: logging.Logger, message: str) -> None:
    """记录带异常栈的错误日志。"""
    logger.exception(message)


def _build_bootstrap_context(root_dir: Path | None = None) -> BootstrapContext:
    """构建 Phase 1.1 所需的基础上下文。"""
    configure_console_streams()
    project_root = root_dir or get_project_root()
    env_path = load_env_file(project_root)
    config_path = project_root / "config.yaml"
    config = load_config(config_path)
    logger, log_path = setup_logging(project_root)

    if env_path.exists():
        logger.debug("已加载环境变量文件: %s", env_path)
    else:
        logger.debug("未找到 .env 文件，将只使用系统环境变量")
    logger.debug("已读取配置文件: %s", config_path)
    logger.info("当前激活的 provider: %s", config.active_provider)

    return BootstrapContext(
        root_dir=project_root,
        env_path=env_path,
        config_path=config_path,
        log_path=log_path,
        config=config,
        logger=logger,
    )


def _resolve_project_path(root_dir: Path, path_value: str) -> Path:
    """将配置中的相对路径解析到项目根目录。"""
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate.resolve()
    return (root_dir / candidate).resolve()


def get_sample_db_path(root_dir: Path) -> Path:
    """返回 sample.db 的标准路径。"""
    return (root_dir / "data" / "sample.db").resolve()


def ensure_sample_db_exists(
    root_dir: Path,
    logger: logging.Logger,
    *,
    force: bool = False,
) -> str:
    """确保 sample.db 存在；默认不覆盖已有数据库。"""
    db_path = get_sample_db_path(root_dir)
    if db_path.exists() and not force:
        return f"Skipped: database already exists at {db_path}. Use --force to recreate it."

    message = create_sample_db(db_path, force=force)
    logger.info(message)
    return message


def _get_provider_api_key(provider: ProviderName) -> str:
    """从环境变量读取当前 provider 的 API Key。"""
    env_key = get_provider_env_key(provider)
    api_key = os.getenv(env_key, "").strip()
    if not api_key:
        raise ValueError(f"当前 provider '{provider}' 缺少 API Key，请设置环境变量 {env_key}")
    return api_key


def _register_builtin_tools(
    tool_registry: ToolRegistry,
    root_dir: Path,
    skill_loader: SkillLoader,
) -> None:
    """注册 4 个内置工具。"""
    tool_registry.register(
        READ_TOOL["name"],
        READ_TOOL["description"],
        READ_TOOL["parameters"],
        create_read_handler(root_dir=root_dir),
    )
    tool_registry.register(
        WRITE_TOOL["name"],
        WRITE_TOOL["description"],
        WRITE_TOOL["parameters"],
        create_write_handler(root_dir=root_dir),
    )
    tool_registry.register(
        BASH_TOOL["name"],
        BASH_TOOL["description"],
        BASH_TOOL["parameters"],
        create_bash_handler(root_dir=root_dir),
    )
    tool_registry.register(
        ACTIVATE_SKILL_TOOL["name"],
        ACTIVATE_SKILL_TOOL["description"],
        ACTIVATE_SKILL_TOOL["parameters"],
        create_activate_skill_handler(skill_loader=skill_loader),
    )


def build_runtime(provider_override: ProviderName | None = None) -> RuntimeContext:
    """统一运行时装配入口。"""
    bootstrap = _build_bootstrap_context()
    ensure_sample_db_exists(bootstrap.root_dir, bootstrap.logger)
    skills_dir = _resolve_project_path(bootstrap.root_dir, bootstrap.config.skills.dir)

    skill_loader = SkillLoader(
        skills_dir=skills_dir,
        enabled=bootstrap.config.skills.enabled,
        logger=logging.getLogger("mini_agent.skills"),
    )
    skill_loader.scan()

    tool_registry = ToolRegistry(logger=logging.getLogger("mini_agent.tools"))
    _register_builtin_tools(
        tool_registry=tool_registry,
        root_dir=bootstrap.root_dir,
        skill_loader=skill_loader,
    )

    provider = provider_override or bootstrap.config.active_provider
    provider_config = bootstrap.config.providers.get(provider)
    provider_model = provider_config.model if provider_config is not None else None
    api_key = _get_provider_api_key(provider)
    llm = LLM(
        provider=provider,
        api_key=api_key,
        model=provider_model,
        logger=logging.getLogger("mini_agent.llm"),
    )
    agent = Agent(
        llm=llm,
        skill_loader=skill_loader,
        tool_registry=tool_registry,
        max_iterations=bootstrap.config.agent.max_iterations,
        logger=logging.getLogger("mini_agent.agent"),
    )

    bootstrap.logger.info(
        "运行时装配完成: provider=%s, skills=%d, tools=%d, configured=%s",
        provider,
        len(skill_loader.catalog),
        len(tool_registry.tools),
        is_provider_configured(provider),
    )

    return RuntimeContext(
        root_dir=bootstrap.root_dir,
        env_path=bootstrap.env_path,
        config_path=bootstrap.config_path,
        log_path=bootstrap.log_path,
        config=bootstrap.config,
        logger=bootstrap.logger,
        skill_loader=skill_loader,
        tool_registry=tool_registry,
        llm=llm,
        agent=agent,
    )


def build_setup_context() -> BootstrapContext:
    """初始化 setup 命令所需的最小上下文（占位）。

    `setup` 只需要配置与日志能力，不应该为了建示例数据额外创建 `Agent`。
    """
    return _build_bootstrap_context()


def get_provider_status_dicts() -> list[dict[str, object]]:
    """返回后续 WebUI 可直接使用的 provider 状态。"""
    project_root = get_project_root()
    load_env_file(project_root)
    active_provider = load_config(project_root / "config.yaml").active_provider

    return [
        {
            "name": status.name,
            "supports_vision": status.supports_vision,
            "configured": status.configured,
            "default_model": status.default_model,
            "is_active": status.name == active_provider,
        }
        for status in list_provider_statuses()
    ]


def _create_argument_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description="Mini Agent 统一入口。直接运行不带子命令时默认启动 WebUI。",
    )
    subparsers = parser.add_subparsers(dest="command")

    cli_parser = subparsers.add_parser(
        "cli",
        help="单次执行或进入交互式 REPL",
        description="运行 Mini Agent CLI。",
    )
    cli_parser.add_argument("message", nargs="?", help="发送给 Agent 的消息内容")
    cli_parser.add_argument(
        "--interactive",
        action="store_true",
        help="启动交互式 REPL",
    )
    cli_parser.add_argument(
        "--show-steps",
        action="store_true",
        help="显示工具调用过程，便于调试",
    )
    cli_parser.add_argument(
        "--provider",
        choices=sorted(PROVIDERS),
        help="临时覆盖 config.yaml 中的 active_provider",
    )

    subparsers.add_parser(
        "webui",
        help="启动 WebUI 服务",
        description="启动 Mini Agent WebUI 服务。",
    )
    setup_parser = subparsers.add_parser(
        "setup",
        help="初始化示例数据",
        description="初始化示例 SQLite 数据库 sample.db。",
    )
    setup_parser.add_argument(
        "--force",
        action="store_true",
        help="如果 sample.db 已存在，则删除后重建",
    )
    return parser


def _run_cli_command(args: argparse.Namespace) -> int:
    """执行 cli 子命令。"""
    if args.interactive and args.message:
        raise ValueError("交互模式下不需要再传入 message")
    if not args.interactive and not args.message:
        raise ValueError("请提供消息内容，或使用 --interactive 进入交互模式")

    runtime = build_runtime(provider_override=args.provider)
    if args.interactive:
        run_cli_repl(runtime.agent, show_steps=args.show_steps)
        return 0

    run_cli_once(
        runtime.agent,
        args.message,
        show_steps=args.show_steps,
    )
    return 0


def _run_webui_command() -> int:
    """执行 webui 子命令。"""
    context = build_setup_context()
    ensure_sample_db_exists(context.root_dir, context.logger)
    run_webui_server(
        root_dir=context.root_dir,
        host=context.config.webui.host,
        port=context.config.webui.port,
        build_runtime=build_runtime,
        get_provider_statuses=get_provider_status_dicts,
        logger=logging.getLogger("mini_agent.server"),
    )
    return 0


def _run_setup_command(args: argparse.Namespace) -> int:
    """执行 setup 子命令。"""
    context = build_setup_context()
    message = ensure_sample_db_exists(
        context.root_dir,
        context.logger,
        force=args.force,
    )
    print(message)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """主入口。"""
    parser = _create_argument_parser()
    args = parser.parse_args(argv)

    try:
        if args.command is None:
            return _run_webui_command()
        if args.command == "cli":
            return _run_cli_command(args)
        if args.command == "webui":
            return _run_webui_command()
        if args.command == "setup":
            return _run_setup_command(args)
        parser.error(f"未知命令: {args.command}")
    except Exception as exc:
        print(f"[error] {exc}", file=os.sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
