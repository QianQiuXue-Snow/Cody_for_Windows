"""
回滚日志管理器 (Rollback Logger)
用于记录文件操作，以便在Agent异常退出时能够回滚操作

功能：
1. 自动记录写/编辑文件操作前的原始状态
2. 存储操作日志到指定目录
3. 支持手动回滚到上一个状态
4. 支持列出可回滚的操作历史
"""

import os
import json
import shutil
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from threading import Lock


class RollbackLogger:
    """回滚日志管理器"""
    
    def __init__(self, log_dir: str = None):
        """
        初始化回滚日志管理器
        
        Args:
            log_dir: 日志存储目录，默认为 logs/rollback
        """
        if log_dir is None:
            # 默认使用工程下的 logs/rollback 目录
            # 使用当前工作目录作为基础
            base_dir = Path.cwd()
            # 检查是否存在 utils 目录，如果存在则使用其父目录
            if (base_dir / 'utils').exists():
                base_dir = base_dir
            log_dir = base_dir / "logs" / "rollback"
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 当前会话的日志文件
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_log_file = self.log_dir / f"session_{self.session_id}.json"
        
        # 操作记录列表
        self.operations: List[Dict[str, Any]] = []
        
        # 线程锁
        self._lock = Lock()
        
        # 是否启用记录
        self.enabled = True
        
        # 初始化日志文件
        self._init_log_file()
    
    def _init_log_file(self):
        """初始化日志文件"""
        initial_data = {
            "session_id": self.session_id,
            "created_at": datetime.now().isoformat(),
            "operations": []
        }
        try:
            with open(self.session_log_file, 'w', encoding='utf-8') as f:
                json.dump(initial_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[RollbackLogger] Failed to init log file: {e}")
    
    def _save_log(self):
        """保存日志到文件"""
        if not self.enabled:
            return
        
        try:
            data = {
                "session_id": self.session_id,
                "created_at": datetime.now().isoformat(),
                "operations": self.operations
            }
            with open(self.session_log_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[RollbackLogger] Failed to save log: {e}")
    
    def record_write(self, file_path: str, content: str) -> Optional[str]:
        """
        记录写文件操作
        
        Args:
            file_path: 文件路径
            content: 要写入的内容
            
        Returns:
            操作ID，用于回滚
        """
        if not self.enabled:
            return None
        
        with self._lock:
            try:
                fp = Path(file_path)
                
                # 检查文件是否存在
                backup_content = None
                if fp.exists():
                    try:
                        backup_content = fp.read_text(encoding='utf-8')
                    except:
                        try:
                            backup_content = fp.read_text(encoding='gbk', errors='replace')
                        except Exception as e:
                            print(f"[RollbackLogger] Failed to read original file: {e}")
                
                op_id = f"write_{len(self.operations) + 1}_{int(time.time())}"
                
                operation = {
                    "id": op_id,
                    "type": "write",
                    "file_path": str(fp.absolute()),
                    "timestamp": datetime.now().isoformat(),
                    "backup_content": backup_content,
                    "new_content": content,
                    "status": "pending"
                }
                
                self.operations.append(operation)
                self._save_log()
                
                return op_id
            except Exception as e:
                print(f"[RollbackLogger] Failed to record write operation: {e}")
                return None
    
    def record_edit(self, file_path: str, old_text: str, new_text: str) -> Optional[str]:
        """
        记录编辑文件操作
        
        Args:
            file_path: 文件路径
            old_text: 要替换的旧内容
            new_text: 要替换成的新内容
            
        Returns:
            操作ID，用于回滚
        """
        if not self.enabled:
            return None
        
        with self._lock:
            try:
                fp = Path(file_path)
                
                # 读取原始文件内容作为备份
                backup_content = None
                if fp.exists():
                    try:
                        backup_content = fp.read_text(encoding='utf-8')
                    except:
                        try:
                            backup_content = fp.read_text(encoding='gbk', errors='replace')
                        except Exception as e:
                            print(f"[RollbackLogger] Failed to read original file: {e}")
                
                op_id = f"edit_{len(self.operations) + 1}_{int(time.time())}"
                
                operation = {
                    "id": op_id,
                    "type": "edit",
                    "file_path": str(fp.absolute()),
                    "timestamp": datetime.now().isoformat(),
                    "backup_content": backup_content,
                    "old_text": old_text,
                    "new_text": new_text,
                    "status": "pending"
                }
                
                self.operations.append(operation)
                self._save_log()
                
                return op_id
            except Exception as e:
                print(f"[RollbackLogger] Failed to record edit operation: {e}")
                return None
    
    def record_bash(self, command: str, affected_files: List[str] = None) -> Optional[str]:
        """
        记录bash命令操作（可能影响文件）
        
        Args:
            command: 执行的命令
            affected_files: 受影响的文件路径列表
            
        Returns:
            操作ID，用于回滚
        """
        if not self.enabled:
            return None
        
        # 只记录可能影响文件的危险命令
        dangerous_patterns = ['del ', 'rm ', 'rd ', 'move ', 'copy ', '>', '>>']
        if not any(p in command.lower() for p in dangerous_patterns):
            return None
        
        with self._lock:
            try:
                # 备份受影响的文件
                backups = {}
                if affected_files:
                    for fpath in affected_files:
                        fp = Path(fpath)
                        if fp.exists():
                            try:
                                backups[str(fp.absolute())] = fp.read_text(encoding='utf-8')
                            except:
                                try:
                                    backups[str(fp.absolute())] = fp.read_text(encoding='gbk', errors='replace')
                                except:
                                    pass
                
                op_id = f"bash_{len(self.operations) + 1}_{int(time.time())}"
                
                operation = {
                    "id": op_id,
                    "type": "bash",
                    "command": command,
                    "timestamp": datetime.now().isoformat(),
                    "affected_files": affected_files or [],
                    "backups": backups,
                    "status": "pending"
                }
                
                self.operations.append(operation)
                self._save_log()
                
                return op_id
            except Exception as e:
                print(f"[RollbackLogger] Failed to record bash operation: {e}")
                return None
    
    def commit_operation(self, op_id: str):
        """
        标记操作已成功提交
        
        Args:
            op_id: 操作ID
        """
        with self._lock:
            for op in self.operations:
                if op["id"] == op_id:
                    op["status"] = "committed"
                    self._save_log()
                    break
    
    def rollback_last(self) -> Dict[str, Any]:
        """
        回滚最后一个操作
        
        Returns:
            回滚结果信息
        """
        with self._lock:
            if not self.operations:
                return {"success": False, "message": "No operations to rollback"}
            
            # 找到最后一个未回滚的操作
            for op in reversed(self.operations):
                if op["status"] != "rolled_back":
                    return self._rollback_operation(op)
            
            return {"success": False, "message": "All operations already rolled back"}
    
    def _rollback_operation(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行单个回滚操作
        
        Args:
            operation: 操作记录
            
        Returns:
            回滚结果
        """
        try:
            op_type = operation["type"]
            file_path = operation.get("file_path")
            
            if op_type == "write":
                # 回滚写操作：恢复原始内容或删除文件
                if operation.get("backup_content") is not None:
                    # 恢复原始内容
                    fp = Path(file_path)
                    fp.write_text(operation["backup_content"], encoding='utf-8')
                    message = f"Restored file: {file_path}"
                else:
                    # 文件原本不存在，删除新创建的文件
                    fp = Path(file_path)
                    if fp.exists():
                        fp.unlink()
                    message = f"Deleted new file: {file_path}"
                
                operation["status"] = "rolled_back"
                self._save_log()
                return {"success": True, "message": message}
            
            elif op_type == "edit":
                # 回滚编辑操作：恢复原始内容
                if operation.get("backup_content") is not None:
                    fp = Path(file_path)
                    fp.write_text(operation["backup_content"], encoding='utf-8')
                    message = f"Restored original content: {file_path}"
                else:
                    message = f"Original content not available: {file_path}"
                
                operation["status"] = "rolled_back"
                self._save_log()
                return {"success": True, "message": message}
            
            elif op_type == "bash":
                # 回滚bash操作：恢复所有受影响的文件
                backups = operation.get("backups", {})
                messages = []
                for fpath, content in backups.items():
                    fp = Path(fpath)
                    fp.write_text(content, encoding='utf-8')
                    messages.append(f"Restored: {fpath}")
                
                operation["status"] = "rolled_back"
                self._save_log()
                return {"success": True, "message": "; ".join(messages) if messages else "No files to restore"}
            
            return {"success": False, "message": f"Unknown operation type: {op_type}"}
            
        except Exception as e:
            return {"success": False, "message": f"Rollback failed: {str(e)}"}
    
    def rollback_all(self) -> Dict[str, Any]:
        """
        回滚所有操作
        
        Returns:
            回滚结果信息
        """
        results = []
        with self._lock:
            # 倒序回滚所有操作
            for op in reversed(self.operations):
                if op["status"] != "rolled_back":
                    result = self._rollback_operation(op)
                    results.append(result)
        
        return {
            "success": True,
            "message": f"Rolled back {len([r for r in results if r['success']])} operations",
            "details": results
        }
    
    def list_operations(self) -> List[Dict[str, Any]]:
        """
        列出所有操作记录
        
        Returns:
            操作记录列表
        """
        return [
            {
                "id": op["id"],
                "type": op["type"],
                "file_path": op.get("file_path", op.get("command", "N/A")),
                "timestamp": op["timestamp"],
                "status": op["status"]
            }
            for op in self.operations
        ]
    
    def get_session_log_path(self) -> str:
        """
        获取当前会话的日志文件路径
        
        Returns:
            日志文件路径
        """
        return str(self.session_log_file)
    
    def disable(self):
        """禁用回滚日志记录"""
        self.enabled = False
    
    def enable(self):
        """启用回滚日志记录"""
        self.enabled = True
    
    def clear_history(self):
        """清除当前会话的操作历史"""
        with self._lock:
            self.operations = []
            self._save_log()


# 全局单例实例
_rollback_logger: Optional[RollbackLogger] = None


def get_rollback_logger() -> RollbackLogger:
    """
    获取回滚日志管理器的全局实例
    
    Returns:
        RollbackLogger实例
    """
    global _rollback_logger
    if _rollback_logger is None:
        _rollback_logger = RollbackLogger()
    return _rollback_logger


def rollback_last() -> Dict[str, Any]:
    """快捷函数：回滚最后一个操作"""
    return get_rollback_logger().rollback_last()


def rollback_all() -> Dict[str, Any]:
    """快捷函数：回滚所有操作"""
    return get_rollback_logger().rollback_all()


def list_operations() -> List[Dict[str, Any]]:
    """快捷函数：列出所有操作"""
    return get_rollback_logger().list_operations()