"""Прогон золотого набора evals."""

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.core import Agent
from evals.tasks import TASKS


def _count_tools(agent: Agent) -> int:
    """Считает вызовы инструментов по истории агента."""
    return sum(
        len(m.get("tool_calls") or [])
        for m in agent.history.messages
        if m.get("role") == "assistant"
    )


def run_one_task(task: dict, work_dir: Path) -> dict:
    name = task["name"]
    sandbox = work_dir / "sandbox"
    sandbox.mkdir(exist_ok=True)

    prepare = task.get("prepare")
    if prepare:
        prepare(sandbox)

    old_cwd = Path.cwd()
    try:
        os.chdir(work_dir)  # агент будет видеть work_dir как корень

        agent = Agent(system_prompt=None)

        answer_parts: list[str] = []
        started = time.time()
        try:
            for chunk in agent.chat(task["prompt"], show_tool_calls=False):
                answer_parts.append(chunk)
        except Exception as e:
            answer_parts.append(f"\n[AGENT ERROR: {e}]")
        elapsed = time.time() - started

        answer = "".join(answer_parts)
        n_steps = _count_tools(agent)
        
        # СОХРАНЯЕМ ИСТОРИЮ ДЛЯ ОТЛАДКИ (пригодится, если запускать с --keep)
        try:
            run_suffix = f"run_{int(time.time())}_{id(agent) % 1000}"
            agent.history.save(work_dir / f"history_{name}_{run_suffix}.json")
        except Exception as e:
            print(f"   [warn] could not save history: {e}")

    finally:
        os.chdir(old_cwd)

    try:
        ok, detail = task["check"](agent, sandbox, answer)
    except Exception as e:
        ok, detail = False, f"checker crashed: {e}"

    return {
        "name": name,
        "category": task["category"],
        "ok": ok,
        "detail": detail,
        "elapsed": elapsed,
        "steps": n_steps,
        "answer_preview": answer[:200].replace("\n", " "),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=1, help="Прогонов на задачу (для pass^k)")
    parser.add_argument("--only", type=str, default="", help="Только эти задачи (через запятую)")
    parser.add_argument("--category", type=str, default="", help="Только эта категория")
    parser.add_argument("--keep", action="store_true", help="Не удалять work_dir (для отладки)")
    args = parser.parse_args()

    tasks = TASKS
    if args.only:
        wanted = {s.strip() for s in args.only.split(",")}
        tasks = [t for t in tasks if t["name"] in wanted]
    if args.category:
        tasks = [t for t in tasks if t["category"] == args.category]

    if not tasks:
        print("Нет задач после фильтрации.")
        return

    work_dir = Path(tempfile.mkdtemp(prefix="agent_evals_"))
    print(f"Work dir: {work_dir}\n")

    results: dict[str, list[bool]] = {t["name"]: [] for t in tasks}
    details: dict[str, list[str]] = {t["name"]: [] for t in tasks}
    timings: dict[str, list[float]] = {t["name"]: [] for t in tasks}
    steps_count: dict[str, list[int]] = {t["name"]: [] for t in tasks}

    total_runs = len(tasks) * args.k
    run_i = 0
    started_all = time.time()

    for k_i in range(args.k):
        for task in tasks:
            run_i += 1
            print(f"[{run_i}/{total_runs}] {task['name']} (run {k_i+1}/{args.k})...", end=" ", flush=True)

            sandbox = work_dir / "sandbox"
            if sandbox.exists():
                shutil.rmtree(sandbox)
            sandbox.mkdir()

            result = run_one_task(task, work_dir)
            results[task["name"]].append(result["ok"])
            details[task["name"]].append(result["detail"])
            timings[task["name"]].append(result["elapsed"])
            steps_count[task["name"]].append(result["steps"])

            status = "✅" if result["ok"] else "❌"
            print(f"{status} {result['elapsed']:.1f}s, {result['steps']} tools")
            if not result["ok"]:
                print(f"   └─ {result['detail']}")

    print("\n" + "=" * 70)
    print("ОТЧЁТ")
    print("=" * 70)

    by_category: dict[str, list[bool]] = {}
    total_ok = 0
    total_runs_done = 0

    for task in tasks:
        name = task["name"]
        cat = task["category"]
        oks = results[name]
        n_ok = sum(oks)
        n_total = len(oks)
        total_ok += n_ok
        total_runs_done += n_total

        by_category.setdefault(cat, []).extend(oks)

        pass_at_1 = n_ok / n_total
        pass_k = "n/a" if n_total == 1 else ("100%" if n_ok == n_total else "0%")
        avg_time = sum(timings[name]) / n_total
        avg_steps = sum(steps_count[name]) / n_total
        status = "✅" if n_ok == n_total else ("⚠️" if n_ok > 0 else "❌")
        print(
            f"{status} {name:25s} "
            f"pass@1={pass_at_1:5.0%}  pass^k={pass_k:>5s}  "
            f"avg={avg_time:5.1f}s  tools={avg_steps:.1f}"
        )

    print("-" * 70)
    for cat, oks in by_category.items():
        n_ok = sum(oks)
        n_total = len(oks)
        print(f"  {cat:10s} {n_ok}/{n_total}  ({n_ok/n_total:.0%})")

    print("-" * 70)
    print(f"  TOTAL      {total_ok}/{total_runs_done}  ({total_ok/total_runs_done:.0%})")

    if args.keep:
        print(f"\nWork dir сохранён: {work_dir}")
        print("Истории диалогов лежат в history_<task_name>.json")
    else:
        shutil.rmtree(work_dir, ignore_errors=True)
        print(f"\nWork dir удалён: {work_dir}")

    total_time = time.time() - started_all
    print(f"Общее время: {total_time:.1f}s")

    sys.exit(0 if total_ok == total_runs_done else 1)


if __name__ == "__main__":
    main()