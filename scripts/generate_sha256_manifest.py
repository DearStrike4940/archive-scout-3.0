from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("output")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = Path(args.output).resolve()
    rows = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.resolve() == output:
            continue
        rows.append(f"{sha256(path)}  {path.relative_to(root).as_posix()}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="ascii")


if __name__ == "__main__":
    main()
