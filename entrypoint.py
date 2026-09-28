#!/usr/bin/env python3
"""Runner script for arcade-agent/analyze-action.

Orchestrates arcade-self-analysis, computes impact-scoped diff analysis,
prepares static files for GitHub Pages, injects GitHub Actions Job Summary,
and sets step outputs.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


CONFIG_FILE_NAMES = {
    "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle",
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Cargo.toml", "Cargo.lock", "go.mod", "go.sum",
    "baseline.json", "tsconfig.json", "architecture.yml"
}


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
    parser.add_argument("--commit-comment-mode", default="impact", choices=["impact", "full"], help="Commit comment mode")
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


def get_changed_files() -> list[str]:
    """Retrieve changed files in current git commit."""
    try:
        res = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]

        res = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
    except Exception as e:
        print(f"Warning: Could not get git diff: {e}", file=sys.stderr)
    return []


def compute_commit_impact(
    source_path: str,
    language: str,
    algorithm: str,
    all_smells: list[dict],
    repo_display: str,
) -> tuple[bool, str]:
    """Calculate impact-scoped architectural summary for current commit."""
    changed_files = get_changed_files()
    if not changed_files:
        return False, ""

    commit_sha = os.environ.get("GITHUB_SHA", "HEAD")[:7]
    touched_configs = [f for f in changed_files if Path(f).name in CONFIG_FILE_NAMES or ".arcade" in f]

    impact = {}
    try:
        from arcade_agent.tools.ingest import ingest
        from arcade_agent.tools.parse import parse
        from arcade_agent.tools.recover import recover
        from arcade_agent.tools.diff_impact import diff_impact

        repo = ingest(source_path)
        lang = language or repo.language or "python"
        graph = parse(str(repo.path), language=lang)
        arch = recover(graph, algorithm=algorithm)
        impact = diff_impact(graph, changed_files, architecture=arch)
    except Exception as e:
        print(f"Warning: diff_impact evaluation failed: {e}", file=sys.stderr)

    matched_files = impact.get("matched_files", [])
    changed_entities = impact.get("changed_entities", [])
    affected_components = impact.get("affected_components", [])
    downstream_dependents = impact.get("downstream_dependents", [])
    broken_contracts = impact.get("broken_contracts", [])

    has_code_impact = bool(matched_files or affected_components)
    has_config_impact = bool(touched_configs)

    if not has_code_impact and not has_config_impact:
        print(f"ℹ️ Commit {commit_sha} does not touch structural code or build configs. Changed files: {changed_files}")
        return False, ""

    # Filter smells strictly relevant to affected components
    affected_set = set(affected_components)
    relevant_smells = []
    for s in all_smells:
        comps = set(s.get("components") or [])
        if s.get("component"):
            comps.add(s.get("component"))
        if comps & affected_set:
            relevant_smells.append(s)

    status_icon = "🟢" if len(relevant_smells) == 0 else ("🟡" if len(relevant_smells) <= 2 else "🔴")
    comp_list = ", ".join(f"`{c}`" for c in affected_components) if affected_components else "*(None direct)*"

    md = [
        f"## {status_icon} Commit Architecture Impact: `{repo_display}`",
        f"**Commit:** `{commit_sha}` | **Scope:** `Impact-Scoped` | **Affected Components:** {comp_list}",
        "",
    ]

    if has_code_impact:
        md.extend([
            "| Dimension | Count | Details |",
            "| :--- | :---: | :--- |",
            f"| **Directly Changed Files** | `{len(matched_files)}` | {', '.join(f'`{f}`' for f in matched_files[:3])}{'...' if len(matched_files) > 3 else ''} |",
            f"| **Modified Entities** | `{len(changed_entities)}` | Structural classes/functions directly modified |",
            f"| **Downstream Callers** | `{len(downstream_dependents)}` | Transitive dependents relying on changed code |",
            f"| **Public Contracts** | `{len(broken_contracts)}` | Modified public entities called from outside |",
            "",
        ])

        if relevant_smells:
            md.extend([
                "### ⚠️ Localized Architectural Smells in Touched Area",
                "| Smell Type | Component(s) | Description |",
                "| :--- | :--- | :--- |",
            ])
            for s in relevant_smells:
                s_type = s.get("smell_type") or s.get("name") or "Unknown"
                s_comp = s.get("component") or (", ".join(s.get("components", []))) or "-"
                s_desc = s.get("description") or "-"
                md.append(f"| `{s_type}` | **{s_comp}** | {s_desc} |")
            md.append("")
        else:
            md.append("> ✨ **No architectural smells or cycles in the touched components.**\n")

    if has_config_impact:
        md.extend([
            "### 🔧 Build & Configuration Effects",
            f"- Modified build/architecture definitions: {', '.join(f'`{f}`' for f in touched_configs)}",
            "*- Note: Configuration changes may alter external dependencies, compiler boundaries, or baseline profiles.*",
            "",
        ])

    return True, "\n".join(md)


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

    # 4. Generate Comprehensive Summary (for Step Summary & PR comments)
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
        summary_md.append("> ✨ **Clean Architecture!** No architectural smells or cyclic components detected.\n")

    summary_md.append(f"*Artifacts generated in `{out_dir}`: Interactive HTML report + JSON baseline.*")
    full_markdown_content = "\n".join(summary_md)

    pr_comment_file = out_dir / "pr_comment.md"
    with open(pr_comment_file, "w", encoding="utf-8") as f:
        f.write(full_markdown_content)

    append_github_summary(full_markdown_content)
    set_github_output("report_markdown", str(pr_comment_file))

    # 5. Compute Commit Comment (Impact-Scoped vs Full)
    commit_comment_file = out_dir / "commit_comment.md"
    if args.commit_comment_mode == "impact":
        has_impact, impact_md = compute_commit_impact(
            args.source_path,
            args.language,
            args.algorithm,
            smells,
            repo_display,
        )
        if has_impact:
            with open(commit_comment_file, "w", encoding="utf-8") as f:
                f.write(impact_md)
            set_github_output("has_architectural_impact", "true")
            set_github_output("commit_comment_markdown", str(commit_comment_file))
            print("✓ Impact-scoped commit comment prepared.")
        else:
            set_github_output("has_architectural_impact", "false")
            set_github_output("commit_comment_markdown", "")
            print("ℹ️ Skipping commit comment: No structural code entities or build configs touched.")
    else:
        # Full mode
        with open(commit_comment_file, "w", encoding="utf-8") as f:
            f.write(full_markdown_content)
        set_github_output("has_architectural_impact", "true")
        set_github_output("commit_comment_markdown", str(commit_comment_file))

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
