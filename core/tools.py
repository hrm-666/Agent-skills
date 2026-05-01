"""
工具注册表：统一管理所有内置工具的 schema 和处理函数
"""
import logging
import shlex
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Literal, Optional

logger = logging.getLogger(__name__)

PolicyAction = Literal["allow", "confirm", "block"]
RiskLevel = Literal["low", "medium", "high"]


@dataclass
class ToolError:
    type: str
    message: str
    recoverable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ToolResult:
    ok: bool
    data: Any = None
    error: Optional[ToolError] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(cls, data: Any, meta: Optional[Dict[str, Any]] = None) -> "ToolResult":
        return cls(ok=True, data=data, meta=meta or {})

    @classmethod
    def failure(
        cls,
        error_type: str,
        message: str,
        recoverable: bool = True,
        meta: Optional[Dict[str, Any]] = None,
    ) -> "ToolResult":
        return cls(
            ok=False,
            error=ToolError(type=error_type, message=message, recoverable=recoverable),
            meta=meta or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "data": self.data,
            "error": self.error.to_dict() if self.error else None,
            "meta": self.meta,
        }


@dataclass
class PolicyDecision:
    action: PolicyAction
    reason: str = ""
    risk_level: RiskLevel = "low"
    matched: Optional[str] = None

    @classmethod
    def allow(cls) -> "PolicyDecision":
        return cls(action="allow")

    @classmethod
    def confirm(cls, reason: str, risk_level: RiskLevel = "medium", matched: Optional[str] = None) -> "PolicyDecision":
        return cls(action="confirm", reason=reason, risk_level=risk_level, matched=matched)

    @classmethod
    def block(cls, reason: str, risk_level: RiskLevel = "high", matched: Optional[str] = None) -> "PolicyDecision":
        return cls(action="block", reason=reason, risk_level=risk_level, matched=matched)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


DEFAULT_POLICY_CONFIG: Dict[str, Any] = {
    "default": "allow",
    "block_tools": [],
    "confirm_tools": [],
    "bash": {
        "blocked_patterns": [
            "rm -rf /",
            "rm -rf /*",
            "sudo",
            "shutdown",
            "reboot",
            "> /dev/",
            "mkfs",
            "dd if=",
        ],
        "confirm_patterns": [
            "rm ",
            "mv ",
            "chmod ",
            "chown ",
        ],
    },
    "write": {
        "confirm_paths": [
            ".env",
            "config.yaml",
        ],
    },
}


class ToolPolicy:
    def __init__(self, config: Optional[Dict[str, Any]] = None, workspace_dir: str = "./workspace"):
        self.config = _deep_merge(DEFAULT_POLICY_CONFIG, config or {})
        self.workspace_dir = Path(workspace_dir).resolve()

    def check(self, tool_name: str, args: Dict[str, Any]) -> PolicyDecision:
        if tool_name in set(self.config.get("block_tools") or []):
            return PolicyDecision.block(f"工具 '{tool_name}' 已被策略禁用", matched=tool_name)

        if tool_name in set(self.config.get("confirm_tools") or []):
            return PolicyDecision.confirm(f"工具 '{tool_name}' 需要用户确认", matched=tool_name)

        if tool_name == "bash":
            return self._check_bash(str(args.get("command", "")))

        if tool_name == "write":
            return self._check_write(str(args.get("path", "")))

        if self.config.get("default", "allow") == "block":
            return PolicyDecision.block(f"工具 '{tool_name}' 被默认策略禁用")

        if self.config.get("default") == "confirm":
            return PolicyDecision.confirm(f"工具 '{tool_name}' 被默认策略要求确认")

        return PolicyDecision.allow()

    def _check_bash(self, command: str) -> PolicyDecision:
        bash_cfg = self.config.get("bash") or {}
        lowered = command.lower()

        if _looks_like_write_outside_workspace(command, self.workspace_dir):
            return PolicyDecision.block(
                reason=f"安全限制：bash 仅允许写入 {self.workspace_dir}，禁止写入其他位置。",
                matched="write-outside-workspace",
            )
        if _runs_workspace_python_script(command):
            return PolicyDecision.block(
                reason="安全限制：禁止通过 bash 执行 workspace/ 下的 Python 脚本（可能绕过写路径限制）。",
                matched="workspace-python",
            )

        if _looks_like_ambiguous_delete(command):
            return PolicyDecision.block(
                reason="删除目标路径不明确。请先用 ls/find 定位文件，并使用明确路径后再删除。",
                matched="ambiguous rm",
            )

        matched = _find_match(lowered, bash_cfg.get("blocked_patterns") or [])
        if matched:
            return PolicyDecision.block(
                reason=f"命令命中高危禁用规则：{matched}",
                matched=matched,
            )

        matched = _find_match(lowered, bash_cfg.get("confirm_patterns") or [])
        if matched:
            return PolicyDecision.confirm(
                reason=f"命令命中风险确认规则：{matched}",
                matched=matched,
            )

        return PolicyDecision.allow()

    def _check_write(self, path: str) -> PolicyDecision:
        write_cfg = self.config.get("write") or {}
        lowered = path.lower()
        matched = _find_match(lowered, write_cfg.get("confirm_paths") or [])
        if matched:
            return PolicyDecision.confirm(
                reason=f"写入该路径需要确认：{matched}",
                matched=matched,
            )
        try:
            p = Path(path).resolve()
            p.relative_to(self.workspace_dir)
        except Exception:
            return PolicyDecision.block(
                reason=f"安全限制：write 只能写入 {self.workspace_dir}",
                matched="write-outside-workspace",
            )
        if p.exists():
            return PolicyDecision.confirm(
                reason=f"目标文件已存在，是否覆盖：{p}",
                matched="overwrite-existing-file",
            )
        return PolicyDecision.allow()


