"""
配置文件加密工具
使用 cryptography 库的 Fernet 对称加密
"""
import json
import base64
import os
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

# 加密文件后缀
ENCRYPTED_EXT = ".enc"
CONFIG_FILE = "config.json"

def generate_key(password: str, salt: bytes = None) -> bytes:
    """
    使用密码生成加密密钥
    
    Args:
        password: 用户密码
        salt: 盐值(如果为None则自动生成)
    
    Returns:
        Fernet密钥(可用于加密解密)
    """
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key, salt

def create_fernet_key(password: str, salt: bytes = None) -> Fernet:
    """
    创建 Fernet 加密器
    
    Args:
        password: 用户密码
        salt: 盐值
    
    Returns:
        Fernet 加密器对象
    """
    key, _ = generate_key(password, salt)
    return Fernet(key)

def encrypt_config(input_file: str, output_file: str, password: str, salt: bytes = None):
    """
    加密配置文件
    
    Args:
        input_file: 输入的明文配置文件路径
        output_file: 输出的加密文件路径
        password: 加密密码
        salt: 盐值(可选)
    """
    if salt is None:
        salt = os.urandom(16)
    
    # 读取原始配置
    with open(input_file, 'r', encoding='utf-8') as f:
        config_data = f.read()
    
    # 创建加密器
    fernet = create_fernet_key(password, salt)
    
    # 加密数据
    encrypted_data = fernet.encrypt(config_data.encode())
    
    # 将盐值和加密数据一起保存
    with open(output_file, 'wb') as f:
        f.write(salt)
        f.write(b'||')
        f.write(encrypted_data)
    
    print(f"加密成功: {input_file} -> {output_file}")

def decrypt_config(encrypted_file: str, password: str) -> dict:
    """
    解密配置文件
    
    Args:
        encrypted_file: 加密文件路径
        password: 解密密码
    
    Returns:
        解密后的配置字典
    """
    if not os.path.exists(encrypted_file):
        raise FileNotFoundError(f"文件不存在: {encrypted_file}")
    
    # 读取加密文件
    with open(encrypted_file, 'rb') as f:
        content = f.read()
    
    # 分离盐值和加密数据
    parts = content.split(b'||')
    if len(parts) != 2:
        raise ValueError("加密文件格式错误")
    
    salt = parts[0]
    encrypted_data = parts[1]
    
    # 创建解密器
    fernet = create_fernet_key(password, salt)
    
    # 解密数据
    try:
        decrypted_data = fernet.decrypt(encrypted_data)
        return json.loads(decrypted_data.decode('utf-8'))
    except Exception as e:
        raise ValueError(f"解密失败，密码可能错误: {e}")

def encrypt_json_file(input_file: str, password: str, salt: bytes = None):
    """
    直接加密JSON文件（原地加密）
    
    Args:
        input_file: 要加密的文件路径
        password: 密码
        salt: 盐值
    """
    if salt is None:
        salt = os.urandom(16)
    
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'ansi', 'cp1252']
    
    # 读取原始配置
    for encoding in encodings:
        try:
            with open(input_file, 'r', encoding=encoding) as f:
                config_data = f.read()
            break
        except UnicodeDecodeError:
            continue
    
    # 创建加密器
    fernet = create_fernet_key(password, salt)
    
    # 加密数据
    encrypted_data = fernet.encrypt(config_data.encode())
    
    # 备份原文件
    backup_file = input_file + ".bak"
    with open(backup_file, 'wb') as f:
        f.write(config_data.encode())
    print(f"已备份原文件到: {backup_file}")
    
    # 写入加密数据
    with open(input_file, 'wb') as f:
        f.write(salt)
        f.write(b'||')
        f.write(encrypted_data)

def is_encrypted_file(file_path: str) -> bool:
    """
    检测文件是否已加密
    
    Args:
        file_path: 文件路径
    
    Returns:
        是否为加密文件
    """
    try:
        with open(file_path, 'rb') as f:
            content = f.read(2)
            return content != b'{'  # JSON文件以 { 开头，加密后不是
    except:
        return False

# ========== 命令行工具 ==========
if __name__ == "__main__":
    if 0:
        import sys
        
        if len(sys.argv) < 2:
            print("用法:")
            print("  python config_crypto.py encrypt <input_file> <output_file> <password>")
            print("  python config_crypto.py decrypt <encrypted_file> <password>")
            sys.exit(1)
        
        command = sys.argv[1]
        
        if command == "encrypt":
            if len(sys.argv) != 5:
                print("错误: 需要指定输入文件、输出文件和密码")
                sys.exit(1)
            encrypt_config(sys.argv[2], sys.argv[3], sys.argv[4])
        
        elif command == "decrypt":
            if len(sys.argv) != 4:
                print("错误: 需要指定加密文件和密码")
                sys.exit(1)
            result = decrypt_config(sys.argv[2], sys.argv[3])
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        else:
            print(f"未知命令: {command}")
            sys.exit(1)
    else:
        current_dir = Path(__file__).parent
        config_path = current_dir / "config.json"
        encrypt_json_file(str(config_path), "123456")