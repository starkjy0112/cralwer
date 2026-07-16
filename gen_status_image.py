# -*- coding: utf-8 -*-
"""crawler_status.png 재생성. xlsx 13~56행 크롤러 현황."""
import sqlite3
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

for f in ["AppleGothic", "AppleSDGothicNeo", "Apple SD Gothic Neo",
          "NanumGothic", "Malgun Gothic"]:
    try:
        fm.findfont(f, fallback_to_default=False)
        plt.rcParams["font.family"] = f
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False

# xlsx 13-56행 (실제 매핑)
ROWS = [
    (13, "alio_item", "재정경재부(알리오 원자재)", "sync"),
    (14, "nara", "조달청 나라장터", "sync"),
    (15, "alio", "알리오 국가공사", "sync"),
    (16, "lh", "LH 파트너몰", "정상"),
    (17, "kr", "국가철도공단", "정상"),
    (18, "ekr", "한국농어촌공사", "정상"),
    (19, "gtdc", "강릉관광개발공사", "정상"),
    (20, "gdco", "강원개발공사(nara)", "mirror"),
    (21, "gmdc", "거제해양관광개발공사", "정상"),
    (22, "gndc", "경남개발공사", "정상"),
    (23, "gbdc", "경상북도개발공사", "정상"),
    (24, "ghdc", "김해시도시개발공사", "정상"),
    (25, "dudc", "대구도시개발공사", "정상"),
    (26, "sdco", "새만금개발공사", "정상"),
    (27, "sh", "SH 서울주택도시공사", "정상"),
    (28, "sh_bid", "SH 입찰", "정상"),
    (29, "isdc", "성남도시개발공사", "정상"),
    (30, "isdc_notice", "성남 고시공고", "정상"),
    (31, "jndc", "전남개발공사", "정상"),
    (32, "jbdc", "전북개발공사", "정상"),
    (33, "jpdc", "제주특별자치도개발공사", "정상"),
    (34, "cbdc", "충북개발공사", "정상"),
    (35, "cndc", "충청남도개발공사", "정상"),
    (36, "ttdc", "통영관광개발공사", "정상"),
    (37, "gcuc", "과천도시공사", "정상"),
    (38, "gmcc", "광주광역시도시공사", "정상"),
    (39, "gh", "GH 경기주택도시공사", "정상"),
    (40, "gys", "고양도시관리공사", "정상"),
    (41, "guriuc", "구리도시공사", "정상"),
    (42, "gunpouc", "군포도시공사", "정상"),
    (43, "ncuc", "남양주도시공사", "정상"),
    (44, "djuc", "당진도시공사", "정상"),
    (45, "dcco", "대전도시공사", "정상"),
    (46, "bmc", "부산도시공사", "정상"),
    (47, "best", "부천도시공사", "정상"),
    (48, "suwonudc", "수원도시공사", "정상"),
    (49, "shsi", "시흥도시공사", "정상"),
    (50, "ansanuc", "안산도시공사", "정상"),
    (51, "auc", "안양도시공사", "정상"),
    (52, "yjuc", "양주도시공사", "정상"),
    (53, "yuc", "용인도시공사", "정상"),
    (54, "uuc", "의왕도시공사", "정상"),
    (55, "uiuc", "의정부도시공사", "정상"),
    (56, "umca", "울산도시공사", "정상"),
]

def get_status():
    con = sqlite3.connect("/Users/teramime/Documents/project_16/crawlers.db")
    cur = con.cursor()
    cur.execute("""
        SELECT crawler_id, COUNT(*), MAX(created_at)
        FROM crawl_data GROUP BY crawler_id
    """)
    stat = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
    con.close()
    return stat

STAT = get_status()

cols = ["행", "크롤러ID", "기관", "DB 건수", "최근 수집", "상태"]
data = []
for row_num, cid, name, policy in ROWS:
    cnt, last = STAT.get(cid, (0, "-"))
    if isinstance(last, str) and " " in last:
        last = last.split(" ")[0]
    cnt_str = f"{cnt:,}" if cnt else "0"
    data.append([str(row_num), cid, name, cnt_str, last, policy])

fig, ax = plt.subplots(figsize=(11, 15))
ax.axis("off")

TITLE = (f"크롤러 현황 (2026-07-10 {datetime.now().strftime('%H:%M')} 기준)\n"
         f"13~15: 알리오/나라 sync / 20: nara 미러 / 16~56: 누적 보관")
ax.set_title(TITLE, fontsize=11, pad=14)

table = ax.table(
    cellText=data,
    colLabels=cols,
    cellLoc="center",
    loc="upper center",
    colWidths=[0.05, 0.14, 0.28, 0.14, 0.14, 0.10],
)
table.auto_set_font_size(False)
table.set_fontsize(8)
table.scale(1.0, 1.35)

for i in range(len(cols)):
    c = table[0, i]
    c.set_facecolor("#dddddd")
    c.set_text_props(fontweight="bold")

POLICY_COLOR = {
    "sync": "#ffe8b3",
    "mirror": "#ffd9d9",
    "저장": "#e0f2ff",
    "정상": "#e6ffe6",
}
for i, row in enumerate(data, start=1):
    p = row[5]
    color = POLICY_COLOR.get(p, "#ffffff")
    for j in range(len(cols)):
        table[i, j].set_facecolor(color)

fig.text(
    0.5, 0.02,
    "정책: 초록 | sync (전체+만료삭제): 노랑 | mirror (nara미러): 빨강 | 저장: 하늘",
    ha="center", fontsize=8,
)

plt.savefig(
    "/Users/teramime/Documents/project_16/crawler_status.png",
    dpi=180, bbox_inches="tight", facecolor="white",
)
print("완료: crawler_status.png")
