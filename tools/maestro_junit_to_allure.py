#!/usr/bin/env python3
"""Convert a Maestro JUnit XML report into Allure result files.

Maestro has no native Allure output, so the reporting pipeline is:
    maestro test --format JUNIT --output report.xml Maestro/flows
    python tools/maestro_junit_to_allure.py --junit report.xml --out allure-results
    allure generate allure-results -o allure-report   # or: allure serve allure-results

Stdlib only -- no third-party dependencies.

Example:
    python tools/maestro_junit_to_allure.py \\
        --junit report.xml \\
        --out allure-results \\
        --screenshots ~/.maestro/tests \\
        --env "device=pixel_6 (API 33)" \\
        --env "branch=main"
"""

import argparse
import hashlib
import json
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


def parse_time(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_timestamp(value):
    """Return epoch millis for an ISO timestamp, or None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return None


def status_of(case):
    """Map JUnit testcase children to an Allure status."""
    if case.find("skipped") is not None:
        return "skipped", None
    failure = case.find("failure")
    if failure is not None:
        return "failed", failure
    error = case.find("error")
    if error is not None:
        return "broken", error
    return "passed", None


def collect_properties(case):
    props = {}
    properties = case.find("properties")
    if properties is not None:
        for prop in properties.findall("property"):
            name = prop.get("name")
            if name:
                props[name] = prop.get("value", "")
    return props


def find_screenshots(screenshots_dir, flow_base):
    """Find PNGs whose filename references the flow file base name."""
    if not screenshots_dir or not screenshots_dir.is_dir():
        return []
    matches = []
    for png in screenshots_dir.rglob("*.png"):
        stem = png.stem.lower()
        if flow_base and flow_base.lower() in stem:
            matches.append(png)
    return sorted(matches)


def convert(junit_path, out_dir, screenshots_dir=None, env_vars=None,
           executor=None):
    tree = ET.parse(junit_path)
    root = tree.getroot()
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]

    out_dir.mkdir(parents=True, exist_ok=True)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    cursor_ms = None
    converted = 0

    for suite in suites:
        suite_name = suite.get("name", "maestro")
        base_ms = parse_timestamp(suite.get("timestamp"))
        if base_ms is not None:
            cursor_ms = base_ms

        for case in suite.findall("testcase"):
            case_name = case.get("name", "unnamed")
            classname = case.get("classname", "")
            duration_ms = int(parse_time(case.get("time"), 0.0) * 1000)
            props = collect_properties(case)
            flow_file = props.get("file", classname)

            status, problem = status_of(case)

            if cursor_ms is None:
                cursor_ms = now_ms
            start_ms = cursor_ms
            stop_ms = cursor_ms + duration_ms
            cursor_ms = stop_ms + 1

            history_id = hashlib.md5(
                f"{suite_name}::{flow_file}::{case_name}".encode("utf-8")
            ).hexdigest()
            result_uuid = str(uuid.uuid4())

            status_details = {}
            if problem is not None:
                message = problem.get("message", "").strip()
                trace = (problem.text or "").strip()
                status_details = {"message": message, "trace": trace or message}

            description_parts = []
            if flow_file:
                description_parts.append(f"Flow file: `{flow_file}`")
            device = props.get("device.name") or props.get("device.id")
            if device:
                platform = props.get("device.platform", "")
                description_parts.append(
                    f"Device: {device} ({platform})".strip())
            system_out = case.findtext("system-out", default="").strip()
            if system_out:
                description_parts.append(f"Output:\n{system_out}")

            labels = [
                {"name": "suite", "value": suite_name},
                {"name": "framework", "value": "maestro"},
            ]
            if flow_file:
                labels.append({"name": "testClass", "value": flow_file})

            attachments = []
            flow_base = Path(flow_file).stem if flow_file else ""
            for png in find_screenshots(screenshots_dir, flow_base):
                dest_name = f"{result_uuid}-{png.name}"
                shutil.copy2(png, out_dir / dest_name)
                attachments.append({
                    "name": png.stem,
                    "source": dest_name,
                    "type": "image/png",
                })

            result = {
                "uuid": result_uuid,
                "historyId": history_id,
                "testCaseId": history_id,
                "fullName": f"{suite_name}: {case_name}",
                "name": case_name,
                "status": status,
                "statusDetails": status_details,
                "stage": "finished",
                "description": "\n\n".join(description_parts),
                "steps": [],
                "attachments": attachments,
                "parameters": [],
                "labels": labels,
                "start": start_ms,
                "stop": stop_ms,
            }
            (out_dir / f"{result_uuid}-result.json").write_text(
                json.dumps(result, indent=2), encoding="utf-8")
            converted += 1

    if env_vars:
        lines = ["<environment>"]
        for key, value in env_vars:
            lines.append(
                f'  <parameter><key>{key}</key><value>{value}</value></parameter>')
        lines.append("</environment>")
        (out_dir / "environment.xml").write_text(
            "\n".join(lines), encoding="utf-8")

    if executor:
        (out_dir / "executor.json").write_text(
            json.dumps(executor, indent=2), encoding="utf-8")

    return converted


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Convert Maestro JUnit XML to Allure results.")
    parser.add_argument("--junit", required=True,
                        help="Path to Maestro JUnit XML (report.xml).")
    parser.add_argument("--out", default="allure-results",
                        help="Output dir for Allure result files.")
    parser.add_argument("--screenshots", default=None,
                        help="Dir searched recursively for PNGs to attach.")
    parser.add_argument("--env", action="append", default=[],
                        metavar="KEY=VAL",
                        help="Extra environment entry (repeatable).")
    parser.add_argument("--executor-name", default=None)
    parser.add_argument("--executor-type", default=None)
    parser.add_argument("--build-url", default=None)
    parser.add_argument("--build-name", default=None)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    junit_path = Path(args.junit)
    if not junit_path.is_file():
        print(f"ERROR: JUnit file not found: {junit_path}", file=sys.stderr)
        return 1

    env_vars = []
    for item in args.env:
        if "=" in item:
            key, value = item.split("=", 1)
            env_vars.append((key.strip(), value.strip()))

    executor = None
    if args.executor_name or args.build_url:
        executor = {
            "name": args.executor_name or "Maestro",
            "type": args.executor_type or "manual",
            "url": args.build_url or "",
            "buildName": args.build_name or "",
        }

    shots = Path(args.screenshots) if args.screenshots else None
    count = convert(junit_path, Path(args.out), shots, env_vars, executor)
    print(f"Converted {count} test case(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
