import subprocess
import os

task_name = "PriceETLPipeline"

python_path = r"C:\Users\User\PycharmProjects\parse_sales\venv\Scripts\python.exe"
script_path = r"C:\Users\User\PycharmProjects\parse_sales\etl\run_pipeline.py"

command = [
    "schtasks",
    "/create",
    "/sc", "daily",
    "/st", "11:00",
    "/tn", task_name,
    "/tr", f'{python_path} {script_path}',
    "/f",
    "/rl", "HIGHEST"
]

subprocess.run(command)
