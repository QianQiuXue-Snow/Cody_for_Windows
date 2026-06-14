import re
import json

from agent.AgentCore import AgentCore

def singleton(cls):
    instances = {}
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    return get_instance

@singleton
class Agent(AgentCore):
    def __init__(self):
        super().__init__()
        
    def agent_loop(self, messages: list):
        self.last_tool_key = None     # 上一次的 (tool_name, args)组合
        self.consecutive_duplicates = 0
        self.rounds_since_todo = 0
        self.last_scanned_list_hash = None
        
        while True:
            
            try:
                response = self.client.chat.completions.create(
                    model=self.MODEL,
                    messages=[{"role": "system", "content": self.PROMOTE}] + messages,
                    tools=self.TOOLS,
                    max_tokens=8000,
                    tool_choice="auto",
                )
            except Exception as e:
                print(f"\033[31m API Error:\033[0m {e}")
                self.enable_loop = False
                return
            
            check_result = self.response_check(response, messages, False)
            if check_result is False:
                return ""
            elif check_result is not None:
                return check_result
            
            msg = response.choices[0].message
            if not msg.tool_calls:
                continue
            
            results = []
            used_todo = False
            is_duplicate = False
            for tool_call in msg.tool_calls:
                tool_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except:
                    args = {}
                    
                if self.check_duplicate_operation(tool_name, args):
                    is_duplicate = True
                    break
                
                # 工具执行
                try:
                    handler = self.TOOL_HANDLERS.get(tool_name)
                    if handler:
                        output = handler(**args)
                        print(f"\033[33m$> {tool_name}\033[0m executed: {output[:1000]}")
                    else:
                        output = f"\033[31m$ Unknown tool:\033[0m {tool_name}"
                    results.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": str(output)
                    })
                except Exception as e:
                    error_msg = f"\033[31m$ Runtime Error:\033[0m {str(e)}"
                    results.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": error_msg
                    })
                if tool_name == "todo":
                    used_todo = True
            self.rounds_since_todo = 0 if used_todo else self.rounds_since_todo + 1
            if self.rounds_since_todo >= 3:
                messages.append({
                    "role": "user",
                    "content": "<SYSTEM REMINDER> You have not updated your todo list in 3 rounds. Please update your tasks (status='pending', 'in_progress', 'completed') to track progress."
                })
                self.rounds_since_todo = 0
            
            if is_duplicate:
                # 注入停止提示
                messages.append({
                    "role": "user", 
                    "content": "WARNING: You attempted to scan the directory repeatedly. STOP SCANNING immediately. Start reading files or output analysis. Do not run 'dir' again."
                })
                print("\033[32m$ Agent stuck in loop, stopping. Warning injected.\033[0m")
                self.enable_loop = False
                return "STOPPED: Repeated command detected. Warning injected."
            
            if results:
                messages.extend(results)
                
        return "Session Ended"
