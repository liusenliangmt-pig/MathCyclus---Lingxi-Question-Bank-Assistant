from pathlib import Path


def main():
    text = Path("question_bank_app.py").read_text(encoding="utf-8")
    checks = {
        "sidebar uses clamp width": "width: clamp(280px, 19vw, 300px)" in text,
        "sidebar min width 280": "min-width: 280px" in text,
        "sidebar max responsive": "max-width: min(300px, 92vw)" in text,
        "sidebar hides horizontal overflow": "overflow-x: hidden" in text,
        "normal word break": "word-break: normal" in text,
        "pre-line nav labels": "white-space: pre-line" in text,
        "radio row stretches": "> label > div:nth-child(2) > div:first-child" in text
        and "align-items: stretch" in text,
        "radio empty icon cell collapses": "flex: 0 0 0" in text,
        "radio text cell expands": "> div:first-child > div:last-child" in text
        and "flex: 1 1 auto" in text,
        "mobile media query": "@media (max-width: 720px)" in text,
        "old 110px sidebar removed": "min-width: 110px" not in text and "max-width: 110px" not in text,
    }
    failed = [name for name, ok in checks.items() if not ok]
    for name, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'} {name}")
    if failed:
        raise SystemExit("CSS smoke failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()
