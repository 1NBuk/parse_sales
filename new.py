import os

total_lines = 0

for root, _, files in os.walk("."):
    for file in files:
        if file.endswith(".py"):
            with open(os.path.join(root, file), "r", encoding="utf-8", errors="ignore") as f:
                total_lines += len(f.readlines())

print("Total lines:", total_lines)