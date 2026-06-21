import os
import re
import json
import subprocess
import sys
from abc import ABC, abstractmethod
import time
from typing import Union
from pathlib import Path
from openai import OpenAI

from tools.TodoManager import TodoManager
from settings.config_loader import config

# 导入回滚日志管理器
try:
    from utils.RollbackLogger import get_rollback_logger
except ImportError:
    get_rollback_logger = None

# 避免循环导入 - 延迟导入LogManager
def _get_logger():
    try:
        from utils.LogManager import logger
        return logger
    except ImportError:
        return None

class AgentCore(ABC):
    def __init__(self, agent_type: str = "Agent"):
        self.config = config
        self.agent_type = agent_type
        self.WORKDIR = Path.cwd()
        api_key = config.api_key or os.environ.get("OPENAI_API_KEY")
        
        self.client = OpenAI(
            base_url=config.base_url,
            api_key=api_key
        )
        self.todo = TodoManager()
        self.MODEL = config.model_name
        self.PROMOTE = config.system_prompt
        self.TOOL_HANDLERS = {
            "bash": lambda **kw: self.run_bash(kw["command"]),
            "read_file": lambda **kw: self.run_read(kw["path"], kw.get("limit")),
            "write_file": lambda **kw: self.run_write(kw["path"], kw["content"]),
            "edit_file": lambda **kw: self.run_edit(kw["path"], kw["old_text"], kw["new_text"]),
            "todo": lambda **kw: self.todo.update(kw["items"])
        }
        self.TOOLS = config.tools
        # 定义终止标志
        self.MARKERS = config.markers
        self.enable_loop = config.enable_loop
        
        # 日志记录器（延迟初始化）
        self._logger = None
        
        # 回滚日志管理器
        self._rollback_logger = None
        
        # 循环控制状态
        self.last_tool_key = None
        self.consecutive_duplicates = 0
        
    @property
    def logger(self):
        if self._logger is None:
            self._logger = _get_logger()
        return self._logger
    
    @property
    def rollback_logger(self):
        if self._rollback_logger is None and get_rollback_logger:
            self._rollback_logger = get_rollback_logger()
        return self._rollback_logger
        
    def safe_path(self, p: str) -> Path:
            # 禁止相对路径中包含 .. （防止目录遍历攻击）
            if ".." in p or p.startswith("/"):
                raise ValueError(f"Path traversal not allowed: {p}")
            
            path = (self.WORKDIR / p).resolve()
            
            # 严格检查：path 必须在 WORKDIR 内
            try:
                # Python 3.9+
                if not path.is_relative_to(self.WORKDIR):
                    raise ValueError(f"Path escapes workspace: {p} -> {path}")
            except AttributeError:
                # Python 3.8 及更低，手动检查
                workdir_str = str(self.WORKDIR).replace("\\", "/")
                path_str = str(path).replace("\\", "/")
                if not path_str.startswith(workdir_str):
                    raise ValueError(f"Path escapes workspace: {p} -> {path}")
            
            return path

    def run_cmd(self, command: str) -> str:
        start_time = time.time()
        
        # 记录工具调用
        if self.logger:
            self.logger.info(f"Executing bash: {command[:50]}...", tool="bash")
        
        # 禁止执行可能导致卡死或无法非交互式处理的命令
        dangerous_patterns = [
            r'\btype\s+\*$',         # 禁止 type * (输出所有文件内容)
            r'\bedel\s*$',           # 禁止不带参数的 del
            r'\bcopy\s+con\s+\.',    # 禁止 copy con . (交互输入)
            r'\bpause$',             # 禁止 pause
            r'\bset\b',              # 禁止 set (修改环境变量)
            r'\bcls\b',              # 禁止 cls
            r'\bmore\b',             # 禁止 more
            r'\bcmd\b',              # 禁止 cmd (嵌套)
            r'^\s*cd\s+go\s*$',      # 防止奇怪的跳转
            r'^\s*if\s+exist\s+$',   # 防止逻辑错误
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return f"\033[31m Error:\033[0m Command blocked for safety: {command}"

        dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
        if any(d in command for d in dangerous):
            return "\033[31m$ Error:\033[0m Dangerous command blocked"
        try:
            if os.name == 'nt':    # windows
                if '*' in command or '?' in command:
                    cmd = f"cmd /c {command}"
                else:
                    cmd = f"cmd /c \"{command}\""
                # 将单引号替换为空，防止命令截断
                safe_cmd = command.replace("'", "'\"'\"'")
                # PowerShell 命令格式：powershell -NoProfile -ExecutionPolicy Bypass -Command "cmd"
                command = f'powershell -NoProfile -ExecutionPolicy Bypass -Command "{safe_cmd}"'
                command = command.replace('&&', ';').replace('||', ';')
                result = subprocess.run(cmd, shell=True, cwd=os.getcwd(),
                               capture_output=True, text=True, encoding='gbk' if sys.platform == 'win32' else None, errors='replace', timeout=120)
            else:
                result = subprocess.run(command, shell=True, cwd=os.getcwd(),
                               capture_output=True, text=True, timeout=120)
            
            # 合并stdout和stderr防止命令混合输出导致解析混乱
            out = (result.stdout + result.stderr).strip()
            safe_lines = [line for line in out.splitlines() if "[WinError 5]" not in line and "拒绝访问" not in line]
            out = "\n".join(safe_lines)
            return out[:50000] if out else "(no output)"
        except subprocess.TimeoutExpired:
            return "\033[31m Error:\033[0m Timeout (120s)"
        except Exception as e:
            return f"\033[31m Error:\033[0m {str(e)}"
        
    def run_read(self, path: str, limit: int = None) -> str:
        try:
            try:
                text = self.safe_path(path).read_text(encoding='utf-8')
            except UnicodeDecodeError:
                text = self.safe_path(path).read_text(encoding='gbk', errors='replace')
            lines = text.splitlines()
            if limit and limit < len(lines):
                lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
                return "\n".join(lines)[:50000]
            return text
        except Exception as e:
            return f"\033[31m Error:\033[0m {str(e)}"
        
    def run_write(self, path: str, content: str) -> str:
        try:
            fp = self.safe_path(path)
            # 记录操作以便回滚
            if self.rollback_logger:
                self.rollback_logger.record_write(str(fp), content)
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content, encoding='utf-8')
            return f"\033[32m File created successfully at {path}. \
                Content written ({len(content)} bytes). \
                Task ready to complete.\033[0m"
        except Exception as e:
            return f"\033[31m Error:\033[0m {str(e)}"
        
    def run_edit(self, path: str, old_text: str, new_text: str) -> str:
        try:
            fp = self.safe_path(path)
            if not fp.exists():
                return f"\033[31m Error:\033[0m File not found in {path}"
            
            # 确保 content 有值
            try:
                content = fp.read_text(encoding='utf-8')
            except Exception as e:
                return f"\033[31m Error:\033[0m reading file {str(e)}"
            
            if old_text not in content:
                return f"\033[31m Error:\033[0m text '{old_text[:20]}...' not found in {path}"
            
            # 记录操作以便回滚
            if self.rollback_logger:
                self.rollback_logger.record_edit(str(fp), old_text, new_text)
            
            content = fp.read_text()
            fp.write_text(content.replace(old_text, new_text, 1))
            return f"Edited {path}"
        except Exception as e:
            return f"\033[31m Error:\033[0m {str(e)}"
    
    def response_check(self, response, messages: list, is_subagent: bool) -> Union[str, bool, None]:
        agent_type = "SubAgent" if is_subagent else "Agent"
        if not response.choices or len(response.choices) == 0:
            print(f"\033[31m {agent_type} Error:\033[0m API return no reply.")
            self.enable_loop = False
            return False
        
        msg = response.choices[0].message
        assistant_msg = {
            "role": "assistant", 
            "content": msg.content
        }
        
        # 检查是否有工具调用
        # 如果之前有工具调用，将其存入 history 以匹配后续的 tool response
        if msg.tool_calls:
            assistant_msg["tool_calls"] = msg.tool_calls
                
        # 检查是否包含终止标志
        if not msg.tool_calls:
            content = msg.content
            # 检查关键词
            is_done = any(re.search(m, content, re.IGNORECASE) for m in self.MARKERS)
                
            if is_done:
                print(f"\033[32m$ {agent_type} report SUCCEED, mission accomplished!\033[0m")
                self.enable_loop = False
                return content
                
            # 如果没有工具调用且没提到完成，通常也意味着结束
            if content and content.strip():
                print(f"{agent_type} generated something but didn't mark task complete: {content}")
                print(f"{agent_type} stop using tools, job finished.")
                self.enable_loop = False
                return content
            
        messages.append(assistant_msg)
        return None
    
    def check_duplicate_operation(self, tool_name: str, args: dict) -> bool:
        """
        检测重复操作，防止死循环
        
        参数:
            tool_name: 工具名称
            args: 工具参数
            
        返回:
            True: 检测到重复操作（连续3次及以上）
            False: 正常操作
        """
        # 构建唯一键用于重复检测 (tool_name + 参数哈希)
        arg_key = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
        
        # 熔断逻辑：防止死循环
        if self.last_tool_key == arg_key:
            self.consecutive_duplicates += 1
            print(f"\033[33m$ Repeat operation detected (#{self.consecutive_duplicates}): {tool_name} -> {args}\033[0m")
            
            if self.consecutive_duplicates >= 3:
                print("\033[31m$ Repeat operation detected multiple times, task was forcibly stopped.\033[0m")
                return True  # 检测到重复，停止
        else:
            self.last_tool_key = arg_key
            self.consecutive_duplicates = 1  # reset counter
        
        return False  # 正常操作
