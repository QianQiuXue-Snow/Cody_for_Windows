from dotenv import load_dotenv
from agent.Agent import Agent

# 尝试导入日志管理器
try:
    from utils.LogManager import logger
except ImportError:
    logger = None

if __name__ == "__main__":
    load_dotenv(override=True)
    
    history = []
    ac = Agent()
    
    print("\033[32m=== Agent 已启动，输入 q/exit 退出 ===\033[0m")
    
    while True:
        try:
            query = input("\033[36mCody v0.1.1 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            print("\n\033[33m检测到退出信号，正在终止...\033[0m")
            break
        
        if query.strip().lower() in ("q", "exit", ""):
            print("\033[33m正在退出...\033[0m")
            break
        
        if not query.strip():
            continue
            
        history.append({"role": "user", "content": query})
        
        try:
            ac.agent_loop(history)
        except Exception as e:
            print(f"\033[31m执行错误：{e}\033[0m")
            continue
        
        # 提取并打印最后一条助手回复
        if history:
            last_msg = history[-1]
            if last_msg.get("role") == "assistant":
                response_content = last_msg.get("content", "")
                if isinstance(response_content, list):
                    for block in response_content:
                        if hasattr(block, "text"):
                            print(block.text)
                        elif isinstance(block, dict) and block.get("type") == "text":
                            print(block.get("text", ""))
                elif isinstance(response_content, str):
                    print(response_content)
    
    # 打印会话摘要
    if logger:
        logger.print_summary()
        logger.save_metrics()
    
    print("\033[32m=== 会话结束 ===\033[0m")
    