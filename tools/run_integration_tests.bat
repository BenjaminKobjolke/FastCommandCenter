@echo off
set QT_QPA_PLATFORM=offscreen
uv run pytest tests\integration -v
pause
