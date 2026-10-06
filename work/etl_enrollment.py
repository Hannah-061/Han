# /// script
# requires-python = ">=3.10"
# dependencies = ["xlrd", "pandas"]
# ///
"""
把 114-1 在學生人數統計表（.xls）轉成整齊的 CSV。

用法：uv run work/etl_enrollment.py
輸出：work/enrollment_114-1.csv（UTF-8 with BOM）
"""
import re
from pathlib import Path

import pandas as pd
import xlrd

ROOT = Path(__file__).resolve().parent.parent
SRC = next((ROOT / "東華大學統計資料" / "在學人數統計表").glob("114-1*.xls"))
OUT = ROOT / "work" / "enrollment_114-1.csv"

COL_COLLEGE, COL_DEPT = 1, 2
COL_F, COL_M = 5, 6  # 「總計」底下的女、男

# 「X 合計N」區段標題 → 學制
SECTION = {"博士班": "博士班", "碩士班": "碩士班", "碩專班": "碩士在職專班", "學士班": "學士班"}


def fill_column(sheet, col, rows):
    """把合併儲存格的值填到整個合併範圍。

    報表裡偶爾有空白格沒被併進任何範圍（例如物理學系的「應用物理博士班一般組」
    那列，系所格是空的、卻在材料系的合併範圍外），這種孤兒格歸給下一個有名字的系所。
    """
    vals = {r: str(sheet.cell_value(r, col)).strip() for r in rows}
    for r0, r1, c0, c1 in sheet.merged_cells:
        if c0 <= col < c1:
            for r in range(r0, r1):
                if r in vals:
                    vals[r] = str(sheet.cell_value(r0, col)).strip()
    nxt = ""
    for r in reversed(rows):
        if vals[r]:
            nxt = vals[r]
        else:
            print(f"⚠️ 第 {r + 1} 列第 {col + 1} 欄空白且不在合併範圍內，歸給下一個：{nxt}")
            vals[r] = nxt
    return vals


def num(v):
    return int(v) if v not in ("", None) else 0


def main():
    sheet = xlrd.open_workbook(SRC, formatting_info=True).sheet_by_index(0)

    # 找出資料列：落在「X 合計N」區段內、到「備註」為止
    data_rows, program = [], {}
    current = None
    for r in range(sheet.nrows):
        head = str(sheet.cell_value(r, 0)).strip()
        if head.startswith("備註"):
            break
        m = re.match(r"(\S+)\s*合計\d", head)
        if m:
            current = SECTION[m.group(1)]
            continue
        if current and str(sheet.cell_value(r, COL_DEPT)).strip() + str(sheet.cell_value(r, 3)).strip():
            data_rows.append(r)
            program[r] = current

    college = fill_column(sheet, COL_COLLEGE, data_rows)
    dept = fill_column(sheet, COL_DEPT, data_rows)

    records = []
    for r in data_rows:
        base = dict(
            college=re.sub(r"[（(].*?[)）]", "", college[r]).strip(),
            dept_raw=dept[r],
            program_raw=program[r],
        )
        records.append({**base, "gender": "女", "count": num(sheet.cell_value(r, COL_F))})
        records.append({**base, "gender": "男", "count": num(sheet.cell_value(r, COL_M))})

    df = (
        pd.DataFrame(records)
        .groupby(["college", "dept_raw", "program_raw", "gender"], sort=False, as_index=False)["count"]
        .sum()
    )
    OUT.parent.mkdir(exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"✅ {len(df)} 列，總人數 {df['count'].sum()} → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
