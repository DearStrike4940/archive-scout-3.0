from __future__ import annotations

import argparse
import importlib.metadata
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement

def normalize(name: str) -> str:
    return name.replace("_", "-").replace(".", "-").casefold()


def requirement_name(value: str) -> str | None:
    try:
        requirement = Requirement(value)
    except InvalidRequirement:
        return None
    if requirement.marker is not None and not requirement.marker.evaluate():
        return None
    return requirement.name


def dependency_closure(roots: list[str]) -> list[importlib.metadata.Distribution]:
    installed = {normalize(dist.metadata.get("Name", "")): dist for dist in importlib.metadata.distributions() if dist.metadata.get("Name")}
    pending = [normalize(name) for name in roots]
    visited: set[str] = set()
    result: list[importlib.metadata.Distribution] = []
    while pending:
        key = pending.pop(0)
        if key in visited:
            continue
        visited.add(key)
        dist = installed.get(key)
        if dist is None:
            continue
        result.append(dist)
        for raw in dist.requires or []:
            name = requirement_name(raw)
            if name and normalize(name) not in visited:
                pending.append(normalize(name))
    return sorted(result, key=lambda item: normalize(item.metadata.get("Name", "")))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--root", action="append", default=[])
    args = parser.parse_args()
    roots = args.root or ["truststore", "urllib3", "httpx"]
    packages = []
    relationships = []
    document_namespace = f"https://archive-scout.invalid/spdx/{args.version}/{uuid.uuid4()}"
    app_id = "SPDXRef-ArchiveScout"
    packages.append(
        {
            "SPDXID": app_id,
            "name": "Archive Scout 3.0",
            "versionInfo": args.version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "MIT",
            "supplier": "Organization: Archive Scout contributors",
        }
    )
    for index, dist in enumerate(dependency_closure(roots), start=1):
        name = dist.metadata.get("Name", "unknown")
        package_id = f"SPDXRef-Package-{index}"
        packages.append(
            {
                "SPDXID": package_id,
                "name": name,
                "versionInfo": dist.version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": dist.metadata.get("License") or "NOASSERTION",
                "supplier": "NOASSERTION",
            }
        )
        relationships.append({"spdxElementId": app_id, "relationshipType": "DEPENDS_ON", "relatedSpdxElement": package_id})
    payload = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"Archive Scout {args.version} Windows SBOM",
        "documentNamespace": document_namespace,
        "creationInfo": {
            "created": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "creators": ["Tool: Archive Scout generate_sbom.py"],
        },
        "packages": packages,
        "relationships": relationships,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
