import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
versions = json.loads((root / "targets/versions.json").read_text())
for name, spec in versions.items():
    actual = subprocess.check_output(
        ["git", "-C", str(root / "targets" / name), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual != spec["commit"]:
        raise SystemExit(f"{name}: 版本不匹配 {actual}")
    print(f"{name}: {actual}")
