"""
对话记忆管理模块
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

MEMORY_CONFIG_FILE = ".memory_config.json"
MEMORY_DATA_FILE = "memory_history.json"


class ConversationMemory:
    """对话记忆管理器"""
    
    def __init__(self, reset_on_start: bool = True):
        """
        初始化记忆
        reset_on_start: 是否在启动时重置记忆（默认 True）
        """
        self.mode = "none"
        self.limit = 10
        self.history: List[Dict] = []
        
        if reset_on_start:
            # 启动时重置，不加载之前的配置和历史
            self.clear_all()
            logger.info("记忆已重置（启动时清空）")
        else:
            self._load_config()
            self._load_history()
    
    def _load_config(self):
        """加载记忆配置"""
        config_path = Path(MEMORY_CONFIG_FILE)
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.mode = config.get("mode", "none")
                    self.limit = config.get("limit", 10)
                logger.info(f"加载记忆配置: mode={self.mode}, limit={self.limit}")
            except Exception as e:
                logger.warning(f"加载记忆配置失败: {e}")
    
    def save_config(self):
        """保存记忆配置"""
        config = {
            "mode": self.mode,
            "limit": self.limit,
            "updated_at": datetime.now().isoformat()
        }
        with open(MEMORY_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        logger.info(f"保存记忆配置: mode={self.mode}, limit={self.limit}")
    
    def _load_history(self):
        """加载永久记忆历史"""
        if self.mode == "permanent":
            history_path = Path(MEMORY_DATA_FILE)
            if history_path.exists():
                try:
                    with open(history_path, 'r', encoding='utf-8') as f:
                        self.history = json.load(f)
                    logger.info(f"加载永久记忆: {len(self.history)} 条记录")
                except Exception as e:
                    logger.warning(f"加载记忆历史失败: {e}")
                    self.history = []
            else:
                self.history = []
    
    def save_history(self):
        """保存永久记忆历史"""
        if self.mode == "permanent":
            with open(MEMORY_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
            logger.info(f"保存永久记忆: {len(self.history)} 条记录")
    
    def clear_history(self):
        """清空记忆历史"""
        self.history = []
        if self.mode == "permanent":
            history_path = Path(MEMORY_DATA_FILE)
            if history_path.exists():
                history_path.unlink()
        logger.info("清空记忆历史")
    
    def clear_all(self):
        """完全清空所有记忆（包括配置和历史文件）"""
        self.mode = "none"
        self.limit = 10
        self.history = []
        
        # 删除配置文件
        config_path = Path(MEMORY_CONFIG_FILE)
        if config_path.exists():
            config_path.unlink()
        
        # 删除历史文件
        history_path = Path(MEMORY_DATA_FILE)
        if history_path.exists():
            history_path.unlink()
        
        logger.info("完全清空所有记忆文件")
    
    def add_exchange(self, user_message: str, assistant_message: str):
        """添加一轮对话到记忆"""
        exchange = {
            "user": user_message,
            "assistant": assistant_message,
            "timestamp": datetime.now().isoformat()
        }
        
        if self.mode == "none":
            return
        elif self.mode == "limited":
            self.history.append(exchange)
            if len(self.history) > self.limit:
                self.history = self.history[-self.limit:]
        elif self.mode == "permanent":
            self.history.append(exchange)
        
        if self.mode == "permanent":
            self.save_history()
    
    def get_context_messages(self) -> List[Dict]:
        """获取用于 LLM 上下文的对话历史"""
        if self.mode == "none":
            return []
        
        messages = []
        for exchange in self.history:
            messages.append({"role": "user", "content": exchange["user"]})
            messages.append({"role": "assistant", "content": exchange["assistant"]})
        
        return messages
    
    def get_info(self) -> Dict:
        """获取记忆状态信息"""
        return {
            "mode": self.mode,
            "limit": self.limit if self.mode == "limited" else None,
            "count": len(self.history),
            "history": self.history[-10:] if self.history else []
        }


_global_memory: Optional[ConversationMemory] = None


def get_memory(reset: bool = True) -> ConversationMemory:
    """
    获取全局记忆实例
    reset: 是否重置记忆（默认 True，每次启动重置）
    """
    global _global_memory
    if _global_memory is None:
        _global_memory = ConversationMemory(reset_on_start=reset)
    return _global_memory


def set_memory_mode(mode: str, limit: int = 10):
    """设置记忆模式"""
    memory = get_memory(reset=False)
    if mode not in ["none", "limited", "permanent"]:
        raise ValueError(f"无效模式: {mode}")
    
    memory.mode = mode
    memory.limit = limit
    
    if mode == "permanent":
        memory.save_history()
    elif mode == "none":
        memory.clear_history()
    elif mode == "limited":
        if len(memory.history) > limit:
            memory.history = memory.history[-limit:]
    
    memory.save_config()
    logger.info(f"记忆模式已切换: {mode}, limit={limit}")


def add_to_memory(user_message: str, assistant_message: str):
    """添加对话到记忆"""
    memory = get_memory(reset=False)
    memory.add_exchange(user_message, assistant_message)


def clear_memory():
    """清空记忆"""
    memory = get_memory(reset=False)
    memory.clear_history()


def reset_memory():
    """完全重置记忆（清除所有文件，恢复到初始状态）"""
    global _global_memory
    _global_memory = None  # 重置全局实例
    # 删除配置文件
    config_path = Path(MEMORY_CONFIG_FILE)
    if config_path.exists():
        config_path.unlink()
    # 删除历史文件
    history_path = Path(MEMORY_DATA_FILE)
    if history_path.exists():
        history_path.unlink()
    logger.info("记忆已完全重置（文件已删除）")