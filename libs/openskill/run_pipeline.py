"""CLI entry point for the OpenSkill pipeline.

Usage:
    # Full pipeline: knowledge acquisition -> skill evolution -> evaluation
    python -m libs.openskill.run_pipeline \
        --tasks <task-name> \
        --eval-runs 5

    # Skip evaluation (just evolve skills)
    python -m libs.openskill.run_pipeline \
        --tasks <task-name> \
        --eval-runs 0
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure repo root is on path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from libs.openskill.pipeline import OpenSkillPipeline  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        description="OpenSkill pipeline: knowledge acquisition, skill evolution, evaluation",
    )

    parser.add_argument(
        "--tasks", nargs="+", required=True,
        help="Task names to run (space-separated)",
    )
    parser.add_argument(
        "--planner-model", default="anthropic/claude-opus-4-6",
        help="LLM model for Agent Planner (default: claude-opus-4-6)",
    )
    parser.add_argument(
        "--creator-model", default="anthropic/claude-opus-4-6",
        help="LLM model for Skill Creator agent (default: claude-opus-4-6)",
    )
    parser.add_argument(
        "--evaluator-model", default="anthropic/claude-opus-4-6",
        help="LLM model for Evaluation agent (default: claude-opus-4-6)",
    )
    parser.add_argument(
        "--eval-agent", choices=["terminus-2", "claude-code", "claude-code-bedrock", "codex"],
        default="claude-code",
        help="Agent harness for evaluation (default: claude-code)",
    )
    parser.add_argument(
        "--surrogate-dr-agent", default="gemini-3.1-flash-lite-preview",
        help="Gemini model for verification research (default: gemini-3.1-flash-lite-preview)",
    )
    parser.add_argument(
        "--dr-agent", default="deep-research-pro-preview-12-2025",
        help="Gemini DR agent model (default: deep-research-pro-preview-12-2025)",
    )
    parser.add_argument(
        "--eval-runs", type=int, default=5,
        help="Number of evaluation runs (default: 5, 0=skip eval)",
    )
    parser.add_argument(
        "--source-tasks-dir", type=Path, default=None,
        help="Source clean tasks directory (default: <repo>/tasks)",
    )
    parser.add_argument(
        "--workspace-dir", type=Path, default=None,
        help="Working directory for pipeline (default: <repo>/workspace)",
    )
    parser.add_argument(
        "--no-force-build", action="store_true",
        help="Don't force Docker rebuild",
    )
    # Ablation flags for DR / search components
    parser.add_argument(
        "--disable-dr", action="store_true",
        help="Disable main Deep Research (Step 2: background.md generation)",
    )
    parser.add_argument(
        "--disable-surrogate-dr", action="store_true",
        help="Disable verification research (Step 2c)",
    )
    parser.add_argument(
        "--disable-targeted-dr", action="store_true",
        help="Disable targeted DR on surrogate failure",
    )
    args = parser.parse_args()

    pipeline = OpenSkillPipeline(
        planner_model=args.planner_model,
        creator_model=args.creator_model,
        evaluator_model=args.evaluator_model,
        eval_agent=args.eval_agent,
        surrogate_dr_agent=args.surrogate_dr_agent,
        dr_agent=args.dr_agent,
        eval_runs=args.eval_runs,
        source_tasks_dir=args.source_tasks_dir,
        workspace_dir=args.workspace_dir,
        force_build=not args.no_force_build,
        enable_dr=not args.disable_dr,
        enable_surrogate_dr=not args.disable_surrogate_dr,
        enable_targeted_dr=not args.disable_targeted_dr,
    )

    print(f"{'='*60}")
    print("OpenSkill Pipeline")
    print(f"{'='*60}")
    print(f"Tasks:            {args.tasks}")
    print(f"Planner model:    {args.planner_model}")
    print(f"Creator model:    {args.creator_model}")
    print(f"Evaluator model:  {args.evaluator_model}")
    print(f"Eval agent:       {args.eval_agent}")
    print(f"DR agent:         {args.dr_agent}")
    print(f"Eval runs:        {args.eval_runs}")
    print(f"Surrogate DR:     {args.surrogate_dr_agent}")
    # Ablation flags
    disabled = []
    if args.disable_dr:
        disabled.append("DR")
    if args.disable_surrogate_dr:
        disabled.append("Surrogate-DR")
    if args.disable_targeted_dr:
        disabled.append("Targeted-DR")
    if disabled:
        print(f"DISABLED:         {', '.join(disabled)}")
    print(f"{'='*60}\n")

    all_results = []
    for task_name in args.tasks:
        try:
            result = pipeline.run_task(task_name)
            all_results.append(result)
        except Exception as e:
            print(f"\n[ERROR] Task {task_name} failed: {e}")
            import traceback
            traceback.print_exc()
            all_results.append({
                "task": task_name,
                "status": "error",
                "error": str(e),
            })

    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for r in all_results:
        task = r.get("task", "?")
        status = r.get("status", "?")
        mean_reward = r.get("eval_mean_reward", "N/A")
        mean_acc = r.get("eval_mean_acc", "N/A")
        elapsed = r.get("elapsed_sec", 0)
        print(f"  {task}: status={status}, mean_reward={mean_reward}, mean_acc={mean_acc}, elapsed={elapsed:.0f}s")
    print(f"{'='*60}")

    # Save full results as JSON
    results_json = REPO_ROOT / "results" / "pipeline_results.json"
    results_json.parent.mkdir(parents=True, exist_ok=True)
    with open(results_json, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nFull results: {results_json}")


if __name__ == "__main__":
    main()
