"""OpenSkill pipeline — the three-stage orchestrator.

Stage 1 (Open-World Knowledge Acquisition, host side):
  Step 1:  Agent Planner (LLM) -> DR query
  Step 2:  Deep Research -> background.md + sources.json
  Step 2b: Skill Planner (LLM) -> skill_plan.md + references/<skill>/
  Step 2c: Verification research (search grounding) -> surrogate_dr_research.md

Stage 2 (Leakage-Free Skill Evolution, container side):
  Step 3:  OpenSkillAgent creates evo-* skills, executes the task, and
           refines against the independent surrogate verifier until the
           virtual pass rate reaches 1.0 or the retry budget is exhausted.
           The hidden ground-truth tests are never invoked here.

Stage 3 (Zero-Shot Target Evaluation, host side):
  Final:   Evaluation agent x N independent runs -> rewards. Ground-truth
           tests are unlocked only in this stage.

Key architectural principles:
- The surrogate verification loop lives inside the agent's
  _check_episode_exit rather than as a separate external loop.
- Multi-skill plan: the LLM decomposes the DR doc into 1-4 skills with
  clear responsibility boundaries; per-skill reference files provide
  focused domain knowledge to the creator agent.
- Reference injection: the DR doc is split into per-skill references/
  subdirectories following the skill-creator meta-skill's progressive
  disclosure pattern.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import shutil
import subprocess
import textwrap
import threading
import time
from datetime import datetime
from pathlib import Path

from .agent_planner import AgentPlanner
from .deep_research_client import DeepResearchClient
from .skill_planner import SkillPlanner, save_skill_plan

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Keywords to strip from all DR / search queries to prevent answer leakage.
_BANNED_SEARCH_KEYWORDS: list[str] = [
    "SkillsBench", "skillsbench", "skills-bench", "skills_bench",
]


def _sanitize_query(query: str) -> str:
    """Remove banned keywords from a search query to prevent answer leakage."""
    for kw in _BANNED_SEARCH_KEYWORDS:
        query = re.sub(re.escape(kw), "", query, flags=re.IGNORECASE)
    return query

# Agent import paths for harbor
OPENSKILL_AGENT_IMPORT = (
    "libs.openskill.openskill_evolution:OpenSkillAgent"
)
TERMINUS2_AGENT_IMPORT = (
    "libs.terminus_agent.agents.terminus_2.harbor_terminus_2_skills:HarborTerminus2WithSkills"
)
AZURE_CLAUDE_CODE_AGENT_IMPORT = (
    "libs.terminus_agent.agents.azure_claude_code:AzureClaudeCode"
)

# eval-agent name → import path mapping
_EVAL_AGENT_IMPORT = {
    "terminus-2": TERMINUS2_AGENT_IMPORT,
    "claude-code": AZURE_CLAUDE_CODE_AGENT_IMPORT,
    "claude-code-bedrock": "libs.terminus_agent.agents.bedrock_claude_code:BedrockClaudeCode",
    "codex": "libs.terminus_agent.agents.azure_codex:AzureCodex",
}


def _print(msg: str) -> None:
    """Print pipeline status."""
    try:
        print(msg, flush=True)
    except BrokenPipeError:
        pass


def _refresh_env():
    """Re-read .env for rotated API keys."""
    dotenv_path = REPO_ROOT / ".env"
    if not dotenv_path.exists():
        return
    try:
        with open(dotenv_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'\"")
                if key and value:
                    os.environ[key] = value
    except Exception:
        pass


def _docker_cleanup() -> None:
    """Force-clean Docker resources left by a harbor run.

    Called after every harbor subprocess exits (success, failure, or kill).
    Removes stopped containers, dangling images, and build cache so the
    next task starts with a clean Docker state.
    """
    for desc, cmd in [
        ("stopped containers", ["docker", "container", "prune", "-f"]),
        ("dangling images",    ["docker", "image", "prune", "-f"]),
        ("build cache",        ["docker", "buildx", "prune", "-f",
                                "--max-used-space", "30GB"]),
    ]:
        try:
            subprocess.run(cmd, capture_output=True, timeout=120)
            _print(f"[pipeline] Docker cleanup: removed {desc}")
        except Exception as e:
            _print(f"[pipeline] Docker cleanup: {desc} failed: {e}")


def _run_harbor(
    task_path: Path,
    model: str,
    agent_import_path: str,
    job_name: str | None = None,
    force_build: bool = False,
    agent_kwargs: dict | None = None,
    timeout_multiplier: float | None = None,
) -> dict:
    """Run a single harbor experiment. Returns result dict."""
    cmd = [
        "uv", "run", "harbor", "run",
        "-p", str(task_path),
        "-m", model,
        "--agent-import-path", agent_import_path,
    ]
    if job_name:
        cmd.extend(["--job-name", job_name])
    if force_build:
        cmd.append("--force-build")
    if timeout_multiplier is not None:
        cmd.extend(["--timeout-multiplier", str(timeout_multiplier)])
    if agent_kwargs:
        for key, value in agent_kwargs.items():
            if isinstance(value, bool):
                arg_value = "true" if value else "false"
            else:
                arg_value = str(value)
            cmd.extend(["--agent-kwarg", f"{key}={arg_value}"])

    _print(f"[pipeline] Running: {' '.join(cmd)}")

    _refresh_env()
    env = os.environ.copy()
    env.pop("__PYVENV_LAUNCHER__", None)
    env["PYTHONUNBUFFERED"] = "1"

    started_at = datetime.now().isoformat()
    captured_lines: list[str] = []
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
        )

        def _reader():
            assert process.stdout is not None
            for line in process.stdout:
                print(line, end="", flush=True)
                captured_lines.append(line)

        reader = threading.Thread(target=_reader, daemon=True)
        reader.start()
        process.wait()
        reader.join(timeout=5)
        if process.stdout:
            process.stdout.close()
        _docker_cleanup()

        finished_at = datetime.now().isoformat()
        stdout = "".join(captured_lines)

        job_folder = job_name
        if not job_folder:
            match = re.search(r"Results written to jobs/([^/]+)/", stdout)
            if match:
                job_folder = match.group(1)

        return {
            "success": process.returncode == 0,
            "returncode": process.returncode,
            "stdout": stdout,
            "job_folder": job_folder,
            "started_at": started_at,
            "finished_at": finished_at,
        }
    except Exception as e:
        _docker_cleanup()
        return {
            "success": False,
            "returncode": -1,
            "stdout": "".join(captured_lines),
            "stderr": str(e),
            "job_folder": job_name,
            "started_at": started_at,
            "finished_at": datetime.now().isoformat(),
        }


def _check_completion(job_folder: str) -> dict:
    """Check harbor job completion and extract reward/test metrics."""
    result = {
        "tests_total": 0,
        "tests_passed": 0,
        "tests_failed": 0,
        "reward": None,
        "finished_normally": False,
    }

    job_path = Path(job_folder)
    if not job_path.is_absolute():
        job_path = REPO_ROOT / "jobs" / job_folder
    if not job_path.exists():
        return result

    # Find trial directory
    trial_dir = None
    for item in job_path.iterdir():
        if item.is_dir() and "__" in item.name:
            trial_dir = item
            break
    if not trial_dir:
        return result

    verifier_dir = trial_dir / "verifier"

    # Parse test-stdout.txt
    test_stdout = verifier_dir / "test-stdout.txt"
    if test_stdout.exists():
        try:
            text = test_stdout.read_text()
            matches = re.findall(r"=+ ([\d\w, ]+) in [\d.]+s.*?=+", text)
            if matches:
                summary = matches[-1]
                p = re.search(r"(\d+) passed", summary)
                f = re.search(r"(\d+) failed", summary)
                e = re.search(r"(\d+) error", summary)
                n_passed = int(p.group(1)) if p else 0
                n_failed = int(f.group(1)) if f else 0
                n_error = int(e.group(1)) if e else 0
                result["tests_total"] = n_passed + n_failed + n_error
                result["tests_passed"] = n_passed
                result["tests_failed"] = n_failed + n_error
        except OSError:
            pass

    # Check reward
    reward_path = verifier_dir / "reward.txt"
    if reward_path.exists():
        try:
            result["reward"] = float(reward_path.read_text().strip())
        except (OSError, ValueError):
            pass

    # Try result.json
    result_json = trial_dir / "result.json"
    if result_json.exists():
        try:
            data = json.loads(result_json.read_text())
            vr = data.get("verifier_result") or {}
            rewards = vr.get("rewards") or {}
            reward_val = rewards.get("reward") if isinstance(rewards, dict) else None
            if reward_val is not None:
                result["reward"] = reward_val
        except (json.JSONDecodeError, KeyError, AttributeError):
            pass

    if result["reward"] is not None:
        result["finished_normally"] = True

    return result


class OpenSkillPipeline:
    """Pipeline orchestrator for OpenSkill."""

    def __init__(
        self,
        planner_model: str = "anthropic/claude-opus-4-6",
        creator_model: str = "anthropic/claude-opus-4-6",
        evaluator_model: str = "anthropic/claude-opus-4-6",
        eval_agent: str = "claude-code",
        dr_agent: str = "deep-research-pro-preview-12-2025",
        eval_runs: int = 5,
        surrogate_dr_agent: str = "gemini-3.1-flash-lite-preview",
        force_build: bool = True,
        source_tasks_dir: Path | None = None,
        workspace_dir: Path | None = None,
        enable_dr: bool = True,
        enable_surrogate_dr: bool = True,
        enable_targeted_dr: bool = True,
    ):
        self.planner_model = planner_model
        self.creator_model = creator_model
        self.evaluator_model = evaluator_model
        self.eval_agent = eval_agent
        self.eval_agent_import = _EVAL_AGENT_IMPORT[eval_agent]
        self.dr_agent = dr_agent
        self.eval_runs = eval_runs
        self.surrogate_dr_agent = surrogate_dr_agent
        self.force_build = force_build
        self.enable_dr = enable_dr
        self.enable_surrogate_dr = enable_surrogate_dr
        self.enable_targeted_dr = enable_targeted_dr

        self.source_tasks_dir = source_tasks_dir or (REPO_ROOT / "tasks")
        self.workspace_dir = workspace_dir or (REPO_ROOT / "workspace")

        # Results tracking
        self.results_csv = REPO_ROOT / "results" / "results.csv"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_task(self, task_name: str) -> dict:
        """Run the full pipeline for a single task.

        DR query → DR doc → skill plan + references → verification research
        → OpenSkillAgent (surrogate loop) → independent evaluation
        """
        _print(f"\n{'='*60}")
        _print(f"[pipeline] Task: {task_name}")
        _print(f"{'='*60}")

        start_time = time.time()

        # 0. Prepare workspace
        workspace = self._prepare_workspace(task_name)
        task_dir = workspace["task_dir"]
        env_dir = workspace["env_dir"]
        doc_dir = workspace["doc_dir"]

        # Read task context
        instruction = (task_dir / "instruction.md").read_text(encoding="utf-8")
        task_toml = {}
        toml_path = task_dir / "task.toml"
        if toml_path.exists():
            import tomllib
            task_toml = tomllib.loads(toml_path.read_text(encoding="utf-8"))

        # Step 1: Agent Planner -> DR query
        _print("\n[pipeline] Step 1: Generating DR query via Agent Planner...")
        planner = AgentPlanner(model=self.planner_model)
        dr_query = planner.generate_dr_query(instruction, task_toml, env_dir)
        _print(f"[pipeline] DR query generated: {len(dr_query)} chars")

        # Save query for inspection
        (doc_dir / "dr_query.txt").write_text(dr_query, encoding="utf-8")

        # Step 2: Gemini DR -> background.md + sources.json
        if self.enable_dr:
            _print("\n[pipeline] Step 2: Running Deep Research...")
            dr_result = self._run_deep_research(dr_query, doc_dir)
            if dr_result["status"] != "completed":
                _print(f"[pipeline] DR failed: {dr_result['status']}")
                _docker_cleanup()
                result = self._make_result(task_name, start_time, "dr_failed")
                self._record_result(result)
                return result

            _print(
                f"[pipeline] DR completed: {dr_result['chars']} chars, "
                f"{dr_result['sources_count']} sources in {dr_result['elapsed']:.0f}s"
            )
        else:
            _print("\n[pipeline] Step 2: Deep Research DISABLED, skipping")

        # Step 2b: Skill Plan — decompose DR doc into multi-skill plan + references
        _print("\n[pipeline] Step 2b: Generating multi-skill plan...")
        bg_path = doc_dir / "background.md"
        dr_background = bg_path.read_text(encoding="utf-8") if bg_path.exists() else ""
        skill_plan = self._generate_skill_plan(
            instruction, task_toml, dr_background, env_dir, doc_dir,
        )
        n_skills = len(skill_plan.get("skills", []))
        _print(f"[pipeline] Skill plan: {n_skills} skills planned")
        for i, s in enumerate(skill_plan.get("skills", []), 1):
            _print(f"[pipeline]   {i}. {s['name']}: {s.get('responsibility', 'N/A')}")

        # Step 2c: Pre-generate verification research for the surrogate verifier
        # This goes into the doc dir so the agent's surrogate verifier
        # can reference it when generating tests
        if self.enable_surrogate_dr:
            _print("\n[pipeline] Step 2c: Generating verification research...")
            self._run_surrogate_dr(instruction, task_toml, doc_dir, env_dir)
        else:
            _print("\n[pipeline] Step 2c: Verification research DISABLED, skipping")

        # Step 3: Run the Skill Creator Agent (internal surrogate loop,
        # exits when the surrogate verifier passes at 100%)
        _print("\n[pipeline] Step 3: Running Skill Creator Agent...")
        creator_result = self._run_skill_creator(task_dir, task_name)
        if not creator_result["success"]:
            _print("[pipeline] Skill creator failed")
            _docker_cleanup()
            result = self._make_result(task_name, start_time, "creator_failed")
            self._record_result(result)
            return result

        # Copy exported skills from job agent logs to workspace
        self._copy_skills_from_job(
            creator_result.get("job_folder"),
            env_dir / "skills",
        )

        # Check if skills were created
        skill_dirs = list((env_dir / "skills").glob("evo-*"))
        _print(f"[pipeline] Skills created: {[d.name for d in skill_dirs]}")

        if not skill_dirs:
            _print("[pipeline] FAIL: No skills created — skipping evaluation")
            result = self._make_result(task_name, start_time, "no_skills_created")
            self._record_result(result)
            return result

        # Final: Evaluation
        if self.eval_runs > 0:
            _print(f"\n[pipeline] Evaluation ({self.eval_runs} runs)...")
            eval_results = self._run_evaluation(task_name, task_dir, env_dir)
        else:
            _print("[pipeline] Evaluation skipped (eval_runs=0)")
            eval_results = []

        elapsed = time.time() - start_time
        result = self._make_result(
            task_name, start_time, "completed",
            eval_results=eval_results,
        )
        result["elapsed_sec"] = elapsed

        # Record to CSV
        self._record_result(result)

        _print(f"\n[pipeline] Task {task_name} completed in {elapsed:.0f}s")
        _print(f"[pipeline] Mean reward: {result.get('eval_mean_reward', 'N/A')}")
        _print(f"[pipeline] Mean acc:    {result.get('eval_mean_acc', 'N/A')}")
        _print(f"[pipeline] Per-run:     {eval_results}")

        return result

    # ------------------------------------------------------------------
    # Step 0: Workspace preparation
    # ------------------------------------------------------------------

    def _prepare_workspace(self, task_name: str) -> dict:
        """Copy the task into the workspace and clear pre-existing artifacts.

        Skills, docs, and verifier state from a previous evolution run (or
        shipped with the released tasks) are removed so the agent starts
        from a clean task definition.
        """
        src = self.source_tasks_dir / task_name
        dst = self.workspace_dir / task_name

        if not src.exists():
            raise FileNotFoundError(f"Source task not found: {src}")

        if src.resolve() == dst.resolve():
            raise ValueError("workspace_dir must differ from source_tasks_dir")

        # Fresh copy
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

        env_dir = dst / "environment"
        doc_dir = env_dir / "doc"

        # Clear pre-existing skills
        skills_dir = env_dir / "skills"
        if skills_dir.exists():
            shutil.rmtree(skills_dir)
        skills_dir.mkdir(parents=True, exist_ok=True)

        # Clear pre-existing docs and verifier state
        if doc_dir.exists():
            shutil.rmtree(doc_dir)
        doc_dir.mkdir(parents=True, exist_ok=True)
        verifier_dir = env_dir / "verifier"
        if verifier_dir.exists():
            shutil.rmtree(verifier_dir)

        _print(f"[pipeline] Workspace prepared: {dst}")
        _print(f"[pipeline]   env_dir: {env_dir}")
        _print(f"[pipeline]   doc_dir: {doc_dir}")

        return {
            "task_dir": dst,
            "env_dir": env_dir,
            "doc_dir": doc_dir,
            "skills_dir": skills_dir,
        }

    # ------------------------------------------------------------------
    # Skill extraction from job
    # ------------------------------------------------------------------

    def _copy_skills_from_job(
        self,
        job_folder: str | None,
        target_skills_dir: Path,
    ) -> None:
        """Copy exported skills from job agent logs to workspace skills dir.

        After the skill creator agent runs, it exports evo-* skills to
        `<job>/<trial>/agent/evolved_skills/`. This method copies them
        to the workspace `environment/skills/` so the evaluation agent
        can load them.
        """
        if not job_folder:
            _print("[pipeline] No job folder to extract skills from")
            return

        job_path = Path(job_folder)
        if not job_path.is_absolute():
            job_path = REPO_ROOT / "jobs" / job_folder

        if not job_path.exists():
            _print(f"[pipeline] Job path not found: {job_path}")
            return

        # Find trial directory
        trial_dir = None
        for item in job_path.iterdir():
            if item.is_dir() and "__" in item.name:
                trial_dir = item
                break

        if not trial_dir:
            _print("[pipeline] No trial directory found in job")
            return

        # Look for evolved_skills in agent logs
        evolved_dir = trial_dir / "agent" / "evolved_skills"
        if not evolved_dir.exists():
            _print(f"[pipeline] No evolved_skills dir in {evolved_dir}")
            return

        # Copy each evo-* skill to target
        for skill_dir in sorted(evolved_dir.iterdir()):
            if skill_dir.is_dir() and skill_dir.name.startswith("evo-"):
                dest = target_skills_dir / skill_dir.name
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(skill_dir, dest)
                _print(f"[pipeline] Copied skill: {skill_dir.name}")

    # ------------------------------------------------------------------
    # Step 2: Deep Research
    # ------------------------------------------------------------------

    def _run_deep_research(self, query: str, doc_dir: Path) -> dict:
        """Run DR and save results to doc_dir."""
        try:
            client = DeepResearchClient(
                agent=self.dr_agent,
            )
        except ValueError as e:
            _print(f"[pipeline] DR client init failed: {e}")
            return {"status": "failed", "chars": 0, "sources_count": 0, "elapsed": 0}

        result = client.research(_sanitize_query(query))

        if result.status == "completed" and result.text:
            # Write background.md
            bg_path = doc_dir / "background.md"
            bg_path.write_text(result.text, encoding="utf-8")

            # Write sources.json
            if result.sources:
                sources_path = doc_dir / "sources.json"
                sources_path.write_text(
                    json.dumps(result.sources, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

            return {
                "status": "completed",
                "chars": len(result.text),
                "sources_count": len(result.sources),
                "elapsed": result.elapsed_sec,
            }

        return {
            "status": result.status,
            "chars": 0,
            "sources_count": 0,
            "elapsed": result.elapsed_sec,
        }

    # ------------------------------------------------------------------
    # Step 2b: Skill Plan + Reference Injection
    # ------------------------------------------------------------------

    def _generate_skill_plan(
        self,
        instruction: str,
        task_toml: dict,
        dr_background: str,
        env_dir: Path,
        doc_dir: Path,
    ) -> dict:
        """Generate multi-skill plan and extract per-skill references.

        Uses the planner model to decompose the DR doc into N skill plans,
        then extracts relevant DR doc sections into per-skill reference files.
        Both the plan (skill_plan.md) and references (references/<skill>/) are
        placed in the doc dir so the agent can read them.
        """
        planner = SkillPlanner(model=self.planner_model)

        # Generate skill plan
        skill_plan = planner.generate_skill_plan(
            instruction=instruction,
            task_toml=task_toml,
            dr_background=dr_background,
            environment_dir=env_dir,
        )

        # Save plan to doc dir (agent will read skill_plan.md)
        save_skill_plan(skill_plan, doc_dir)
        _print(f"[pipeline] Saved skill plan to {doc_dir / 'skill_plan.md'}")

        # Extract per-skill references from DR doc
        ref_dirs = planner.extract_skill_references(
            skill_plan=skill_plan,
            dr_background=dr_background,
            doc_dir=doc_dir,
        )
        for ref_dir in ref_dirs.values():
            _print(f"[pipeline] Created reference dir: {ref_dir}")

        return skill_plan

    # ------------------------------------------------------------------
    # Step 3: Skill Creator Agent
    # ------------------------------------------------------------------

    def _run_skill_creator(self, task_dir: Path, task_name: str) -> dict:
        """Run the OpenSkill agent (Terminus-2 harness) with the internal
        surrogate verification loop."""
        job_name = f"openskill-creator-{task_name}-{int(time.time()) % 10000:04d}"

        return _run_harbor(
            task_path=task_dir,
            model=self.creator_model,
            agent_import_path=OPENSKILL_AGENT_IMPORT,
            job_name=job_name,
            force_build=self.force_build,
            agent_kwargs={
                "enable_dr_initial": False,  # DR doc already placed in workspace
                "enable_targeted_dr": self.enable_targeted_dr,
            },
        )

    # ------------------------------------------------------------------
    # Verification research: lightweight search for surrogate context (pre-injection)
    # ------------------------------------------------------------------

    def _run_surrogate_dr(
        self,
        instruction: str,
        task_toml: dict,
        doc_dir: Path,
        env_dir: Path | None = None,
    ) -> str:
        """Run a lightweight search to gather VERIFICATION-SPECIFIC domain knowledge.

        Complementary to the first DR (agent_planner → background.md) which
        provides skill-building knowledge (APIs, patterns, pitfalls).  This
        second DR focuses exclusively on what an **independent verifier** needs
        to generate strong pytest assertions — things the first DR does NOT
        cover: ground-truth reference values, statistical invariants,
        cross-validation methods, and published benchmarks.

        The first DR's ``background.md`` is read and passed as "Already Known"
        context to explicitly prevent redundant searching.

        Returns:
            Research text for surrogate test generation, or empty string on failure.
        """
        from .agent_planner import build_domain_hint, build_planner_context

        # Build domain hint from task metadata + instruction
        domain_hint = build_domain_hint(task_toml, instruction)

        # Build the same rich context used elsewhere (instruction + toml + env files)
        task_context = build_planner_context(instruction, task_toml, env_dir)

        # Read first DR output to exclude from this search
        background_excerpt = ""
        background_path = doc_dir / "background.md"
        if background_path.exists():
            full_bg = background_path.read_text(encoding="utf-8")
            background_excerpt = full_bg[:4000]
            if len(full_bg) > 4000:
                background_excerpt += "\n... (truncated)"

        # Build query — orthogonal to the first DR
        query = textwrap.dedent(f"""\
            ## Domain

            {domain_hint}

            ## Goal

            I need to write an independent SURROGATE TEST (pytest) that verifies
            whether a coding skill's output is correct, WITHOUT access to the
            ground-truth solution or tests.

            I need VERIFICATION ANCHORS — independently derived ground-truth
            values and invariants that I can hard-code as pytest assertions.
            These must come from external authoritative sources (documentation,
            textbooks, reference implementations), NOT from running the skill.

            ## Already Known (from prior research — DO NOT REPEAT)

            A separate deep research pass already gathered the following domain
            knowledge for building the skill (API usage, code patterns, pitfalls,
            deprecations). Do NOT duplicate any of this. Assume I already have
            everything below:

            <already_known>
            {background_excerpt}
            </already_known>

            ## Task Context

            {task_context}

            ## What I Need (ONLY these — nothing from "Already Known")

            1. **INDEPENDENTLY COMPUTABLE REFERENCE VALUES**: For well-known or
               small inputs relevant to this task, compute the exact expected
               outputs step by step. Show the full computation chain
               (input → intermediate → final result). These must be derivable
               without running the skill itself. For example: "For SMILES 'CCO',
               Morgan fingerprint with radius=2 produces bit vector [...],
               Tanimoto similarity with 'CO' = 0.333."

            2. **DATASET-LEVEL STATISTICAL INVARIANTS**: For the task's input
               data, what aggregate properties must the output satisfy?
               Examples: row counts after joins, sum-to-one constraints for
               probabilities, monotonicity in sorted output, value range bounds
               from the domain (e.g., "similarity scores ∈ [0,1]"),
               completeness checks (every input entity appears in output).

            3. **CROSS-VALIDATION APPROACHES**: Are there alternative tools,
               libraries, or methods that can independently compute the same
               result as a cross-check? For example: if the skill uses
               scipy.optimize, can Wolfram Alpha verify the answer? If it uses
               pandas groupby, can a SQL query produce the same aggregation?
               Provide concrete code or commands for the alternative approach.

            4. **BENCHMARKS AND REFERENCE IMPLEMENTATIONS**: Are there published
               benchmarks, textbook examples, Kaggle notebooks, or reference
               implementations that solve this exact or very similar problem?
               Provide URLs, expected inputs/outputs for standard test cases,
               and any known result tables that can serve as test oracles.

            Be CONCRETE: specific numbers, specific function calls, specific
            URLs. Every fact must be directly translatable into a pytest
            assertion. Do NOT provide general API documentation or coding
            patterns — those are already covered.
        """)

        _print("[pipeline] Running lightweight search for verification research...")
        _print(f"[pipeline] Surrogate DR agent: {self.surrogate_dr_agent}")

        try:
            # Use Gemini generative model with search grounding (not deep research)
            from google import genai
            from google.genai import types

            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                _print("[pipeline] No Gemini API key for surrogate DR, skipping")
                return ""

            client = genai.Client(api_key=api_key)

            response = client.models.generate_content(
                model=self.surrogate_dr_agent,
                contents=_sanitize_query(query),
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.3,
                ),
            )

            research_text = response.text or ""
            _print(f"[pipeline] Surrogate DR completed: {len(research_text)} chars")

            # Save for inspection
            (doc_dir / "surrogate_dr_research.md").write_text(
                research_text, encoding="utf-8",
            )

            return research_text

        except Exception as e:
            _print(f"[pipeline] Surrogate DR failed: {e}")
            return ""

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def _run_evaluation(
        self,
        task_name: str,
        task_dir: Path,
        env_dir: Path,
    ) -> list[dict]:
        """Run N evaluation runs with the generated skill."""
        eval_agent_import = self.eval_agent_import

        results = []

        for run_idx in range(self.eval_runs):
            _print(f"\n[pipeline] Eval run {run_idx + 1}/{self.eval_runs}")

            job_name = (
                f"openskill-eval-{task_name}-"
                f"run{run_idx + 1}-{int(time.time()) % 10000:04d}"
            )

            result = _run_harbor(
                task_path=task_dir,
                model=self.evaluator_model,
                agent_import_path=eval_agent_import,
                job_name=job_name,
                force_build=(run_idx == 0),  # Only force-build first run
            )

            # Check completion
            job_folder = result.get("job_folder", job_name)
            completion = _check_completion(job_folder)

            run_result = {
                "run": run_idx + 1,
                "success": result["success"],
                "tests_passed": completion["tests_passed"],
                "tests_total": completion["tests_total"],
                "reward": completion["reward"],
                "finished_normally": completion["finished_normally"],
            }
            results.append(run_result)

            _print(
                f"[pipeline] Eval run {run_idx + 1}: "
                f"{completion['tests_passed']}/{completion['tests_total']} tests, "
                f"reward={completion['reward']}"
            )

            # Docker cleanup between runs
            try:
                subprocess.run(
                    ["docker", "container", "prune", "-f"],
                    capture_output=True, timeout=30,
                )
            except Exception:
                pass

        return results

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    def _make_result(
        self,
        task_name: str,
        start_time: float,
        status: str,
        eval_results: list[dict] | None = None,
    ) -> dict:
        elapsed = time.time() - start_time
        result = {
            "task": task_name,
            "status": status,
            "elapsed_sec": elapsed,
            "creator_model": self.creator_model,
            "evaluator_model": self.evaluator_model,
            "planner_model": self.planner_model,
            "timestamp": datetime.now().isoformat(),
        }

        if eval_results:
            rewards = [r["reward"] for r in eval_results if r["reward"] is not None]
            passed = [r["tests_passed"] for r in eval_results]
            totals = [r["tests_total"] for r in eval_results]

            result["eval_runs"] = len(eval_results)
            result["eval_rewards"] = rewards
            result["eval_mean_reward"] = sum(rewards) / len(rewards) if rewards else 0.0
            result["eval_tests_passed"] = passed
            result["eval_tests_total"] = totals

            # Per-run accuracy: passed / total for each run
            accs = [
                p / t if t > 0 else 0.0
                for p, t in zip(passed, totals)
            ]
            result["eval_accs"] = accs
            result["eval_mean_acc"] = sum(accs) / len(accs) if accs else 0.0

        return result

    def _record_result(self, result: dict) -> None:
        """Append result to CSV."""
        csv_path = self.results_csv
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "timestamp", "task", "status", "elapsed_sec",
            "creator_model", "evaluator_model", "planner_model",
            "eval_runs", "eval_mean_reward", "eval_mean_acc",
            "eval_rewards", "eval_accs",
            "eval_tests_passed", "eval_tests_total",
        ]

        write_header = not csv_path.exists()
        with open(csv_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            if write_header:
                writer.writeheader()
            writer.writerow(result)

        _print(f"[pipeline] Result recorded: {csv_path}")
