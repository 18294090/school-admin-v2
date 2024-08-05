@echo off
REM 激活虚拟环境
call .\venv\Scripts\activate

REM 启动Flask应用
flask --app main run --host="0.0.0.0" --port="5000" --debug

REM 保持命令提示符窗口打开
pause