from __future__ import annotations

import os

import uvicorn


def main() -> None:
    port = int(os.environ.get("V8_API_PORT", "8765"))
    if not 1 <= port <= 65535:
        raise ValueError(f"V8_API_PORT 非法: {port}")
    uvicorn.run("api:app", host="127.0.0.1", port=port, reload=False)


if __name__ == "__main__":
    main()
