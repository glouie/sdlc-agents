# SDLC Agent System

A modular multi-agent system organized around the Software Development Lifecycle.
Two modes: **BUILD** (generate a new project from a goal) and **REVIEW** (audit existing code).

---

## Quick Start

```bash
pip install anthropic
export ANTHROPIC_API_KEY=your_key_here
```

### BUILD MODE — Start a new project from scratch

```bash
python build_orchestrator.py "A CLI tool that monitors log files and alerts on error patterns"
```

That's it. The tool will:
1. Ask you a focused set of questions (hybrid — once upfront, then fully automatic)
2. Build a project spec from your answers
3. Design the architecture (tech stack, patterns, file structure)
4. Show you the plan and ask for confirmation
5. Generate all source code, tests, Dockerfile, CI, Makefile, .env.example
6. Run code review on the generated files and auto-fix issues
7. Print how to run, test, and deploy your new project

```bash
# Skip optional phases
python build_orchestrator.py "Parse nginx logs" --no-review
python build_orchestrator.py "S3 sync tool" --output my-s3-sync --no-tests

# Full build with custom output dir
python build_orchestrator.py "File deduplication CLI" --output dedup-cli
```

### REVIEW MODE — Audit existing code

```bash
# Review a single file
python sdlc_orchestrator.py script.py --fix

# Full pipeline: review + tests + deployment check
python sdlc_orchestrator.py app.py --all --auto

# With team conventions
python sdlc_orchestrator.py app.py --fix --conventions CONVENTIONS.md

# UI/UX review
python 4_review/ui_review_orchestrator.py index.html --fix --platform web
```

---

## Directory Structure

```
sdlc_agents/
│
├── build_orchestrator.py          ★ START HERE for new projects
├── sdlc_orchestrator.py           ★ START HERE for existing code
│
├── core/
│   ├── base_agent.py              Shared runner — all agents import from here
│   ├── merger_agent.py            Universal fix merger — reused by all pipelines
│   ├── prompt_generator_agent.py  On-the-fly prompt generation for any language
│   ├── interview_agent.py         Upfront question gathering (hybrid pipeline)
│   └── architect_agent.py         Decides structure, stack, file manifest
│
├── 1_planning/
│   ├── product_manager_agent.py   WHAT to build and WHY (requirements)
│   └── project_manager_agent.py   WHEN and HOW (task plan + progress)
│
├── 2_design/
│   ├── ui_accessibility_agent.py
│   ├── ui_color_contrast_agent.py
│   ├── ui_typography_agent.py
│   ├── ui_mobile_touch_agent.py
│   ├── ui_keyboard_desktop_agent.py
│   ├── ui_visual_feedback_agent.py
│   └── ui_layout_structure_agent.py
│
├── 3_development/
│   ├── code_generator_agent.py    ★ Generates source files from spec
│   ├── code_security_agent.py
│   ├── code_style_agent.py
│   ├── code_logic_agent.py
│   └── code_structure_agent.py
│
├── 4_review/
│   ├── code_review_orchestrator.py
│   └── ui_review_orchestrator.py
│
├── 5_testing/
│   └── test_generator_agent.py
│
└── 6_deployment/
    ├── config_generator_agent.py  ★ Generates Dockerfile, CI, Makefile, .env
    └── deployment_checklist_agent.py
```

---

## How the Build Pipeline Works

```
You: "Build a CLI tool that watches log files and alerts on patterns"
                            ↓
        interview_agent     asks 4-8 focused questions, you answer once
                            ↓
        interview_agent     synthesizes answers into project_spec.json
                            ↓
        architect_agent     decides: language, parser lib, error strategy,
                            test framework, folder layout, file manifest
                            ↓
        [CONFIRMATION]      shows plan → you approve → runs automatically
                            ↓
        code_generator      generates files in dependency order
                            each agent gets: spec + arch + dep signatures only
                            ↓
        code_review         security + style + logic review on every file
                            auto-fixes everything
                            ↓
        config_generator    Dockerfile, docker-compose, CI yaml, Makefile
                            ↓
        DONE: runnable project in output_dir/
```

---

## Architecture Principles

**Architect agent is the keystone.** Without it, generator agents make
inconsistent tech decisions. The architect runs once; every generator
receives its decisions as context.

**Context stays minimal per agent.** Generator agents receive only dependency
signatures, not full file contents. This keeps each call focused and cheap.

**Fix order matters.** Security → Logic → Style → Structure → Accessibility.
Applied in this order to avoid conflicts when merging.

**Prompt cache.** Generated prompts for new languages are cached in
`.agent_prompt_cache.json`. Only generated once. Hand-edit to tune.

---

## Language Support

**Built-in:** bash, Python, JavaScript/TypeScript

**Auto-generated:** Ruby, Go, Rust, Java, Kotlin, Swift, and any other language.
Cached after first use.

```bash
python core/prompt_generator_agent.py reviewer ruby security
python core/prompt_generator_agent.py refine ruby security "missed SQL injection"
```
