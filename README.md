# Cody_for_Windows
A lightweight, self-made AI agent.

**[🇨🇳 中文说明](README.zh.md)** | **[English](README.md)**

## Introduction

Cody evolved from a minimalist AI agent framework. Its name is a portmanteau of **Code** + **Candy**, representing a programming assistant that simplifies complexity while delivering full functionality.

On the other hand, "Cody" is also a tribute to **Clone Commander Cody** from *Star Wars*, who famously executed Order 66 against Obi-Wan Kenobi.

## Build & Run

Please configure your API key in a .env file or set OPENAI_API_KEY as a environment variable.

```cmd
# Create the runtime environment
conda create -n Cody-py311 python=3.11 -y  
conda activate Cody-py311 

# Install dependencies
pip install -r requirements.txt

# Run the project
python main.py
```

## Version Log

v 0.0.1: The foundational AI Agent structure. Capable of conversation and executing CMD commands.
⚠️ Note: Currently includes only basic protection against dangerous commands with no strict permission limits. Use with caution.

v 0.0.2: The first stable version! At least it could be used. File tools added in this version.

v 0.1.0:
-- Workflow Scheduling Management: Introduced a new workflow arrangement and scheduling management feature to enhance task execution efficiency.
-- AgentCore Refactoring: Completely refactored the AgentCore module to optimize the underlying implementation logic.
-- Configuration Decoupling: Decoupled the configuration files from the main program, improving flexibility and maintainability.
-- Optional Config Encryption: Added an optional encryption feature for configuration files to further enhance the security of sensitive data.

v 0.1.1
-- Introduced sub-agent task scheduling to support complex multi-task orchestration.
-- Enhanced continuous logging mechanism and added log rollback capabilities for better traceability.

## Acknowledgments、

Special thanks to [**Learn Claude Code**]((https://learn.shareai.run)). This project was developed and refined through step-by-step learning based on their tutorial.