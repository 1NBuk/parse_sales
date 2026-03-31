import subprocess
import os


task_name = "PriceETLPipeline"

python_path = r"C:\Users\User\PycharmProjects\parse_sales\venv\Scripts\python.exe"
script_path = r"C:\Users\User\PycharmProjects\parse_sales\etl\run_pipeline.py"

run_command = f'"{python_path}" "{script_path}"'

daily = [
    "schtasks",
    "/create",
    "/tn", task_name,
    "/tr", run_command,
    "/sc", "daily",
    "/st", "12:00",
    "/ru", os.getlogin(),
    "/f"
]

startup = [
    "schtasks",
    "/create",
    "/tn", task_name + "_startup",
    "/tr", run_command,
    "/sc", "onstart",
    "/ru", os.getlogin(),
    "/f"
]

subprocess.run(daily, shell=True)
subprocess.run(startup, shell=True)

print("Tasks created successfully")