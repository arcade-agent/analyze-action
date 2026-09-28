#!/usr/bin/env python3
"""Runner script for arcade-agent/analyze-action.

Orchestrates arcade-self-analysis, prepares static files for GitHub Pages,
injects GitHub Actions Job Summary, and sets step outputs.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="arcade-agent architecture analysis runner")
    parser.add_argument("--source-path", default=".", help="Source path to analyze")
    parser.add_argument("--language", default="", help="Language override")
    parser.add_argument("--algorithm", default="pkg", help="Recovery algorithm (pkg, acdc, wca, arc)")
    parser.add_argument("--output-dir", default="public", help="Output directory for reports")
    parser.add_argument("--repo-name", default="", help="Repository display name")
    parser.add_argument("--exclude-dirs", default="", help="Comma-separated dirs to exclude")
    parser.add_argument("--exclude-tests", default="true", help="Apply test exclusion policy")
    parser.add_argument("--fail-on-smells", default="false", help="Fail if smells detected")
    parser.add_argument("--generate-pages-index", default="true", help="Generate index.html for Pages")
    return parser.parse_args()


def set_github_output(key: str, value: str) -> None:
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def append_github_summary(markdown: str) -> None:
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(markdown + "\n")


def main() -> None:
    args = parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report_html = out_dir / "arcade_report.html"
    report_json = out_dir / "arcade_results.json"

    cmd = [
        "arcade-self-analysis",
        "--source", args.source_path,
        "--algorithm", args.algorithm,
        "--output-json", str(report_json),
        "--output-html", str(report_html),
    ]

    if args.language:
        cmd.extend(["--language", args.language])
    if args.exclude_dirs:
        cmd.extend(["--exclude-dirs", args.exclude_dirs])
    if args.exclude_tests.lower() == "false":
        cmd.append("--no-exclude-tests")
    if args.repo_name:
        cmd.extend(["--repo-name", args.repo_name])

    print("==================================================")
    print("🚀 Running arcade-agent Architecture Analysis")
    print(f"Command: {' '.join(cmd)}")
    print("==================================================")

    res = subprocess.run(cmd)
    if res.returncode != 0:
        print("❌ arcade-self-analysis failed.", file=sys.stderr)
        sys.exit(res.returncode)

    if not report_json.exists():
        print(f"❌ Expected results file {report_json} does not exist.", file=sys.stderr)
        sys.exit(1)

    with open(report_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    repo_display = data.get("repo_name") or args.repo_name or "Repository"
    language = data.get("language") or "auto-detected"
    num_components = data.get("num_components", 0)
    num_entities = data.get("num_entities", 0)
    num_edges = data.get("num_edges", 0)
    smells = data.get("smells", [])
    num_smells = len(smells)

    # 1. Setup GitHub Pages entry point if requested
    if args.generate_pages_index.lower() == "true" and report_html.exists():
        pages_index = out_dir / "index.html"
        shutil.copyfile(report_html, pages_index)
        print(f"✓ Copied HTML report to {pages_index} for GitHub Pages serving.")

    # 2. Generate shields.io compatible badge data
    badge_color = "brightgreen" if num_smells == 0 else ("yellow" if num_smells <= 2 else "red")
    badge_data = {
        "schemaVersion": 1,
        "label": "architecture",
        "message": f"{num_components} components | {num_smells} smells",
        "color": badge_color,
    }
    with open(out_dir / "badge.json", "w", encoding="utf-8") as f:
        json.dump(badge_data, f, indent=2)

    # 3. Export GitHub Action outputs
    set_github_output("report_html", str(report_html))
    set_github_output("report_json", str(report_json))
    set_github_output("smell_count", str(num_smells))
    set_github_output("component_count", str(num_components))
    set_github_output("pages_dir", str(out_dir))

    # 4. Generate GitHub Step Summary (Rich Markdown)
    status_icon = "🟢" if num_smells == 0 else ("🟡" if num_smells <= 2 else "🔴")
    summary_md = [
        f"## {status_icon} Architecture Analysis: {repo_display}",
        f"**Algorithm:** `{args.algorithm}` | **Language:** `{language}` | **Status:** **{num_smells} Smell(s)**",
        "",
        "| Metric | Value | Description |",
        "| :--- | :---: | :--- |",
        f"| **Architectural Components** | `{num_components}` | High-level logical modules recovered |",
        f"| **Entities / Classes** | `{num_entities}` | Analyzed structural units |",
        f"| **Dependencies (Edges)** | `{num_edges}` | Cross-entity couplings and calls |",
        f"| **Architectural Smells** | `{num_smells}` | Cycle, God Component, or Unstable coupling |",
        "",
    ]

    if num_smells > 0:
        summary_md.extend([
            "### ⚠️ Detected Architectural Smells",
            "| Smell Type | Component(s) | Details |",
            "| :--- | :--- | :--- |",
        ])
        for smell in smells:
            s_type = smell.get("smell_type") or smell.get("name") or "Unknown"
            s_comp = smell.get("component") or (", ".join(smell.get("components", []))) or "-"
            s_desc = smell.get("description") or "-"
            summary_md.append(f"| `{s_type}` | **{s_comp}** | {s_desc} |")
        summary_md.append("")
    else:
        summary_md.append("> ✨ **Clean Architecture!** No architectural smells or cyclic components detected.")
        summary_md.append("")

    summary_md.append(f"*Artifacts generated in `{out_dir}`: Interactive HTML report + JSON baseline.*")
    markdown_content = "\n".join(summary_md)

    pr_comment_file = out_dir / "pr_comment.md"
    with open(pr_comment_file, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    append_github_summary(markdown_content)
    set_github_output("report_markdown", str(pr_comment_file))

    print("\n==================================================")
    print("📋 Analysis Summary")
    print(f"  Repo:        {repo_display}")
    print(f"  Components:  {num_components}")
    print(f"  Entities:    {num_entities}")
    print(f"  Edges:       {num_edges}")
    print(f"  Smells:      {num_smells}")
    print(f"  Output Dir:  {out_dir}")
    print("==================================================")

    if args.fail_on_smells.lower() == "true" and num_smells > 0:
        print(f"❌ Step failed because --fail-on-smells=true and {num_smells} smell(s) were found.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