class ToolRegistry:
    def __init__(self, policy: Optional[ToolPolicy] = None):
        # name -> {"schema": dict, "handler": Callable}
        self.tools: Dict[str, Dict] = {}
        self.policy = policy or ToolPolicy()

    def register(self, name: str, description: str, parameters: dict, handler: Callable):
        """注册一个工具"""
        self.tools[name] = {
            "schema": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            },
            "handler": handler,
        }
        logger.debug(f"工具已注册：{name}")

    def get_openai_schemas(self) -> list[dict]:
        """返回 OpenAI function calling 格式的 tools 列表"""
        return [v["schema"] for v in self.tools.values()]

    def execute(self, name: str, arguments: dict, confirmed: bool = False) -> ToolResult:
        """
        执行工具，返回结构化结果。
        不存在的工具返回结构化错误（让 LLM 自己纠错，而不是抛异常）。
        """
        if name not in self.tools:
            available = ", ".join(self.tools.keys())
            return ToolResult.failure(
                "ToolNotFound",
                f"工具 '{name}' 不存在。可用工具：{available}",
                recoverable=True,
            )

        decision = self.policy.check(name, arguments or {})
        if decision.action == "block":
            logger.warning(f"工具 {name} 被策略阻止：{decision.reason}")
            return ToolResult.failure(
                "PolicyBlocked",
                decision.reason,
                recoverable=False,
                meta={"policy": decision.to_dict(), "tool_name": name, "args": arguments},
            )
        if decision.action == "confirm" and not confirmed:
            logger.info(f"工具 {name} 需要用户确认：{decision.reason}")
            return ToolResult.failure(
                "ConfirmationRequired",
                decision.reason,
                recoverable=True,
                meta={
                    "policy": decision.to_dict(),
                    "confirmation": {
                        "tool_name": name,
                        "args": arguments,
                        "reason": decision.reason,
                        "risk_level": decision.risk_level,
                    },
                },
            )

        try:
            logger.info(f"执行工具：{name}，参数：{arguments}")
            result = self.tools[name]["handler"](**arguments)
            if isinstance(result, ToolResult):
                return result
            result_str = str(result)
            logger.info(f"工具 {name} 执行完成，输出长度：{len(result_str)}")
            logger.debug(f"工具 {name} 输出：{result_str[:500]}")
            meta = {}
            if confirmed:
                meta["confirmed"] = True
                meta["policy"] = decision.to_dict()
            if name == "bash" and isinstance(result, dict):
                exit_code = result.get("exit_code")
                if result.get("timed_out") or exit_code != 0:
                    return ToolResult(
                        ok=False,
                        data=result,
                        error=ToolError(
                            type="CommandFailed",
                            message=_bash_error_message(result),
                            recoverable=True,
                        ),
                        meta=meta,
                    )
            return ToolResult.success(result, meta=meta)
        except Exception as e:
            logger.error(f"工具 {name} 执行出错：{e}", exc_info=True)
            return ToolResult.failure("ToolExecutionError", f"工具 '{name}' 执行失败：{e}", recoverable=True)


def _bash_error_message(result: dict) -> str:
    if result.get("timed_out"):
        return result.get("stderr") or "bash 命令执行超时"
    exit_code = result.get("exit_code")
    stderr = (result.get("stderr") or "").strip()
    if stderr:
        return f"bash 命令执行失败，exit_code={exit_code}：{stderr}"
    return f"bash 命令执行失败，exit_code={exit_code}"


def _find_match(value: str, patterns: Iterable[str]) -> Optional[str]:
    for pattern in patterns:
        pattern_text = str(pattern).lower()
        if pattern_text and pattern_text in value:
            return str(pattern)
    return None


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _looks_like_ambiguous_delete(command: str) -> bool:
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if not parts or parts[0] != "rm":
        return False

    targets = [p for p in parts[1:] if not p.startswith("-")]
    if not targets:
        return False

    for target in targets:
        if target.startswith(("/", "~", "./", "../")) or "/" in target:
            continue
        return True
    return False


def _looks_like_write_outside_workspace(command: str, workspace_dir: Path) -> bool:
    lowered = command.lower().replace("\\", "/")

    # Common mutating patterns in shell / PowerShell / cmd / scripts.
    write_markers = [
        ">",
        ">>",
        "out-file",
        "set-content",
        "add-content",
        "new-item",
        "copy ",
        "copy-item",
        "move ",
        "move-item",
        "mv ",
        "cp ",
        "tee ",
        "write_text(",
        "open(",
        "w'",
        'w"',
        "wb",
        "json.dump(",
    ]
    if not any(marker in lowered for marker in write_markers):
        return False
    workspace_norm = str(workspace_dir).lower().replace("\\", "/")
    if "workspace/" in lowered or workspace_norm in lowered:
        return False
    return True


def _runs_workspace_python_script(command: str) -> bool:
    lowered = command.lower().replace("\\", "/")
    if "python" not in lowered:
        return False
    return " workspace/" in f" {lowered}" or "python workspace/" in lowered
