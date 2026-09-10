"""OpenSkill Evaluation Runner.

Runs harbor eval (N runs) on a task with existing skills, records results to CSV.
No skill creation — just evaluation of what's already in environment/skills/.

Usage:
    uv run python -m libs.openskill.run_eval \
        --tasks simpo-code-reproduction \
        --tasks-dir tasks-evolved \
        --eval-runs 5 \
        --eval-agent claude-code \
        --model anthropic/claude-opus-4-6 \
        --results-csv results/eval_results.csv
"""

from __future__ import annotations

import argparse
import csv
import logging
import time
from datetime import datetime
from pathlib import Path

# Re-use the existing pipeline machinery
from .pipeline import (
    _EVAL_AGENT_IMPORT,
    REPO_ROOT,
    _check_completion,
    _run_harbor,
)

logger = logging.getLogger(__name__)


def _print(msg: str) -> None:
    try:
        print(msg, flush=True)
    except BrokenPipeError:
        pass


def _record_result(result: dict, csv_path: Path) -> None:
    """Append result to CSV."""
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

    _print(f"[eval] Result recorded: {csv_path}")


def run_eval(
    task_name: str,
    tasks_dir: Path,
    eval_runs: int = 5,
    eval_agent: str = "claude-code",
    model: str = "anthropic/claude-opus-4-6",
    results_csv: Path | None = None,
    timeout_multiplier: float = 3.0,
    agent_kwargs: dict | None = None,
) -> dict:
    """Run N evaluation runs on a task and record results."""

    task_dir = tasks_dir / task_name
    if not task_dir.exists():
        raise FileNotFoundError(f"Task not found: {task_dir}")

    env_dir = task_dir / "environment"
    skills_dir = env_dir / "skills"

    # Check skills exist
    skill_dirs = list(skills_dir.glob("evo-*")) if skills_dir.exists() else []
    if not skill_dirs:
        _print(f"[eval] WARNING: No evo-* skills found in {skills_dir}")

    eval_agent_import = _EVAL_AGENT_IMPORT[eval_agent]
    start_time = time.time()

    _print(f"\n{'='*60}")
    _print(f"[eval] Task: {task_name}")
    _print(f"[eval] Skills: {[d.name for d in skill_dirs]}")
    _print(f"[eval] Agent: {eval_agent} ({model})")
    _print(f"[eval] Runs: {eval_runs}")
    _print(f"{'='*60}")

    eval_results = []
    for run_idx in range(eval_runs):
        _print(f"\n[eval] Run {run_idx + 1}/{eval_runs}")

        # Include model short name to avoid job dir collisions when
        # multiple models evaluate the same task in parallel.
        model_short = model.split("/")[-1].lower().replace(".", "")
        job_name = (
            f"eval-{task_name}-{model_short}-"
            f"run{run_idx + 1}-{int(time.time()) % 10000:04d}"
        )

        result = _run_harbor(
            task_path=task_dir,
            model=model,
            agent_import_path=eval_agent_import,
            job_name=job_name,
            force_build=(run_idx == 0),
            agent_kwargs=agent_kwargs,
            timeout_multiplier=timeout_multiplier,
        )

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
        eval_results.append(run_result)

        _print(
            f"[eval] Run {run_idx + 1}: "
            f"{completion['tests_passed']}/{completion['tests_total']} tests, "
            f"reward={completion['reward']}"
        )

        # Docker cleanup between runs
        try:
            import subprocess
            subprocess.run(
                ["docker", "container", "prune", "-f"],
                capture_output=True, timeout=30,
            )
        except Exception:
            pass

    # Compute summary
    elapsed = time.time() - start_time
    rewards = [r["reward"] for r in eval_results if r["reward"] is not None]
    passed = [r["tests_passed"] for r in eval_results]
    totals = [r["tests_total"] for r in eval_results]
    accs = [p / t if t > 0 else 0.0 for p, t in zip(passed, totals)]

    summary = {
        "timestamp": datetime.now().isoformat(),
        "task": task_name,
        "status": "completed",
        "elapsed_sec": elapsed,
        "creator_model": model,
        "evaluator_model": model,
        "planner_model": model,
        "eval_runs": len(eval_results),
        "eval_mean_reward": sum(rewards) / len(rewards) if rewards else 0.0,
        "eval_mean_acc": sum(accs) / len(accs) if accs else 0.0,
        "eval_rewards": rewards,
        "eval_accs": accs,
        "eval_tests_passed": passed,
        "eval_tests_total": totals,
    }

    _print(f"\n[eval] Done: {task_name} in {elapsed:.0f}s")
    _print(f"[eval] Mean reward: {summary['eval_mean_reward']:.4f}")
    _print(f"[eval] Mean acc:    {summary['eval_mean_acc']:.4f}")
    _print(f"[eval] Per-run:     {eval_results}")

    # Record to CSV
    if results_csv:
        _record_result(summary, results_csv)

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="OpenSkill Evaluation Runner",
    )
    parser.add_argument(
        "--tasks", nargs="+", required=True,
        help="Task name(s) to evaluate",
    )
    parser.add_argument(
        "--tasks-dir",
        type=Path,
        default=REPO_ROOT / "tasks-evolved",
        help="Path to tasks directory (default: tasks-evolved, which ships the evolved skills)",
    )
    parser.add_argument(
        "--eval-runs", type=int, default=5,
        help="Number of evaluation runs per task",
    )
    parser.add_argument(
        "--eval-agent",
        choices=["terminus-2", "claude-code", "claude-code-bedrock", "codex"],
        default="claude-code",
        help="Evaluation agent type",
    )
    parser.add_argument(
        "--model",
        default="anthropic/claude-opus-4-6",
        help="Model for evaluation agent",
    )
    parser.add_argument(
        "--timeout-multiplier", type=float, default=None,
        help="Multiplier applied to task timeouts (env build, agent, verifier)",
    )
    parser.add_argument(
        "--results-csv",
        type=Path,
        default=REPO_ROOT / "results" / "eval_results.csv",
        help="Path to results CSV",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    results = []
    for task_name in args.tasks:
        try:
            result = run_eval(
                task_name=task_name,
                tasks_dir=args.tasks_dir,
                eval_runs=args.eval_runs,
                eval_agent=args.eval_agent,
                model=args.model,
                results_csv=args.results_csv,
                timeout_multiplier=args.timeout_multiplier,
            )
            results.append(result)
        except Exception as e:
            _print(f"\n[eval] FAILED: {task_name}: {e}")
            import traceback
            traceback.print_exc()
            results.append({"task": task_name, "status": "error", "error": str(e)})

    # Summary
    _print(f"\n{'='*60}")
    _print("[eval] Summary")
    _print(f"{'='*60}")
    for r in results:
        reward = r.get("eval_mean_reward", "N/A")
        acc = r.get("eval_mean_acc", "N/A")
        if isinstance(reward, float):
            _print(f"  {r['task']:40s}  reward={reward:.3f}  acc={acc:.3f}")
        else:
            _print(f"  {r['task']:40s}  {r.get('status', 'unknown')}")


if __name__ == "__main__":
    main()
