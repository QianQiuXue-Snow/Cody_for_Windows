import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

class LogManager:
    """日志管理器 - 统一管理日志输出和监控指标"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, log_dir: str = "logs", log_level: str = "INFO"):
        # 避免重复初始化
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_level = getattr(__import__('logging'), log_level, None)
        self._log_level_str = log_level
        
        # 监控指标
        self.metrics = {
            "total_requests": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_response_time": 0.0,
            "total_errors": 0,
            "session_start": datetime.now().isoformat(),
            "sessions": []
        }
        
        # 当前会话指标
        self.current_session = {
            "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "response_times": [],
            "errors": 0,
            "start_time": time.time()
        }
        
        # 日志文件
        self.log_file = self.log_dir / f"agent_{datetime.now().strftime('%Y%m%d')}.log"
        self.metrics_file = self.log_dir / "metrics.json"
        
        self._initialized = True
        
        # 初始化日志
        self.info("LogManager initialized")
    
    def _get_log_level_value(self) -> int:
        levels = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}
        return levels.get(self._log_level_str, 20)
    
    def _format_log(self, level: str, message: str, extra: dict = None) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] [{level:8}] {message}"
        
        if extra:
            extra_str = " | ".join(f"{k}={v}" for k, v in extra.items())
            log_entry += f" | {extra_str}"
        
        return log_entry
    
    def _write_log(self, level: str, message: str, extra: dict = None):
        """写入日志文件（仅文件，不打印到控制台）"""
        log_entry = self._format_log(level, message, extra)
        
        # 只写入文件，不打印到控制台
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_entry + "\n")
        except Exception as e:
            # 写入失败时静默处理
            pass
    
    def debug(self, message: str, **kwargs):
        self._write_log("DEBUG", message, kwargs if kwargs else None)
    
    def info(self, message: str, **kwargs):
        self._write_log("INFO", message, kwargs if kwargs else None)
    
    def warning(self, message: str, **kwargs):
        self._write_log("WARNING", message, kwargs if kwargs else None)
    
    def error(self, message: str, **kwargs):
        self._write_log("ERROR", message, kwargs if kwargs else None)
        self.metrics["total_errors"] += 1
        self.current_session["errors"] += 1
    
    # ==================== 监控指标 ====================
    
    def record_request(self, 
                       input_tokens: int = 0, 
                       output_tokens: int = 0, 
                       response_time: float = 0.0,
                       agent_type: str = "Agent",
                       tool_name: str = None):
        """记录一次API请求的指标"""
        
        self.metrics["total_requests"] += 1
        self.metrics["total_input_tokens"] += input_tokens
        self.metrics["total_output_tokens"] += output_tokens
        self.metrics["total_response_time"] += response_time
        
        self.current_session["requests"] += 1
        self.current_session["input_tokens"] += input_tokens
        self.current_session["output_tokens"] += output_tokens
        self.current_session["response_times"].append(response_time)
        
        # 详细日志
        extra = {
            "agent": agent_type,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "response_time": f"{response_time:.2f}s"
        }
        if tool_name:
            extra["tool"] = tool_name
            
        self.info(f"API Request completed", **extra)
    
    def record_tool_execution(self, tool_name: str, duration: float, success: bool = True):
        """记录工具执行情况"""
        status = "SUCCESS" if success else "FAILED"
        self.info(f"Tool execution: {tool_name}", 
                  tool=tool_name, 
                  duration=f"{duration:.3f}s", 
                  status=status)
    
    def get_usage_summary(self) -> Dict:
        """获取当前使用量摘要"""
        total_tokens = self.metrics["total_input_tokens"] + self.metrics["total_output_tokens"]
        avg_response_time = (
            self.metrics["total_response_time"] / self.metrics["total_requests"] 
            if self.metrics["total_requests"] > 0 else 0
        )
        
        return {
            "total_requests": self.metrics["total_requests"],
            "total_input_tokens": self.metrics["total_input_tokens"],
            "total_output_tokens": self.metrics["total_output_tokens"],
            "total_tokens": total_tokens,
            "average_response_time": f"{avg_response_time:.2f}s",
            "total_errors": self.metrics["total_errors"]
        }
    
    def get_session_summary(self) -> Dict:
        """获取当前会话摘要"""
        session_time = time.time() - self.current_session["start_time"]
        total_tokens = (self.current_session["input_tokens"] + 
                       self.current_session["output_tokens"])
        avg_response_time = (
            sum(self.current_session["response_times"]) / 
            len(self.current_session["response_times"])
            if self.current_session["response_times"] else 0
        )
        
        return {
            "session_id": self.current_session["session_id"],
            "duration": f"{session_time:.1f}s",
            "requests": self.current_session["requests"],
            "input_tokens": self.current_session["input_tokens"],
            "output_tokens": self.current_session["output_tokens"],
            "total_tokens": total_tokens,
            "avg_response_time": f"{avg_response_time:.2f}s",
            "errors": self.current_session["errors"]
        }
    
    def save_metrics(self):
        """保存指标到文件"""
        # 更新会话历史
        self.metrics["sessions"].append({
            "session_id": self.current_session["session_id"],
            "requests": self.current_session["requests"],
            "input_tokens": self.current_session["input_tokens"],
            "output_tokens": self.current_session["output_tokens"],
            "errors": self.current_session["errors"],
            "start_time": datetime.fromtimestamp(
                self.current_session["start_time"]
            ).isoformat()
        })
        
        try:
            with open(self.metrics_file, "w", encoding="utf-8") as f:
                json.dump(self.metrics, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.error(f"Failed to save metrics: {e}")
    
    def print_summary(self):
        """打印使用摘要"""
        session = self.get_session_summary()
        
        print("\n" + "="*50)
        print("Session Summary")
        print("="*50)
        print(f"  Session ID: {session['session_id']}")
        print(f"  Duration:   {session['duration']}")
        print(f"  Requests:   {session['requests']}")
        print(f"  Input:      {session['input_tokens']} tokens")
        print(f"  Output:     {session['output_tokens']} tokens")
        print(f"  Total:      {session['total_tokens']} tokens")
        print(f"  Avg Time:   {session['avg_response_time']}")
        print(f"  Errors:     {session['errors']}")
        print("="*50 + "\n")
    
    def reset_session(self):
        """重置会话统计"""
        self.current_session = {
            "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "response_times": [],
            "errors": 0,
            "start_time": time.time()
        }
        self.info("Session metrics reset")


# 全局实例
logger = LogManager()