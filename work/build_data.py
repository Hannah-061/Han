# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas"]
# ///
"""
把 data/ 的三個 CSV 整理成網頁可以直接載入的 docs/data.js。

用法：uv run work/build_data.py
網頁用 <script src="data.js"></script> 載入後，資料在 window.BI_DATA：

  dims        各維度的值清單（學期、學院、系所、學位別、性別、休學原因）
  enrollment  { cols, rows }：rows 每列是 [學期, 學院, 系所, 學位別, 性別, 在學人數]，
              前 5 欄是 dims 裡的索引
  leave       { cols, rows }：rows 每列是 [學期, 學院, 系所, 學位別, 性別, 休學原因,
              學期間休學人數, 學期底休學狀態人數]，前 6 欄是 dims 裡的索引
  depts       { 系所: { college, aliases: [舊名稱...] } }
"""
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "docs" / "data.js"

DIMS = ["semester", "college", "dept", "degree", "gender", "reason"]
ORDER = {"degree": ["學士", "碩士", "博士"], "gender": ["女", "男"]}


def read(name):
    return pd.read_csv(DATA / name, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def main():
    enr = read("enrollment.csv")
    lev = read("leave.csv")
    mapping = read("dept_mapping.csv")
    enr["count"] = enr["count"].astype(int)
    lev[["new_leave", "on_leave_end"]] = lev[["new_leave", "on_leave_end"]].astype(int)

    # 各維度的值清單；學期照時間排序，學位別、性別用固定順序，其他照第一次出現的順序
    dims = {}
    for d in DIMS:
        seen = pd.concat([df[d] for df in (enr, lev) if d in df]).drop_duplicates().tolist()
        dims[d] = ORDER.get(d) or (sorted(seen) if d == "semester" else seen)
        assert set(seen) <= set(dims[d]), f"{d} 有未定義的值：{set(seen) - set(dims[d])}"

    def encode(df, keys, values):
        g = df.groupby(keys, as_index=False)[values].sum()
        for k in keys:
            g[k] = g[k].map({v: i for i, v in enumerate(dims[k])})
        return {"cols": keys + values, "rows": g[keys + values].values.tolist()}

    keys = ["semester", "college", "dept", "degree", "gender"]
    out = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "dims": dims,
        "enrollment": encode(enr, keys, ["count"]),
        "leave": encode(lev, keys + ["reason"], ["new_leave", "on_leave_end"]),
        "depts": {
            r.dept: {"college": r.college, "aliases": [a for a in r.aliases.split(";") if a]}
            for r in mapping.itertuples()
        },
    }

    OUT.parent.mkdir(exist_ok=True)
    body = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(f"// 由 work/build_data.py 產生，請勿手動修改\nwindow.BI_DATA = {body};\n", encoding="utf-8")

    # 核對：加總前後人數一致，且 114-1 在學人數 = 10035
    def total(part, col):
        i = out["enrollment" if part == "e" else "leave"]["cols"].index(col)
        return sum(r[i] for r in out["enrollment" if part == "e" else "leave"]["rows"])

    assert total("e", "count") == enr["count"].sum()
    assert total("l", "new_leave") == lev["new_leave"].sum()
    assert total("l", "on_leave_end") == lev["on_leave_end"].sum()
    s = dims["semester"].index("114-1")
    n114 = sum(r[-1] for r in out["enrollment"]["rows"] if r[0] == s)
    print(f"{'✅' if n114 == 10035 else '❌'} 114-1 在學人數合計：{n114}（應為 10035）")
    print(f"在學 {len(out['enrollment']['rows'])} 列、休學 {len(out['leave']['rows'])} 列、系所 {len(out['depts'])} 個")
    print(f"→ {OUT.relative_to(ROOT)}（{OUT.stat().st_size / 1024:.1f} KB）")
    assert n114 == 10035


if __name__ == "__main__":
    main()
