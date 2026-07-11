"""
run_all.py — Run the full LQOA eval suite and print a pass/fail summary table.

Usage:
  python eval/run_all.py
  # or
  pytest eval/run_all.py -v
"""
import sys
import os
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TESTS = [
    ("Output layer      ", "eval/test_hot_lead.py"),
    ("Governance layer  ", "eval/test_disqualify.py"),
    ("Human gate layer  ", "eval/test_approval_gate.py"),
    ("Fairness layer    ", "eval/test_fairness.py"),
    ("Adversarial layer ", "eval/test_injection.py"),
]

WIDTH = 60


def run_test(label: str, path: str) -> tuple[bool, str]:
    """Run a single pytest file, return (passed, summary_line)."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", path, "-v", "--tb=short", "--no-header"],
        capture_output=True,
        text=True,
        cwd=os.path.join(os.path.dirname(__file__), ".."),
    )
    passed = result.returncode == 0
    # Extract pytest summary line
    lines = result.stdout.splitlines()
    summary = next(
        (l for l in reversed(lines) if l.startswith("PASSED") or "passed" in l or "failed" in l or "error" in l),
        result.stdout[-200:] if result.stdout else result.stderr[-200:],
    )
    return passed, summary


def main():
    print("\n" + "=" * WIDTH)
    print("  LQOA Eval Suite — Results")
    print("=" * WIDTH)

    all_passed = True
    rows = []
    for label, path in TESTS:
        passed, summary = run_test(label, path)
        all_passed = all_passed and passed
        status = "✅ PASS" if passed else "❌ FAIL"
        rows.append((label, status, summary))
        print(f"  {status}  {label}  {path}")

    print("=" * WIDTH)
    if all_passed:
        print("  🎉 ALL TESTS PASSED — Project complete!")
    else:
        print("  ⚠️  Some tests failed. See output above.")
    print("=" * WIDTH + "\n")

    # Detailed output for failures
    for label, status, summary in rows:
        if "FAIL" in status:
            print(f"\n--- Detail: {label} ---")
            print(summary[:500])

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
