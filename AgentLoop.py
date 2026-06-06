import os
import re
import json
import subprocess
from pathlib import Path

from openai import OpenAI

def singleton(cls):
    instances = {}
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    return get_instance

@singleton
class agent_core:
    def __init__(self):
        self.WORKDIR = Path.cwd()
        api_key = os.getenv("DEEPSEEK_API_KEY")
        
        self.client = OpenAI(
            base_url="https://api.deepseek.com",
            api_key=api_key
        )
        self.MODEL = "deepseek-v4-pro"
        self.SYSTEM = f"""
            You are an autonomous coding agent operating at {os.getcwd()} and your name is Cody.
            GOAL: Solve user tasks using Windows cmd commands and file tools.
            STRICT RULES:
            1. **Act, do not explain.**
            2. **Completion Signal:** When a file is created or a task is done, your FINAL message BEFORE calling any tools (or if no tools needed) MUST contain the exact phrase: "##TASK_COMPLETE##".
            3. **No Loops:** If you have successfully written a file and verified it, output "##TASK_COMPLETE##" and stop. Do NOT run extra verification commands like 'read_file' or 'dir' after you are already done, unless the user explicitly asks to see it.
            4. **Immediate Stop:** Once "##TASK_COMPLETE##" is output, the system will stop. Do not generate more commands.
            5. **Strict Workspace Constraint:** Files MUST be created in {os.getcwd()} or its subdirectories ONLY. NEVER use ".." in paths. Valid paths: "file.txt", "folder/file.txt", "./file.txt". Invalid: "../file.txt", "../../file.txt". Stay within the workspace {os.getcwd()}.
            """
        self.TOOL_HANDLERS = {
            "cmd": lambda **kw: self.run_cmd(kw["command"]),
            "read_file": lambda **kw: self.run_read(kw["path"], kw.get("limit")),
            "write_file": lambda **kw: self.run_write(kw["path"], kw["content"]),
            "edit_file": lambda **kw: self.run_edit(kw["path"], kw["old_text"], kw["new_text"]),
        }
        self.TOOLS = [
            {
                "type": "function",
                "function": {"name": "cmd", 
                             "description": "Run a shell command.", 
                             "parameters": {"type": "object", 
                                            "properties": {"command": {"type": "string"}}, 
                                            "required": ["command"]}}
            },
            {
                "type": "function",
                "function": {"name": "read_file", 
                             "description": "Read file contents.", 
                             "parameters": {"type": "object", 
                                            "properties": {"path": {"type": "string"}, 
                                                           "limit": {"type": "integer"}}, 
                                            "required": ["path"]}}
            },
            {
                "type": "function",
                "function": {"name": "write_file", 
                             "description": "Write content to file.", 
                             "parameters": {"type": "object", 
                                   "properties": {"path": {"type": "string"}, 
                                                  "content": {"type": "string"}}, 
                                   "required": ["path"]}}
            },
            {
                "type": "function",
                "function": {"name": "edit_file", 
                             "description": "Replace exact text in file.", 
                             "parameters": {"type": "object", 
                                            "properties": {"path": {"type": "string"}, 
                                                           "old_text": {"type": "string"}, 
                                                           "new_text": {"type": "string"}}, 
                                            "required": ["path", "old_text", "new_text"]}}
            },
        ]
        # 定义终止标志
        self.MARKERS = ["##TASK_COMPLETE##", "任务完成", "Done", "success"]
        self.enable_loop = True
        
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
        dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
        if any(d in command for d in dangerous):
            return "Error: Dangerous command blocked"
        try:
            if os.name == 'nt':    # windows
                # 将单引号替换为空，防止命令截断
                safe_cmd = command.replace("'", "'\"'\"'")
                # PowerShell 命令格式：powershell -NoProfile -ExecutionPolicy Bypass -Command "cmd"
                command = f'powershell -NoProfile -ExecutionPolicy Bypass -Command "{safe_cmd}"'
                command = command.replace('&&', ';').replace('||', ';')
                result = subprocess.run(command, shell=True, cwd=os.getcwd(),
                               capture_output=True, text=True, encoding=None, errors='replace', timeout=120)
            else:
                result = subprocess.run(command, shell=True, cwd=os.getcwd(),
                               capture_output=True, text=True, timeout=120)
            # 合并stdout和stderr防止命令混合输出导致解析混乱
            out = (result.stdout + result.stderr).strip()
            return out[:50000] if out else "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: Timeout (120s)"
        except Exception as e:
            return f"Error: {str(e)}"
        
    def run_read(self, path: str, limit: int = None) -> str:
        try:
            text = self.safe_path(path).read_text()
            lines = text.splitlines()
            if limit and limit < len(lines):
                lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
                return "\n".join(lines)[:50000]
            return text
        except Exception as e:
            return f"Error: {str(e)}"
        
    def run_write(self, path: str, content: str) -> str:
        try:
            fp = self.safe_path(path)
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content, encoding='utf-8')
            return f"File created successfully at {path}. \
                Content written ({len(content)} bytes). \
                Task ready to complete."
        except Exception as e:
            return f"Error: {str(e)}"
        
    def run_edit(self, path: str, old_text: str, new_text: str) -> str:
        try:
            fp = self.safe_path(path)
            if not fp.exists():
                return f"Error: File not found in {path}"
            
            # 确保 content 有值
            try:
                content = fp.read_text(encoding='utf-8')
            except Exception as e:
                return f"Error reading file: {str(e)}"
            
            if old_text not in content:
                return f"Error: text '{old_text[:20]}...' not found in {path}"
            content = fp.read_text()
            fp.write_text(content.replace(old_text, new_text, 1))
            return f"Edited {path}"
        except Exception as e:
            return f"Error: {str(e)}"

    def agent_loop(self, messages: list, max_steps=10):
        self.enable_loop = True
        self.last_tool_key = None     # 上一次的 (tool_name, args)组合
        self.consecutive_duplicates = 0
        
        step = 1
            
        while self.enable_loop and step <= max_steps:
            print(f"\n--- Step {step} / {max_steps} ---")
            
            try:
                response = self.client.chat.completions.create(
                    model=self.MODEL,
                    messages=[{"role": "system", "content": self.SYSTEM}] + messages,
                    tools=self.TOOLS,
                    max_tokens=8000,
                    tool_choice="auto",
                )
            except Exception as e:
                print(f"\033[31mAPI Error: {e}\033[0m")
                self.enable_loop = False
                return
            
            # 先检查消息是否存在
            if not response.choices or len(response.choices) == 0:
                print("Error: API return no reply")
                self.enable_loop = False
                return

            msg = response.choices[0].message
            
            # 保存 assistant 消息时，必须同时保存 tool_calls
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
                    print("Agent report SUCCEED, mission accomplished!")
                    self.enable_loop = False
                    return content
                
                # 如果没有工具调用且没提到完成，通常也意味着结束
                print("Agent stop using tools, job finished.")
                self.enable_loop = False
                return content
            
            messages.append(assistant_msg)
            
            results = []
            is_duplicate = False
            for tool_call in msg.tool_calls:
                tool_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except:
                    args = {}
            
                # 构建唯一键用于重复检测 (tool_name + 参数哈希)
                arg_key = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
                
                # 熔断逻辑：防止死循环
                if self.last_tool_key == arg_key:
                    self.consecutive_duplicates += 1
                    print(f"Repeat operation detected (#{self.consecutive_duplicates}): {tool_name} -> {args}")
                    if self.consecutive_duplicates >= 3:
                        print("Repeat operation detected mutiple times, task was forcibly stopped.")
                        is_duplicate = True
                        break # 跳出 for loop
                else:
                    self.last_tool_key = arg_key
                    self.consecutive_duplicates = 1 #  reset counter

                if is_duplicate:
                    break
                
                # 工具执行
                try:
                    handler = self.TOOL_HANDLERS.get(tool_name)
                    if handler:
                        output = handler(**args)
                        print(f"> {tool_name} executed: {output[:200]}")
                    else:
                        output = f"Unknown tool: {tool_name}"
                    results.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": str(output)
                    })
                except Exception as e:
                    error_msg = f"Runtime Error: {str(e)}"
                    results.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": f"Runtime Error: {str(e)}"
                    })
            
            if is_duplicate:
                self.enable_loop = False
                break
            messages.extend(results)
            step += 1
        
        if self.enable_loop and step > max_steps:
            print(f"\nWarning: reached max loop count ({max_steps}), task was forcibly stopped.")
        
        return "Session Ended"
