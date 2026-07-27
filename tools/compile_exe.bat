@echo off
setlocal

pushd "%~dp0.."
uv run --group dev pyinstaller --name FastCommandCenter --onefile --windowed --specpath build fastcommandcenter.py
popd
