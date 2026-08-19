"""Load local env files without asking a shell to parse secret values."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from dotenv import dotenv_values


VALID_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SECRET_FILES = ("st_invest_quant.env", "v8_copilot.env")


def secret_environment(data_root: Path) -> dict[str, str]:
    environment = dict(os.environ)
    for name in SECRET_FILES:
        path = data_root / "local_secrets" / name
        if not path.is_file():
            continue
        values = dotenv_values(path, interpolate=False)
        invalid = [str(key) for key in values if key is None or not VALID_NAME.fullmatch(str(key))]
        if invalid:
            raise ValueError(f"secrets 文件含非法变量名: {path}: {', '.join(invalid)}")
        for key, value in values.items():
            if value is not None:
                environment[str(key)] = str(value)
    return environment


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: with_secrets.py PYTHON_SCRIPT [ARGS...]", file=sys.stderr)
        return 2
    data_root = Path(os.environ.get("V8_DATA_ROOT", Path(__file__).resolve().parents[2]))
    script = Path(sys.argv[1])
    if not script.is_absolute():
        script = Path.cwd() / script
    if not script.is_file():
        print(f"Python entry point does not exist: {script}", file=sys.stderr)
        return 2
    try:
        environment = secret_environment(data_root)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    os.execve(sys.executable, [sys.executable, str(script), *sys.argv[2:]], environment)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
