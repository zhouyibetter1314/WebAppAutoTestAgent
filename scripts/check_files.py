"""Small offline staged-file checks; never scan third-party submodule sources."""

import re
import sys
from pathlib import Path

failed = False
for name in sys.argv[1:]:
    path = Path(name)
    if not path.is_file() or name.startswith(
        ("targets/4gaboards/", "targets/admidio/", "targets/discourse/")
    ):
        continue
    raw = path.read_bytes()
    if b"\0" in raw:
        continue
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        continue
    issues = []
    if re.search(r"^(<<<<<<< |=======\s*$|>>>>>>> )", text, re.M):
        issues.append("合并冲突标记")
    if re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bsk-[A-Za-z0-9]{24,}", text):
        issues.append("疑似密钥")
    if raw and not raw.endswith(b"\n"):
        issues.append("缺少文件末尾换行")
    if any(line.rstrip(" \t") != line for line in text.splitlines()):
        issues.append("行尾空白")
    if issues:
        print(f"{name}: {', '.join(issues)}")
        failed = True
raise SystemExit(1 if failed else 0)
