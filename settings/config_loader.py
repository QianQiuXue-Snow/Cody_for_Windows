import json
import os
import base64
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from dotenv import load_dotenv

# 模块加载时先尝试加载 .env
load_dotenv()

# ========== 加密相关函数 ==========
def _create_fernet(password: str, salt: bytes) -> Fernet:
    """使用密码和盐值创建Fernet加密器"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return Fernet(key)

def _decrypt_config(encrypted_file: str, password: str) -> dict:
    """解密配置文件"""
    if not os.path.exists(encrypted_file):
        raise FileNotFoundError(f"文件不存在: {encrypted_file}")
    
    with open(encrypted_file, 'rb') as f:
        content = f.read()
    
    parts = content.split(b'||')
    if len(parts) != 2:
        raise ValueError("加密文件格式错误")
    
    salt = parts[0]
    encrypted_data = parts[1]
    
    fernet = _create_fernet(password, salt)
    
    try:
        decrypted_data = fernet.decrypt(encrypted_data)
        return json.loads(decrypted_data.decode('utf-8'))
    except Exception as e:
        raise ValueError(f"解密失败，密码可能错误: {e}")

def _is_encrypted(file_path: str) -> bool:
    """
    检测文件是否已加密
    
    使用多种策略进行检测：
    1. 检查文件是否有加密特征头（salt|| 格式，salt为16字节）
    2. 检查文件是否以 { 开头（普通JSON）
    3. 尝试作为普通JSON解析，失败则可能是加密文件
    
    Args:
        file_path: 配置文件路径
    
    Returns:
        是否为加密文件
    """
    encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030']
    
    # 策略1: 检查加密特征（salt|| 开头，salt为16字节）
    try:
        with open(file_path, 'rb') as f:
            header = f.read(20)  # 读取足够长的头部来检测 salt||
            if b'||' in header:
                parts = header.split(b'||')
                if len(parts[0]) == 16:  # salt 固定为16字节
                    return True
    except Exception:
        pass
    
    # 策略2: 检查是否以 { 开头（普通JSON）
    try:
        with open(file_path, 'rb') as f:
            first_bytes = f.read(2)
            # JSON文件可能的开头形式: {"  或  {\n  或  { 
            if first_bytes in (b'{"', b'{\n', b'{ '):
                return False
    except Exception:
        pass
    
    # 策略3: 尝试作为普通JSON解析
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()  # 读取整个文件来判断
                json.loads(content if content else '{}')
                return False  # 成功解析为JSON，说明未加密
        except (json.JSONDecodeError, UnicodeDecodeError, IOError):
            continue
    
    # 所有策略都失败，极有可能是加密文件
    return True

# ========== ConfigLoader 类 ==========
class ConfigLoader:
    # 密码可以通过环境变量或配置文件指定
    _decrypt_password = os.environ.get('CONFIG_PASSWORD', '')
    
    @classmethod
    def set_password(cls, password: str):
        """设置解密密码"""
        cls._decrypt_password = password
    
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.raw_config = self._load_config()
        self._init_workdir()

    def _load_config(self):
        if not os.path.exists(self.config_path):
            print(f"Warning: {self.config_path} not found. Using defaults.")
            return self._get_defaults()
        
        try:
            # 检查是否为加密文件
            if _is_encrypted(self.config_path):
                if not self._decrypt_password:
                    raise ValueError("配置文件已加密，请设置密码: ConfigLoader.set_password('your_password')")
                return _decrypt_config(self.config_path, self._decrypt_password)
            
            # 普通JSON文件
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {self.config_path}: {e}")
            return self._get_defaults()
        except ValueError as e:
            print(f"Error: {e}")
            return self._get_defaults()

    def _get_defaults(self):
        return {
            "agent": {
                "workdir": ".",
                "model_name": "Qwen3-vl:8b",
                "system_prompt_template": "You are an agent at {WORKDIR}."
            },
            "llm": {"base_url": "http://localhost:11434/v1", "api_key": ""},
            "settings": {"markers": ["##TASK_COMPLETE##"], "enable_loop": True}
        }

    def _init_workdir(self):
        raw_path = self.raw_config.get("agent", {}).get("workdir", ".")
        if not os.path.isabs(raw_path):
            self.workdir = (Path.cwd() / raw_path).resolve()
        else:
            self.workdir = Path(raw_path).resolve()
            
    @property
    def tools(self):
        return self.raw_config.get("tools", [])

    @property
    def system_prompt(self) -> str:
        raw = self.raw_config.get("agent", {}).get("system_prompt_template", "")
        return raw.replace("{WORKDIR}", str(self.workdir))

    @property
    def markers(self):
        return self.raw_config.get("settings", {}).get("markers", ["##TASK_COMPLETE##"])

    @property
    def model_name(self):
        return self.raw_config["agent"]["model_name"]

    @property
    def api_key(self):
        return self.raw_config["llm"]["api_key"]

    @property
    def base_url(self):
        return self.raw_config["llm"]["base_url"]

    @property
    def enable_loop(self):
        return self.raw_config["settings"]["enable_loop"]


# 全局实例
config = ConfigLoader("settings/config.json")