"""Summarise usability sessions: success, time, wrong clicks, SUS, and the priority bugs.
Usage: python -m tools.usability_summary results.csv sus.csv   (formats: docs/usability/)"""

import csv
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

SUCCESS_TARGET = 0.9
SUS_TARGET = 80.0
TIME_LIMITS = {
    "T1": 900,
    "T2": 300,
    "T3": 480,
    "T4": 480,
    "T5": 30,
    "T6": 600,
    "T7": 600,
    "T8": 480,
}


@dataclass
class TaskSummary:
    task: str
    n: int
    success: float
    median_seconds: float
    wrong_clicks: float
    unclear: int

    @property
    def below_target(self) -> bool:
        limit = TIME_LIMITS.get(self.task)
        return self.success < SUCCESS_TARGET or (limit is not None and self.median_seconds > limit)


def sus_score(answers: list[int]) -> float:
    """Standard SUS: odd items score (answer - 1), even items (5 - answer), sum times 2.5."""
    if len(answers) != 10 or any(not 1 <= a <= 5 for a in answers):
        raise ValueError("a SUS questionnaire has ten answers from 1 to 5")
    return 2.5 * sum((a - 1) if k % 2 == 0 else (5 - a) for k, a in enumerate(answers))


def summarise_tasks(rows: list[dict[str, str]]) -> list[TaskSummary]:
    out = []
    for task in sorted({r["task"] for r in rows}):
        mine = [r for r in rows if r["task"] == task]
        out.append(
            TaskSummary(
                task, len(mine), sum(int(r["success"]) for r in mine) / len(mine),
                statistics.median(float(r["seconds"]) for r in mine),
                statistics.mean(float(r["wrong_clicks"]) for r in mine),
                sum(int(r["unclear_remarks"]) for r in mine),
            )
        )  # fmt: skip
    return out


def read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def report(results: list[dict[str, str]], sus_rows: list[dict[str, str]]) -> tuple[str, bool]:
    lines = [
        "Task | n | success | median s | wrong clicks | unclear remarks",
        "--- | --- | --- | --- | --- | ---",
    ]
    tasks = summarise_tasks(results)
    for t in tasks:
        lines.append(
            f"{t.task} | {t.n} | {t.success:.0%} | {t.median_seconds:.0f} | {t.wrong_clicks:.1f} | {t.unclear}"
        )
    scores = [sus_score([int(r[f"q{k}"]) for k in range(1, 11)]) for r in sus_rows]
    sus = statistics.mean(scores) if scores else 0.0
    lines.append(f"\nSUS: {sus:.1f} from {len(scores)} participant(s) (target {SUS_TARGET:.0f})")
    bugs = [t for t in tasks if t.below_target]
    ok = not bugs and sus >= SUS_TARGET
    lines.append("\nPriority bugs (tasks below target):" if bugs else "\nNo task is below target.")
    lines += [f"- {t.task}: success {t.success:.0%}, median {t.median_seconds:.0f} s" for t in bugs]
    if sus < SUS_TARGET and scores:
        lines.append(f"- SUS {sus:.1f} is below {SUS_TARGET:.0f}: read the unclear remarks")
    return "\n".join(lines), ok


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    try:
        text, ok = report(read(Path(sys.argv[1])), read(Path(sys.argv[2])))
    except OSError as exc:
        print(f"error: a file could not be read ({exc.strerror}): {exc.filename}", file=sys.stderr)
        return 2
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
