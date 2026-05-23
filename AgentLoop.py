import os
import json
import subprocess
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
        api_key = os.getenv("DEEPSEEK_API_KEY")
        
        self.client = OpenAI(
            base_url="https://api.deepseek.com",
            api_key=api_key
        )
        self.MODEL = "deepseek-v4-pro"
        self.SYSTEM = f"""You are a coding agent at {os.getcwd()} and your name is Cody. 
                    Use windows cmd to solve tasks. Act, don't explain.

                    ### Time & Location Context
                    <time_location>
                    Current Time: 2026-05-23 Saturday
                    Current Location: Shijiazhuang, Hebei
                    </time_location>
                    """
        self.TOOLS = [{
            "type": "function",
            "function": {
                "name": "cmd",
                "description": "Run a shell command.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "The shell command to execute"}
                    },
                    "required": ["command"],
                },
            },
        }]

    def run_cmd(self, command: str) -> str:
        dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
        if any(d in command for d in dangerous):
            return "Error: Dangerous command blocked"
        try:
            r = subprocess.run(command, shell=True, cwd=os.getcwd(),
                               capture_output=True, text=True, timeout=120)
            # 合并stdout和stderr防止命令混合输出导致解析混乱
            out = (r.stdout + r.stderr).strip()
            return out[:50000] if out else "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: Timeout (120s)"
        except Exception as e:
            return f"Error: {str(e)}"

    def agent_loop(self, messages: list):
        while True:
            try:
                response = self.client.chat.completions.create(
                    model=self.MODEL,
                    messages=[{"role": "system", "content": self.SYSTEM}] + messages,
                    tools=self.TOOLS,
                    max_tokens=8000,
                )
            except Exception as e:
                print(f"\033[31mAPI Error: {e}\033[0m")
                return

            msg = response.choices[0].message
            
            # 保存 assistant 消息时，必须同时保存 tool_calls
            assistant_msg = {
                "role": "assistant", 
                "content": msg.content
            }
            
            # 检查是否有工具调用# 如果之前有工具调用，将其存入 history 以匹配后续的 tool response
            if msg.tool_calls:
                assistant_msg["tool_calls"] = msg.tool_calls 
            messages.append(assistant_msg)
            
            # 如果没有工具调用，对话结束
            if not msg.tool_calls:
                return
            
            results = []
            for tool_call in msg.tool_calls:
                if tool_call.function.name == "bash":
                    try:
                        args = json.loads(tool_call.function.arguments)
                        cmd = args.get('command', '')
                        print(f"\033[33m$ {cmd}\033[0m")
                        output = self.run_bash(cmd)
                        print(output[:200])
                        results.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": output,
                        })
                    except json.JSONDecodeError:
                        results.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": "Error: Invalid JSON arguments"
                        })
            messages.extend(results)
