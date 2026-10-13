"""Time generation on the stress project (2,000 interfaces; target < 10 s).
Usage: python -m tools.bench_generate"""

import time

from harness_design_studio.core.commands import apply_ops
from harness_design_studio.core.generate.engine import plan_generation
from harness_design_studio.core.samples import stress_project
from harness_design_studio.core.verify import verify_project


def main() -> None:
    p = stress_project()
    t0 = time.perf_counter()
    plan = plan_generation(p)
    t1 = time.perf_counter()
    apply_ops(p, plan.ops)
    t2 = time.perf_counter()
    report = verify_project(p)
    t3 = time.perf_counter()
    again = plan_generation(p)
    t4 = time.perf_counter()
    print(plan.report.summary())
    print(
        f"plan {t1 - t0:.2f} s, apply {t2 - t1:.2f} s, verify {t3 - t2:.2f} s, replan {t4 - t3:.2f} s"
    )
    print(report.summary(), "| second plan empty:", again.empty)


if __name__ == "__main__":
    main()
