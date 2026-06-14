# Cody_for_Windows
一个自制的简单ai agent

**[🇨🇳 中文说明](README.zh.md)** | **[English](README.md)**

## 简介

Cody 脱胎于极简 AI Agent 框架，并在此基础上逐步完善。其名称由 Code（代码）与 Candy（糖果）组合而成，寓意这是一款能让编程化繁为简、同时保持功能强大的辅助工具。

另一方面，Cody的名字来源于星球大战中的克隆人指挥官Cody，他在执行第66号令时炮击了Obi-Wan Kenobi。

## 构建与运行

请在 .env 文件中配置你的 API 密钥，或将其（OPENAI_API_KEY）设置为环境变量。

```cmd
# 创建运行环境
conda create -n Cody-py311 python=3.11 -y  
conda activate Cody-py311 

# 安装依赖库
pip install -r requirements.txt

# 运行工程
python main.py
```

## 版本日志

v 0.0.1: 最基础的 AI Agent 架构。支持自然语言对话及 CMD 命令调用。
️ 注意：目前仅包含基础的危险命令防护，未设置严格的权限限制，请谨慎使用。

v 0.0.2: 第一个稳定版本（至少已经能运行了）！增加了文件处理的基础工具。

v 0.1.0：
-- 新增工作流程管理：引入全新的工作流程安排与调度管理功能，提升任务执行效率。
-- 重构 AgentCore 架构：对 AgentCore 核心模块进行了全面重构，优化了底层实现逻辑。
-- 配置文件解耦：将设置文件从主程序中独立解耦，提升了配置的灵活性与可维护性。
-- 支持配置加密：新增设置文件加密的可选项，进一步增强敏感数据的安全性。

## 致谢

特别感谢 [**Learn Claude Code**](https://learn.shareai.run)。本项目是在该教程的指引下，通过逐步学习与迭代改良而最终完善的。
