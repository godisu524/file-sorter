"""mixed 폴더의 파일을 확장자별로 분류해 sorted 폴더에 복사합니다.

구조: sorted/<분류>/<YYYY-MM>/<파일>
- 원본은 복사만 하고 건드리지 않습니다.
- 날짜 폴더는 파일의 수정 날짜 기준입니다.

사용법:
  python sort_files.py                      # mixed 폴더 → sorted 폴더
  python sort_files.py "다른\\폴더"          # 다른 폴더 → 그 옆의 sorted 폴더
  python sort_files.py 폴더 --dst 결과폴더
  python sort_files.py 폴더 --rule 문서=docx,pdf --rule 이미지=jpg,png
"""

import argparse
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")  # 오류 메시지도 한글이 깨지지 않게

BASE = Path(__file__).resolve().parent

# --rule을 주지 않았을 때 쓰는 기본 규칙
CATEGORIES = {
    "문서": {"docx", "hwp", "pdf", "txt", "pptx"},
    "엑셀": {"xlsx", "xls", "csv"},
    "이미지": {"jpg", "jpeg", "png", "gif"},
    "압축": {"zip", "7z"},
}
OTHER = "기타"


def parse_rules(rules: list[str]) -> dict[str, set[str]]:
    """'문서=docx,pdf' 형식의 글을 {'문서': {'docx', 'pdf'}}로 바꿉니다."""
    categories = {}
    for rule in rules:
        name, _, exts = rule.partition("=")
        if not name.strip() or not exts.strip():
            sys.exit(f"규칙 형식이 잘못됐습니다: {rule!r} (예: 문서=docx,pdf)")
        categories[name.strip()] = {
            e.strip().lower().lstrip(".") for e in exts.split(",") if e.strip()
        }
    return categories


def category_of(path: Path, categories: dict[str, set[str]]) -> str:
    ext = path.suffix.lower().lstrip(".")  # .JPG와 .jpg를 같게 취급
    for name, exts in categories.items():
        if ext in exts:
            return name
    return OTHER


def main() -> None:
    parser = argparse.ArgumentParser(description="파일을 확장자·수정 월별로 분류해 복사")
    parser.add_argument("src", nargs="?", default=BASE / "mixed", type=Path,
                        help="분류할 폴더 (기본: 이 스크립트 옆의 mixed)")
    parser.add_argument("--dst", type=Path,
                        help="결과 폴더 (기본: 분류할 폴더 옆의 sorted)")
    parser.add_argument("--rule", action="append", default=[],
                        help="분류 규칙, 예: 문서=docx,pdf (여러 번 사용 가능)")
    args = parser.parse_args()

    src = args.src.resolve()
    dst = (args.dst or src.parent / "sorted").resolve()
    categories = parse_rules(args.rule) if args.rule else CATEGORIES
    order = list(categories) + [OTHER]

    if not src.is_dir():
        sys.exit(f"폴더를 찾을 수 없습니다: {src}")
    if dst == src:
        sys.exit("결과 폴더가 원본 폴더와 같습니다. --dst로 다른 폴더를 지정하세요.")

    print(f"원본: {src}")
    print(f"결과: {dst}\n")

    counts = Counter()
    for f in sorted(src.iterdir()):
        if not f.is_file():
            continue
        cat = category_of(f, categories)
        month = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m")
        target_dir = dst / cat / month
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target_dir / f.name)  # copy2: 수정 날짜도 그대로 유지
        counts[(cat, month)] += 1

    # 결과 표
    print(f"{'분류':<6}{'월':<10}{'개수':>5}")
    print("-" * 24)
    for cat in order:
        months = sorted(m for c, m in counts if c == cat)
        for m in months:
            print(f"{cat:<6}{m:<10}{counts[(cat, m)]:>5}")
        if months:
            subtotal = sum(counts[(cat, m)] for m in months)
            print(f"{'':<6}{'(소계)':<10}{subtotal:>5}")
            print("-" * 24)
    print(f"{'합계':<16}{sum(counts.values()):>5}")


if __name__ == "__main__":
    main()
