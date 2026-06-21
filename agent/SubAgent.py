import re
import json
import time

from agent.AgentCore import AgentCore

class SubAgent(AgentCore):
    def __init__(self):
        super().__init__(agent_type="SubAgent")
        self.PROMOTE = self.config.subagent_system_prompt
        self._logger = None
        
    @property
    def logger(self):
        if self._logger is None:
            try:
                from utils.LogManager import logger
                self._logger = logger
            except ImportError:
                pass
        return self._logger

    def run_subagent(self, prompt: str) -> str:
        sub_messages = [{"role": "system", "content": prompt}]
        for _ in range(30):
            try:
                start_time = time.time()
                response = self.client.chat.completions.create(
                    model=self.MODEL,
                    messages=[{"role": "system", "content": self.PROMOTE}] + sub_messages,
                    tools=self.TOOLS,
                    max_tokens=8000,
                    tool_choice="auto",
                )
                response_time = time.time() - start_time
                
                # 记录SubAgent API调用指标
                if self.logger:
                    try:
                        usage = response.usage
                        input_tokens = usage.prompt_tokens if usage else 0
                        output_tokens = usage.completion_tokens if usage else 0
                        self.logger.record_request(
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            response_time=response_time,
                            agent_type="SubAgent"
                        )
                    except:
                        self.logger.record_request(
                            input_tokens=0,
                            output_tokens=0,
                            response_time=response_time,
                            agent_type="SubAgent"
                        )
            except Exception as e:
                print(f"\033[31m SubAgent API Error:\033[0m {e}")
                self.enable_loop = False
                return
            
            check_result = self.response_check(response, sub_messages, True)
            if check_result is False:
                return ""
            elif check_result is not None:
                return check_result
            
            sub_msg = response.choices[0].message
            if not sub_msg.tool_calls:
                continue
            
            results = []
            used_todo = False
            is_duplicate = False
            for tool_call in sub_msg.tool_calls:
                tool_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except:
                    args = {}
                
                if self.check_duplicate_operation(tool_name, args):
                    is_duplicate = True
                    results.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": "Operation skipped: duplicate detected to prevent infinite loop"
                    })
                    continue
                
                try:
                    handler = self.TOOL_HANDLERS.get(tool_name)
                    if handler:
                        output = handler(**args)
                        print(f"\033[33m$> {tool_name}\033[0m executed: {output[:200]}")
                    else:
                        output = f"\033[31m$ Unknown tool:\033[0m {tool_name}"
                    results.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": str(output)[:5000]
                    })
                except Exception as e:
                    error_msg = f"\033[31m$ Runtime Error:\033[0m {str(e)}"
                    results.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": error_msg
                    })
            if results:
                sub_messages.extend(results)
        
        # 处理返回值
        if response.content:
            if isinstance(response.content, list):
                return "".join(b.text for b in response.content if hasattr(b, "text")) or "(no summary)"
            else:
                return str(response.content) if response.content else "(no summary)"
        else:
            return "(no summary)"