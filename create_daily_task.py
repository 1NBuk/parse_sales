import subprocess
import os

task_name = "PriceETLPipeline"

python_path = r"C:\Users\User\PycharmProjects\parse_sales\venv\Scripts\python.exe"
script_path = r"C:\Users\User\PycharmProjects\parse_sales\etl\run_pipeline.py"

command = [
    "schtasks",
    "/create",
    "/sc", "daily",
    "/st", "14:33",
    "/tn", task_name,
    "/tr", f'cmd /c "{python_path} {script_path}"',
    "/ru", os.getlogin(),
    "/f"
]

result = subprocess.run(command, capture_output=True, text=True, shell=True)

print(result.stdout)
print(result.stderr)