"""파일 정리 도우미 (웹 버전)

파일을 여러 개 올리면 종류별·달별 폴더로 나눈 뒤 zip 파일 하나로 내려받게 해 줍니다.
분류 규칙(문서·엑셀·이미지·압축·기타)은 sort_files.py의 것을 그대로 씁니다.

실행 방법:
  streamlit run app.py
"""

import io
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath

import pandas as pd
import streamlit as st

from sort_files import CATEGORIES, OTHER, category_of

NO_DATE = "날짜모름"
MODES = {
    "확장자별": "예) 문서 / 보고서.docx",
    "확장자 + 월별": "예) 문서 / 2026-03 / 보고서.docx",
    "월별만": "예) 2026-03 / 보고서.docx",
}


def zip_name(info: zipfile.ZipInfo) -> str:
    """zip 안의 파일 이름을 꺼냅니다. 윈도우에서 만든 zip의 한글 이름이 깨지지 않게 고칩니다."""
    name = info.filename
    if not info.flag_bits & 0x800:  # UTF-8 표시가 없으면 윈도우 한글(cp949)로 만든 zip
        try:
            name = name.encode("cp437").decode("cp949")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return PurePosixPath(name).name


def collect(uploads, unzip: bool) -> list[dict]:
    """올린 파일을 꺼내 목록으로 만듭니다. zip은 (원하면) 풀어서 안의 파일을 꺼냅니다."""
    items = []
    for up in uploads:
        data = up.getvalue()
        if unzip and up.name.lower().endswith(".zip"):
            try:
                zf = zipfile.ZipFile(io.BytesIO(data))
            except zipfile.BadZipFile:
                zf = None
            if zf:
                for info in zf.infolist():
                    name = zip_name(info)
                    if info.is_dir() or not name or "__MACOSX" in info.filename or name == ".DS_Store":
                        continue
                    y, m = info.date_time[:2]
                    items.append({"name": name, "data": zf.read(info), "month": f"{y:04d}-{m:02d}"})
                continue
        # 브라우저는 파일을 올릴 때 수정 날짜를 보내 주지 않으므로 날짜를 알 수 없음
        items.append({"name": up.name, "data": data, "month": NO_DATE})
    return items


def plan(items: list[dict], mode: str) -> list[dict]:
    """각 파일이 zip 안의 어느 폴더로 갈지 정합니다. 같은 이름이 겹치면 (2), (3)을 붙입니다."""
    rows, used = [], set()
    for it in sorted(items, key=lambda x: x["name"]):
        cat = category_of(Path(it["name"]), CATEGORIES)
        if mode == "확장자별":
            folder = cat
        elif mode == "확장자 + 월별":
            folder = f"{cat}/{it['month']}"
        else:
            folder = it["month"]
        name, n = it["name"], 2
        stem, suffix = Path(name).stem, Path(name).suffix
        while f"{folder}/{name}".lower() in used:
            name = f"{stem} ({n}){suffix}"
            n += 1
        used.add(f"{folder}/{name}".lower())
        rows.append({"파일 이름": name, "종류": cat, "수정한 달": it["month"],
                     "들어갈 폴더": folder, "_data": it["data"]})
    return rows


def make_zip(rows: list[dict]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in rows:
            zf.writestr(f"{r['들어갈 폴더']}/{r['파일 이름']}", r["_data"])
    return buf.getvalue()


st.set_page_config(page_title="파일 정리 도우미", page_icon="🗂️", layout="wide")
st.title("🗂️ 파일 정리 도우미")
st.write(
    "뒤섞인 파일을 올리면 **종류별·달별 폴더로 나눈 zip 파일**로 만들어 드립니다. "
    "올린 파일은 정리에만 쓰이고 저장되지 않습니다."
)

# ---------- 1단계: 파일 올리기 ----------
st.subheader("① 정리할 파일을 올려 주세요")
uploads = st.file_uploader(
    "파일을 여기로 끌어다 놓거나 'Browse files'를 눌러 고르세요 (여러 개 가능)",
    accept_multiple_files=True,
)
unzip = st.checkbox(
    "zip 파일은 풀어서 안에 든 파일을 정리하기",
    value=True,
    help="끄면 zip 파일 자체를 '압축' 종류로 분류합니다.",
)
st.info(
    "💡 **달별로 나누려면 폴더를 zip으로 묶어서 올리세요.** "
    "파일을 하나씩 올리면 인터넷 브라우저가 '수정한 날짜'를 보내 주지 않아서 "
    f"달을 알 수 없고, 그런 파일은 **'{NO_DATE}'** 폴더로 들어갑니다. "
    "(폴더를 마우스 오른쪽 버튼으로 누르고 '압축 대상 → ZIP 파일'을 고르면 됩니다)"
)

st.subheader("② 어떻게 나눌까요?")
mode = st.radio("분류 기준", list(MODES), captions=list(MODES.values()), index=1)

with st.expander("종류는 이렇게 나눕니다 (펼쳐 보기)"):
    st.table(pd.DataFrame(
        [{"종류": k, "해당 확장자": ", ".join(sorted(v))} for k, v in CATEGORIES.items()]
        + [{"종류": OTHER, "해당 확장자": "위에 없는 나머지 전부"}]
    ))
    st.caption("확장자는 대문자·소문자를 구분하지 않습니다. (.JPG와 .jpg는 같은 '이미지')")

# ---------- 2단계: 버튼 ----------
st.subheader("③ 확인하고 내려받기")
st.caption("먼저 **미리보기**로 결과를 확인한 뒤, 괜찮으면 **분류 실행**을 누르세요.")
col1, col2 = st.columns(2)
preview_clicked = col1.button("👀 미리보기", width="stretch")
run_clicked = col2.button("✅ 분류 실행 (zip 만들기)", type="primary", width="stretch")

# 올린 파일·기준이 바뀌면 예전 결과는 보여주지 않음
signature = (tuple((u.name, u.size) for u in uploads or []), mode, unzip)
if st.session_state.get("signature") != signature:
    st.session_state.pop("result", None)

if preview_clicked or run_clicked:
    if not uploads:
        st.warning("먼저 ①에서 정리할 파일을 올려 주세요.")
    else:
        rows = plan(collect(uploads, unzip), mode)
        if not rows:
            st.info("정리할 파일이 없습니다. (zip 안이 비어 있을 수 있어요)")
        elif preview_clicked:
            st.success(f"파일 {len(rows)}개를 아래처럼 나눌 예정입니다.")
            table = pd.DataFrame(rows).drop(columns="_data")
            st.dataframe(table, width="stretch", hide_index=True, height=450)
        else:
            with st.spinner("zip 파일을 만드는 중..."):
                counts = Counter(r["들어갈 폴더"] for r in rows)
                st.session_state["result"] = (make_zip(rows), counts)
                st.session_state["signature"] = signature

if "result" in st.session_state:
    data, counts = st.session_state["result"]
    st.success(f"완료! 파일 {sum(counts.values())}개를 정리했습니다. 아래 버튼을 눌러 내려받으세요.")
    st.download_button(
        "⬇️ 정리된 파일 내려받기 (분류결과.zip)",
        data=data,
        file_name="분류결과.zip",
        mime="application/zip",
        type="primary",
        on_click="ignore",
    )
    summary = pd.DataFrame(sorted(counts.items()), columns=["폴더", "파일 개수"])
    st.dataframe(summary, width="stretch", hide_index=True)
