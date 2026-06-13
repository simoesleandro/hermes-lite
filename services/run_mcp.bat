@echo off
REM Inicia o MCP server Hermes Lite (stdio — para Cursor / Claude Desktop)
cd /d "%~dp0.."
python mcp_server.py
