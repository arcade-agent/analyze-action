# arcade-agent/analyze-action

[![Test Action](https://github.com/arcade-agent/analyze-action/actions/workflows/test.yml/badge.svg)](https://github.com/arcade-agent/analyze-action/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/arcade-agent)](https://pypi.org/project/arcade-agent/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Zero-config GitHub Action** for software architecture recovery, smell detection (Cycles, God Components, Unstable Couplings), and living **GitHub Pages** reports powered by [arcade-agent](https://github.com/arcade-agent/arcade-agent).

---

## ⚡ Quickstart (Copy & Paste)

### 1. Basic Architecture Check (PRs & Commits)

Add `.github/workflows/architecture.yml` to your repository:

```yaml
name: Architecture Check

on:
  push:
    branches: [ main, master ]
  pull_request:

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Analyze Architecture
        uses: arcade-agent/analyze-action@v1
        with:
          fail-on-smells: false
```
*Outputs a rich architectural table with component breakdowns directly in your GitHub Actions Job Summary.*

---

### 2. Living Architecture Dashboard on GitHub Pages

Publish an interactive, zero-rot architecture report to `https://<org>.github.io/<repo>/`:

```yaml
name: Architecture Health & Pages

on:
  push:
    branches: [ main, master ]
  schedule:
    - cron: '0 3 1 * *'  # Re-run monthly so reports never rot
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: 'pages'
  cancel-in-progress: false

jobs:
  analyze-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # 1. Run arcade-agent analysis
      - name: Analyze Architecture
        uses: arcade-agent/analyze-action@v1
        with:
          output-dir: 'public'
          generate-pages-index: true

      # 2. Deploy directly to GitHub Pages
      - name: Setup Pages
        uses: actions/configure-pages@v5

      - name: Upload Pages Artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: 'public'

      - name: Deploy to GitHub Pages
        uses: actions/deploy-pages@v4
```

> **Note:** Under repository **Settings → Pages**, set **Source** to **GitHub Actions**.

---

## ⚙️ Inputs & Configuration

| Input | Default | Description |
| :--- | :--- | :--- |
| `source-path` | `.` | Path to source tree relative to workspace. |
| `language` | `""` | Optional language override (`java`, `python`, `typescript`, `go`, `rust`, `c`, `kotlin`). Auto-detected if empty. |
| `algorithm` | `pkg` | Architecture recovery algorithm: `pkg` (package-based), `acdc`, `wca`, `arc`. |
| `output-dir` | `public` | Directory to output `index.html`, `arcade_report.html`, and `arcade_results.json`. |
| `generate-pages-index` | `true` | Automatically copies HTML report to `index.html` for GitHub Pages hosting. |
| `fail-on-smells` | `false` | Fail the GitHub Action step if any architectural smells are detected. |
| `exclude-dirs` | `""` | Comma-separated paths to ignore (e.g. `fixtures,e2e,dist`). |
| `exclude-tests` | `true` | Exclude test suites and vendor folders. |
| `python-version` | `3.12` | Python version for runtime environment. |
| `arcade-agent-version`| `""` | PyPI package version (default: installs latest). |

### Action Outputs

* `report-html`: Path to the generated interactive HTML report.
* `report-json`: Path to the raw JSON results and graph data.
* `smell-count`: Total count of architectural smells detected.
* `component-count`: Total number of recovered components.
* `pages-dir`: Path to the directory ready for `actions/upload-pages-artifact`.

---

## 🥊 Market Comparison

How does `arcade-agent/analyze-action` compare with established industry tools?

| Feature / Dimension | **arcade-agent** | **SonarQube** | **ArchUnit** (Java) | **CodeQL** | **Structure101 / Lattix** |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Primary Focus** | **Software Architecture** (Recovery, Smells, Boundaries) | Code Quality, Bugs & Vulns (AST / Lint) | Unit-test style architecture assertion | Semantic security vulnerability queries | Enterprise DSM (Design Structure Matrix) |
| **Setup Overhead** | **Zero Config** (1 GitHub Action step) | High (Requires server / SonarCloud token) | Medium (Requires writing Java test code) | Medium (Database build step required) | Very High (Proprietary license & server) |
| **Small Repo Viability** | **Instant (< 1s)**, works on single-package micro-libs | Heavyweight, overkill for micro-libs | Great for Java, unavailable for Polyglot | Slow query execution on small commits | Incompatible with quick CI |
| **Polyglot** | Java, Python, TS, Go, Rust, C, Kotlin | Yes | Java only | Yes (compiled/interpreted) | Mostly JVM / C++ |
| **Living Pages Dashboard**| **Built-in** (`deploy-pages` native) | Requires hosted SonarCloud dashboard | None (Only passes/fails build) | None (GitHub Security tab only) | Heavy proprietary dashboard |
| **AI Agent / MCP Ready** | **Native** (MCP tools + JSON baseline) | No | No | No | No |

---

## ⚖️ Trade-offs & Limitations

1. **AST-based vs. Runtime Reflection:**
   * *Advantage:* Analyses do not require building, compiling, or executing your codebase (works across JVM, Go, Node, Python in seconds without Maven/Gradle/NPM build overhead).
   * *Trade-off:* Does not track dynamic reflection or runtime dependency injection (e.g., Spring XML/reflection bindings) unless explicit in imports/calls.
2. **Component Granularity:**
   * On massive monoliths (1M+ LOC), hierarchical clustering (`acdc` / `wca`) requires memory. On micro-repos (< 50 files), the default `pkg` algorithm is optimal and finishes in < 0.2s.
3. **Smell Sensitivity:**
   * Default smell detection identifies severe anti-patterns (Cyclic Dependencies, God Components, Unstable Interface Couplings). Style lints and line-level issues are intentionally left to traditional linters.

---

## 🚦 Go / No-Go Decision Framework

### ✅ GO (Adopt this Action):
* **You want zero-maintenance architectural observability:** You want a live architectural map on GitHub Pages without paying for SaaS or running a dedicated server.
* **You maintain micro-libraries, SDKs, or CLI tools:** You want CI checks that run in < 500ms without slowing down PR merges.
* **You want to prevent architectural erosion:** Catching accidental circular imports or "kitchen sink" God utility files before PRs merge.
* **You want living proof for open source / client portfolios:** Showcases clean architecture with transparent, verifiable metrics.

### 🛑 NO-GO (Do NOT Adopt):
* **You need deep dynamic security tainting:** Use **CodeQL** or **Snyk**.
* **You need strictly enforced Java package access rules at compiler level:** Use **ArchUnit** unit tests.
* **You need line-by-line syntax & formatting enforcement:** Use **Ruff**, **ESLint**, or **Spotless**.

---

## 🗺️ Roadmap & Next Steps

- [x] **v1.0.0**: Zero-config Composite Action with PyPI installer and Step Summary table.
- [x] **GitHub Pages Integration**: Out-of-the-box `index.html` generation and shields.io `badge.json`.
- [ ] **PR Delta Commenter**: Auto-commenting on PRs comparing HEAD against Base branch baseline.
- [ ] **Marketplace Release**: Verified GitHub Marketplace listing tag (`v1`).
- [ ] **Multi-language Monorepo Matrix**: Parallel analysis across submodules.

---

## 📄 License

MIT © [arcade-agent](https://github.com/arcade-agent)
