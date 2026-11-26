"""Dependency-free structural validation for emitted USDA packages."""

from __future__ import annotations

import re
from pathlib import Path

from cityg.validation import ValidationReport


class UsdaPackageValidator:
    """Check syntax and composition assets before an official USD/physics runtime."""

    asset_pattern = re.compile(r"@([^@]+)@")
    default_prim_pattern = re.compile(r'defaultPrim\s*=\s*"([^"]+)"')

    def validate(self, root_layer: str | Path) -> ValidationReport:
        root = Path(root_layer)
        report = ValidationReport()
        if not root.is_file():
            report.add("error", "missing_usd_root", "Root USDA layer does not exist", str(root))
            return report

        visited: set[Path] = set()
        pending = [root.resolve()]
        reference_count = 0
        payload_count = 0
        instance_count = 0
        physics_scene_count = 0
        while pending:
            path = pending.pop()
            if path in visited:
                continue
            visited.add(path)
            text = path.read_text(encoding="utf-8")
            if not text.startswith("#usda 1.0"):
                report.add(
                    "error", "invalid_usda_header", "Layer must start with #usda 1.0", str(path)
                )
            self._balanced(text, path, report)
            match = self.default_prim_pattern.search(text)
            if not match or not re.search(
                rf'def\s+\w+\s+"{re.escape(match.group(1))}"', text
            ):
                report.add(
                    "error",
                    "invalid_default_prim",
                    "defaultPrim is missing or not defined in the layer",
                    str(path),
                )

            reference_count += text.count("prepend references")
            payload_count += text.count("prepend payload")
            instance_count += text.count("instanceable = true")
            physics_scene_count += len(re.findall(r'def\s+PhysicsScene\s+"', text))
            for asset in self.asset_pattern.findall(text):
                if asset.startswith("/"):
                    report.add(
                        "error",
                        "absolute_usd_asset_path",
                        "USD package must use relocatable relative asset paths",
                        str(path),
                    )
                    continue
                target = (path.parent / asset).resolve()
                if not target.is_file():
                    report.add(
                        "error",
                        "missing_usd_asset",
                        f"Referenced layer does not exist: {asset}",
                        str(path),
                    )
                elif target.suffix == ".usda":
                    pending.append(target)

        report.metrics = {
            "reachable_layer_count": len(visited),
            "reference_arc_count": reference_count,
            "payload_arc_count": payload_count,
            "instanceable_prim_count": instance_count,
            "physics_scene_count": physics_scene_count,
            "package_bytes": sum(path.stat().st_size for path in visited),
            "pxr_schema_validation": "not_run",
        }
        if payload_count == 0:
            report.add("error", "missing_payloads", "Package contains no payload arcs", str(root))
        if reference_count == 0:
            report.add("error", "missing_references", "Package contains no reference arcs", str(root))
        if instance_count == 0:
            report.add("error", "missing_instances", "Package contains no instanceable prims", str(root))
        if physics_scene_count != 1:
            report.add(
                "error",
                "invalid_physics_scene_count",
                f"Package must contain exactly one PhysicsScene, found {physics_scene_count}",
                str(root),
            )
        return report

    @staticmethod
    def _balanced(text: str, path: Path, report: ValidationReport) -> None:
        pairs = {"{": "}", "(": ")", "[": "]"}
        reverse = {value: key for key, value in pairs.items()}
        stack = []
        in_string = False
        escaped = False
        for char in text:
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char in pairs:
                stack.append(char)
            elif char in reverse:
                if not stack or stack.pop() != reverse[char]:
                    report.add(
                        "error", "unbalanced_usda", "Unbalanced USDA delimiters", str(path)
                    )
                    return
        if in_string or stack:
            report.add("error", "unbalanced_usda", "Unbalanced USDA delimiters", str(path))
