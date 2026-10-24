# -*- coding: utf-8 -*-
"""우아분양 정적 사이트 생성기 → _site/.  사용: python scripts/build_site.py  (data/bunyang.json 필요)"""
import sys, json, re, shutil, time, collections, statistics
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import *

SRC = json.loads((ROOT / "data" / "bunyang.json").read_text(encoding="utf-8"))
A = SRC["items"]; COMP = SRC["comp"]; AVG = SRC["avg"]; WIN = SRC["win"]
ASOF = "2020년 2월~2025년 11월 공고분"
PY = 3.3058

def table(heads, rows, num=()):
    th = "".join('<th%s>%s</th>' % (' class="num"' if i in num else "", h) for i, h in enumerate(heads))
    body = "".join("<tr>%s</tr>" % "".join('<td%s>%s</td>' % (' class="num"' if i in num else "", v) for i, v in enumerate(r)) for r in rows)
    return '<div class="tbl-wrap"><table class="tbl"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (th, body)

def chips(items): return '<div class="chips">%s</div>' % "".join('<a class="chip" href="%s">%s</a>' % (u, esc(t)) for t, u in items)
def sl(s): return re.sub(r"[^0-9A-Za-z가-힣]+", "-", s).strip("-") or "x"
def eok(m):
    if m is None: return "-"
    m = int(round(m)); e, r = divmod(m, 10000)
    return ("%d억 %s만원" % (e, "{:,}".format(r)) if r else "%d억원" % e) if e else "%s만원" % "{:,}".format(r)
def dt(s): return s.replace("-", ".") if s else ""
def rng(a): return (dt(a[0]) + (" ~ " + dt(a[1]) if a[1] and a[1] != a[0] else "")) if a and a[0] else ""
NOTE = "분양 정보는 한국부동산원 청약홈 공공데이터(%s)를 정리한 참고용이며 분양가·일정은 변경될 수 있습니다. 청약 전 반드시 청약홈(applyhome.co.kr)의 입주자 모집공고문을 확인하세요. 투자·청약 권유가 아닙니다." % ASOF
SIDO_FULL = {"서울": "서울특별시", "경기": "경기도", "인천": "인천광역시", "부산": "부산광역시", "대구": "대구광역시", "광주": "광주광역시", "대전": "대전광역시", "울산": "울산광역시", "세종": "세종특별자치시", "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도", "전북": "전북특별자치도", "전남": "전라남도", "경북": "경상북도", "경남": "경상남도", "제주": "제주특별자치도"}
SIDOS = list(SIDO_FULL)

# ── 전처리 ──
for a in A:
    a["slug"] = sl(a["name"])[:40] + "-" + a["id"]; a["path"] = "/apt/%s/%s/" % (a["sido"], a["slug"])
    prices = [t["price"] / (t["area"] / PY) for t in a["types"] if t["price"] and t["area"]]
    a["py_max"] = max(prices) if prices else None; a["py_min"] = min(prices) if prices else None
    a["p_max"] = max((t["price"] for t in a["types"] if t["price"]), default=None); a["p_min"] = min((t["price"] for t in a["types"] if t["price"]), default=None)
    a["year"] = a["d_pub"][:4]; a["ym"] = a["d_pub"][:7]
    if a["sg"].endswith("지구"): a["sg"] = ""
    a["builder"] = a["builder"].strip()
A.sort(key=lambda a: (a["d_pub"], a["name"]), reverse=True)
BY_SIDO = collections.defaultdict(list); BY_SG = collections.defaultdict(list); BY_BUILDER = collections.defaultdict(list); BY_YM = collections.defaultdict(list); BY_MOVE = collections.defaultdict(list)
for a in A:
    BY_SIDO[a["sido"]].append(a)
    if a["sg"]: BY_SG[(a["sido"], a["sg"])].append(a)
    if a["builder"]: BY_BUILDER[a["builder"]].append(a)
    BY_YM[a["ym"]].append(a)
    if a["move"]: BY_MOVE[a["move"]].append(a)
def bnorm(b): return re.sub(r"\(주\)|㈜|주식회사|\(유\)", "", b).strip()
BSLUG = {}
used = set()
for b in sorted(BY_BUILDER):
    s = sl(bnorm(b)); n = 2; base = s
    while s in used: s = "%s-%d" % (base, n); n += 1
    used.add(s); BSLUG[b] = s

def arow(a):
    return ['<a href="%s">%s</a>' % (a["path"], esc(a["name"])), esc(a["sido"] + (" " + a["sg"] if a["sg"] else "")), "{:,}세대".format(a["size"]), dt(a["d_pub"]), esc(a["builder"] or "-"), esc(eok(a["p_max"])) if a["p_max"] else "-"]
AH = ["단지", "지역", "공급", "공고일", "시공사", "최고 분양가"]

def flags_text(a):
    f = a["flags"]; out = []
    if f["spec"]: out.append("투기과열지구")
    if f["adj"]: out.append("조정대상지역")
    if f["cap"]: out.append("분양가상한제")
    if f["redev"]: out.append("정비사업(재개발·재건축 등)")
    if f["pub"]: out.append("공공주택지구")
    if f["large"]: out.append("대규모택지개발지구")
    return out

# ───────────────────────── 단지 ─────────────────────────
TN = collections.Counter()
DUPK = collections.Counter((a["name"], a["sido"], a["sg"], a["size"]) for a in A)
def page_apt(a):
    ft = flags_text(a); ty = a["types"]
    k_ = (a["name"], a["sido"], a["sg"], a["size"]); sfx = (" (%s 공고)" % a["d_pub"][:7].replace("-", ".")) if DUPK[k_] > 1 else ""
    nb_sg = [x for x in BY_SG.get((a["sido"], a["sg"]), []) if x is not a][:6] if a["sg"] else []
    nb_b = [x for x in BY_BUILDER.get(a["builder"], []) if x is not a][:5] if a["builder"] else []
    price_txt = ""
    if a["p_max"]:
        price_txt = f" 주택형별 최고 분양가는 {eok(a['p_min'])}~{eok(a['p_max'])}이고 3.3㎡(평)당 약 {a['py_min']:,.0f}~{a['py_max']:,.0f}만원 수준입니다."
    lead = (f"<p class=\"lead\"><b>{esc(a['name'])}</b>은(는) {esc(a['addr'])}에 공급하는 {esc(a['kind'])}({esc(a['detail'])}·{esc(a['sale'])})로 총 <b>{a['size']:,}세대</b>입니다. 모집공고일은 {dt(a['d_pub'])}"
            f"{(', 청약 접수는 ' + rng(a['d_apply'])) if rng(a['d_apply']) else ''}{(', 당첨자 발표는 ' + dt(a['d_win'])) if a['d_win'] else ''}입니다. "
            f"{('시공사 ' + esc(a['builder']) + ', ') if a['builder'] else ''}{('시행사 ' + esc(a['dev']) + ', ') if a['dev'] else ''}{('입주예정은 ' + esc(a['move']) + '입니다.') if a['move'] else ''}{price_txt}</p>")
    sched = [("모집공고", dt(a["d_pub"])), ("특별공급 접수", rng(a["d_sp"])), ("해당지역 1순위", rng(a["d_1h"])), ("경기지역 1순위", rng(a["d_1g"])), ("기타지역 1순위", rng(a["d_1o"])), ("해당지역 2순위", rng(a["d_2h"])), ("청약 접수", rng(a["d_apply"])), ("당첨자 발표", dt(a["d_win"])), ("계약", rng(a["d_con"]))]
    sched = [[k, v] for k, v in sched if v]
    t_sched = table(["일정", "날짜"], sched)
    tr = []
    for t in sorted(ty, key=lambda t: (t["area"] or 0)):
        pp = (t["price"] / (t["area"] / PY)) if t["price"] and t["area"] else None
        sp = []
        for lab, k in (("다자녀", "sp_m"), ("신혼부부", "sp_n"), ("생애최초", "sp_f"), ("노부모", "sp_p"), ("기관추천", "sp_i")):
            if t[k]: sp.append("%s %d" % (lab, t[k]))
        tr.append([esc(t["ty"] or "-"), ("%.2f㎡" % t["area"]) if t["area"] else "-", "%d" % t["gen"], ("%d (%s)" % (t["sp"], ", ".join(sp))) if t["sp"] and sp else "%d" % t["sp"], esc(eok(t["price"])) if t["price"] else "-", ("%s만원" % "{:,.0f}".format(pp)) if pp else "-"])
    t_type = table(["주택형", "공급면적", "일반공급", "특별공급", "최고 분양가", "3.3㎡당"], tr, (2, 4, 5)) if tr else ""
    rg = ('<h2 class="group-title">🧭 규제·지구 지정</h2><p class="lead">%s</p>' % esc(", ".join(ft))) if ft else ""
    nbs = ('<h2 class="group-title">📍 같은 지역 다른 분양 단지</h2>' + table(AH, [arow(x) for x in nb_sg])) if nb_sg else ""
    nbb = ('<h2 class="group-title">🏗️ 같은 시공사 다른 분양 단지</h2>' + table(AH, [arow(x) for x in nb_b])) if nb_b else ""
    links = []
    if a["url"]: links.append('<a href="%s" rel="nofollow noopener" target="_blank">청약홈 모집공고</a>' % esc(a["url"]))
    if a["home"]: links.append('<a href="%s" rel="nofollow noopener" target="_blank">분양 홈페이지</a>' % esc(a["home"] if a["home"].startswith("http") else "http://" + a["home"]))
    info = [["단지명", esc(a["name"])], ["유형", "%s · %s · %s" % (esc(a["kind"]), esc(a["detail"]), esc(a["sale"]))], ["위치", esc(a["addr"])], ["공급규모", "{:,}세대".format(a["size"])], ["시공사", esc(a["builder"] or "-")], ["시행사", esc(a["dev"] or "-")], ["입주예정", esc(a["move"] or "-")], ["문의", esc(a["tel"] or "-")]]
    body = f"""
<div class="page-head"><h1>{esc(a['name'])} — 분양가·청약일정 {a['size']:,}세대</h1><p>{esc(a['sido'])} {esc(a['sg'])} · {esc(a['kind'])} · 공고 {dt(a['d_pub'])}</p></div>
{lead}
{ad()}
<h2 class="group-title">📋 단지 정보</h2>
{table(['항목', '내용'], info)}
<h2 class="group-title">📅 청약 일정</h2>
{t_sched}
{('<h2 class="group-title">🏠 주택형별 공급·분양가</h2>' + t_type) if t_type else ''}
{rg}
{('<p class="lead">' + " · ".join(links) + '</p>') if links else ''}
{nbs}
{nbb}
<p class="note">{NOTE} ‘최고 분양가’는 주택형별 분양 최고금액(층별 최고)이며 실제 분양가는 층·향에 따라 다릅니다.</p>
{chips([("%s 분양" % a["sido"], "/region/%s/" % a["sido"])] + ([(a["sg"] + " 분양", "/region/%s/%s/" % (a["sido"], a["sg"]))] if a["sg"] and (a["sido"], a["sg"]) in SGP else []) + [("%s년 %s월 분양 일정" % (a["year"], a["ym"][5:]), "/month/%s/%s/" % (a["year"], a["ym"][5:]))] + ([(a["builder"], "/builder/%s/" % BSLUG[a["builder"]])] if len(BY_BUILDER.get(a["builder"], [])) >= 2 else []))}
"""
    faq = [(f"{a['name']} 분양가는 얼마인가요?", (f"주택형별 최고 분양가 {eok(a['p_min'])}~{eok(a['p_max'])}입니다(3.3㎡당 약 {a['py_min']:,.0f}~{a['py_max']:,.0f}만원).") if a["p_max"] else "공공데이터에 분양가가 없습니다. 모집공고문을 확인하세요."),
           (f"{a['name']} 청약 일정은?", ("청약 접수 " + rng(a["d_apply"]) + (", 당첨자 발표 " + dt(a["d_win"]) if a["d_win"] else "")) if rng(a["d_apply"]) else "모집공고문을 확인하세요."), (f"{a['name']} 시공사는?", a["builder"] or "공공데이터에 시공사 정보가 없습니다.")]
    write(a["path"], layout(a["path"], f"{a['name']}{sfx} 분양가·청약일정 — {a['sido']} {a['sg']} {a['size']:,}세대", f"{a['name']}({a['addr']}) {a['size']:,}세대. 모집공고 {dt(a['d_pub'])}, {('청약 ' + rng(a['d_apply']) + ', ') if rng(a['d_apply']) else ''}{('시공사 ' + a['builder'] + ', ') if a['builder'] else ''}{('최고 분양가 ' + eok(a['p_max']) + '.') if a['p_max'] else ''}", body, faq,
          [("홈", "/"), ("지역별", "/region/"), (a["sido"], "/region/%s/" % a["sido"]), (a["name"], a["path"])]), "0.5")

# ───────────────────────── 지역 ─────────────────────────
SGP = {k for k, v in BY_SG.items() if len(v) >= 2}
def stats_line(lst):
    py = [a["py_max"] for a in lst if a["py_max"]]
    return "%d단지·%s세대" % (len(lst), "{:,}".format(sum(a["size"] for a in lst))) + (", 3.3㎡당 최고 분양가 평균 약 %s만원" % "{:,.0f}".format(sum(py) / len(py)) if py else "")

def page_sg(sido, sg):
    lst = BY_SG[(sido, sg)]; path = "/region/%s/%s/" % (sido, sg)
    body = f"""
<div class="page-head"><h1>{esc(sg)} 신규 분양 단지 {len(lst)}곳 — 분양가·청약일정</h1><p>{esc(SIDO_FULL[sido])} {esc(sg)} · {stats_line(lst)}</p></div>
<p class="lead"><b>{esc(SIDO_FULL[sido])} {esc(sg)}</b>에서 {ASOF}에 모집공고가 난 분양 단지는 {len(lst)}곳({stats_line(lst)})입니다. 최근 공고 순입니다. 단지를 누르면 분양가·청약 일정·주택형별 공급 내용을 볼 수 있습니다.</p>
{ad()}
{table(AH, [arow(a) for a in lst])}
<p class="note">{NOTE}</p>
{chips([(sido, "/region/%s/" % sido), ("월별 분양 일정", "/month/"), ("평균 분양가", "/price/%s/" % sido)])}
"""
    faq = [(f"{sg} 신규 분양 단지는?", f"{ASOF} 기준 {len(lst)}곳이며 최근 단지는 {lst[0]['name']}입니다."), (f"{sg} 분양가는 얼마인가요?", stats_line(lst) + "입니다.")]
    write(path, layout(path, f"{SIDO_FULL[sido]} {sg} 신규 분양 단지 {len(lst)}곳 — 분양가·청약일정·시공사", f"{SIDO_FULL[sido]} {sg} 분양 단지 {len(lst)}곳({stats_line(lst)}). 분양가·청약일정·시공사.", body, faq, [("홈", "/"), ("지역별", "/region/"), (sido, "/region/%s/" % sido), (sg, path)]), "0.7")

def page_sido(sido):
    lst = BY_SIDO[sido]; path = "/region/%s/" % sido; sgs = collections.Counter(a["sg"] for a in lst if a["sg"])
    body = f"""
<div class="page-head"><h1>{esc(SIDO_FULL[sido])} 신규 분양 단지 {len(lst)}곳 — 분양가·청약일정</h1><p>{stats_line(lst)}</p></div>
<p class="lead"><b>{esc(SIDO_FULL[sido])}</b>에서 {ASOF}에 모집공고가 난 분양 단지는 {len(lst)}곳({stats_line(lst)})입니다. 시군구를 눌러 지역별 단지를 확인하세요.</p>
{ad()}
{chips([("%s %d곳" % (g, c), "/region/%s/%s/" % (sido, g)) if (sido, g) in SGP else ("%s %d곳" % (g, c), [x for x in lst if x["sg"] == g][0]["path"]) for g, c in sgs.most_common()])}
<h2 class="group-title">🆕 최근 공고 단지</h2>
{table(AH, [arow(a) for a in lst[:60]])}
<p class="note">{NOTE}</p>
{chips([("경쟁률", "/competition/%s/" % sido), ("평균 분양가", "/price/%s/" % sido), ("지역별", "/region/")])}
"""
    faq = [(f"{SIDO_FULL[sido]} 신규 분양 단지는?", f"{ASOF} 기준 {len(lst)}곳입니다."), (f"{sido} 청약 경쟁률은?", "경쟁률 페이지에서 월별 특별·일반공급 경쟁률을 확인할 수 있습니다.")]
    write(path, layout(path, f"{SIDO_FULL[sido]} 신규 분양 단지 {len(lst)}곳 — 분양가·청약일정", f"{SIDO_FULL[sido]} 분양 단지 {len(lst)}곳({stats_line(lst)}). 시군구별 목록과 청약 일정.", body, faq, [("홈", "/"), ("지역별", "/region/"), (sido, path)]), "0.8")
    for g in sorted(sgs):
        if (sido, g) in SGP: page_sg(sido, g)

def hub_region():
    rows = [['<a href="/region/%s/">%s</a>' % (s, SIDO_FULL[s]), len(BY_SIDO[s]), "{:,}".format(sum(a["size"] for a in BY_SIDO[s]))] for s in SIDOS if BY_SIDO.get(s)]
    body = f"""
<div class="page-head"><h1>지역별 신규 분양 단지 — 전국 {len(A):,}곳 분양가·청약일정</h1><p>{ASOF}</p></div>
<p class="lead">{ASOF} 모집공고가 난 전국 분양 단지 {len(A):,}곳을 지역별로 정리했습니다. 지역을 선택하면 단지별 분양가, 청약 일정, 시공사를 볼 수 있습니다.</p>
{ad()}
{table(['시도', '분양 단지', '공급 세대'], rows, (1, 2))}
<p class="note">{NOTE}</p>
{chips([("월별 분양 일정", "/month/"), ("건설사별", "/builder/"), ("경쟁률", "/competition/"), ("평균 분양가", "/price/")])}
"""
    faq = [("전국에 분양 단지는 몇 곳인가요?", f"{ASOF} 기준 {len(A):,}곳입니다."), ("분양 정보는 어디서 가져오나요?", "한국부동산원 청약홈이 공개한 분양정보 공공데이터를 사용합니다.")]
    write("/region/", layout("/region/", f"지역별 신규 분양 단지 — 전국 {len(A):,}곳 분양가·청약일정", f"{ASOF} 전국 분양 단지 {len(A):,}곳을 시도·시군구별로 정리. 분양가·청약일정·시공사.", body, faq, [("홈", "/"), ("지역별", "/region/")], coupang=True), "0.9")

# ───────────────────────── 월별·입주 ─────────────────────────
def page_month(y, m):
    lst = BY_YM["%s-%s" % (y, m)]; path = "/month/%s/%s/" % (y, m)
    sc = collections.Counter(a["sido"] for a in lst)
    body = f"""
<div class="page-head"><h1>{y}년 {int(m)}월 분양 일정 — 청약 단지 {len(lst)}곳</h1><p>{stats_line(lst)}</p></div>
<p class="lead"><b>{y}년 {int(m)}월</b>에 모집공고가 난 분양 단지는 {len(lst)}곳({stats_line(lst)})입니다. 지역별로는 {', '.join('%s %d곳' % (k, v) for k, v in sc.most_common(5))} 순입니다. 단지를 누르면 청약 접수일과 당첨자 발표일, 분양가를 볼 수 있습니다.</p>
{ad()}
{table(AH, [arow(a) for a in lst])}
<p class="note">{NOTE}</p>
{chips([("%s년 분양 전체" % y, "/month/%s/" % y), ("월별 분양 일정", "/month/"), ("지역별", "/region/")])}
"""
    faq = [(f"{y}년 {int(m)}월 분양 단지는?", f"모집공고 기준 {len(lst)}곳입니다."), ("청약 일정은 어디서 확인하나요?", "각 단지 페이지에서 청약 접수일·당첨자 발표일을 확인하고 청약홈 모집공고문으로 최종 확인하세요.")]
    write(path, layout(path, f"{y}년 {int(m)}월 분양 일정 — 청약 단지 {len(lst)}곳·분양가", f"{y}년 {int(m)}월 모집공고 분양 단지 {len(lst)}곳({stats_line(lst)}). 청약일정과 분양가.", body, faq, [("홈", "/"), ("월별 일정", "/month/"), (y + "년", "/month/%s/" % y), (m + "월", path)]), "0.6")

def page_year(y):
    ms = sorted({a["ym"][5:] for a in A if a["year"] == y}); lst = [a for a in A if a["year"] == y]; path = "/month/%s/" % y
    body = f"""
<div class="page-head"><h1>{y}년 분양 단지 {len(lst)}곳 — 월별 청약 일정</h1><p>{stats_line(lst)}</p></div>
<p class="lead"><b>{y}년</b>에 모집공고가 난 분양 단지는 {len(lst)}곳({stats_line(lst)})입니다. 월을 누르면 해당 월 단지 목록이 나옵니다.</p>
{ad()}
{chips([("%s월 %d곳" % (int(m), len(BY_YM['%s-%s' % (y, m)])), "/month/%s/%s/" % (y, m)) for m in ms])}
<h2 class="group-title">🏆 {y}년 공급 규모 큰 단지 TOP 20</h2>
{table(AH, [arow(a) for a in sorted(lst, key=lambda a: -a['size'])[:20]])}
<p class="note">{NOTE}</p>
"""
    write(path, layout(path, f"{y}년 분양 단지 {len(lst)}곳 — 월별 청약 일정·분양가", f"{y}년 분양 단지 {len(lst)}곳({stats_line(lst)}). 월별 일정과 대단지 순위.", body, [(f"{y}년에 분양한 단지는 몇 곳인가요?", f"모집공고 기준 {len(lst)}곳입니다.")], [("홈", "/"), ("월별 일정", "/month/"), (y + "년", path)]), "0.7")
    for m in ms: page_month(y, m)

def hub_month():
    ys = sorted({a["year"] for a in A}, reverse=True)
    body = f"""
<div class="page-head"><h1>월별 분양 일정 — 연도별 청약 단지 목록</h1><p>{ASOF}</p></div>
<p class="lead">연도와 월별로 모집공고가 난 분양 단지를 정리했습니다. 연도를 누르면 월별 목록과 대단지 순위를 볼 수 있습니다.</p>
{ad()}
{chips([("%s년 %d곳" % (y, len([a for a in A if a["year"] == y])), "/month/%s/" % y) for y in ys])}
<p class="note">{NOTE}</p>
{chips([("지역별", "/region/"), ("입주 예정월", "/move-in/")])}
"""
    write("/month/", layout("/month/", "월별 분양 일정 — 연도별 청약 단지 목록", f"{ASOF} 모집공고 분양 단지를 연도·월별로 정리했습니다. 청약일정과 분양가.", body, [("분양 일정은 어떻게 찾나요?", "연도와 월을 선택하면 해당 월 모집공고 단지가 나옵니다.")], [("홈", "/"), ("월별 일정", "/month/")], coupang=True), "0.8")

def page_move(ym):
    lst = BY_MOVE[ym]; path = "/move-in/%s/" % ym
    body = f"""
<div class="page-head"><h1>{ym[:4]}년 {int(ym[5:])}월 입주 예정 분양 단지 {len(lst)}곳</h1><p>{stats_line(lst)}</p></div>
<p class="lead"><b>{ym[:4]}년 {int(ym[5:])}월</b> 입주 예정으로 공고된 분양 단지는 {len(lst)}곳({stats_line(lst)})입니다. 입주 일정은 공사 상황에 따라 바뀔 수 있습니다.</p>
{ad()}
{table(AH, [arow(a) for a in lst])}
<p class="note">{NOTE} 입주예정월은 모집공고 기준이며 실제 입주 시기와 다를 수 있습니다.</p>
{chips([("입주 예정월", "/move-in/"), ("월별 분양 일정", "/month/")])}
"""
    write(path, layout(path, f"{ym[:4]}년 {int(ym[5:])}월 입주 예정 분양 단지 {len(lst)}곳", f"{ym[:4]}년 {int(ym[5:])}월 입주 예정 분양 단지 {len(lst)}곳({stats_line(lst)}). 분양가·시공사.", body, [(f"{ym[:4]}년 {int(ym[5:])}월 입주 예정 단지는?", f"모집공고 기준 {len(lst)}곳입니다.")], [("홈", "/"), ("입주 예정", "/move-in/"), (ym, path)]), "0.5")

def hub_move():
    ms = sorted(BY_MOVE, reverse=True)
    body = f"""
<div class="page-head"><h1>입주 예정월별 분양 단지 — 입주 시기로 찾기</h1><p>{ASOF}</p></div>
<p class="lead">입주 예정월별로 분양 단지를 정리했습니다. 입주 시기를 기준으로 단지를 찾을 때 이용하세요.</p>
{ad()}
{chips([("%s %d곳" % (m, len(BY_MOVE[m])), "/move-in/%s/" % m) for m in ms])}
<p class="note">{NOTE}</p>
"""
    write("/move-in/", layout("/move-in/", "입주 예정월별 분양 단지 — 입주 시기로 찾기", f"{ASOF} 분양 단지를 입주 예정월별로 정리했습니다.", body, [("입주 예정월은 정확한가요?", "모집공고 기준이며 공사 상황에 따라 바뀔 수 있습니다.")], [("홈", "/"), ("입주 예정", "/move-in/")]), "0.6")
    for m in ms: page_move(m)

# ───────────────────────── 건설사 ─────────────────────────
def page_builder(b):
    lst = BY_BUILDER[b]; path = "/builder/%s/" % BSLUG[b]; sc = collections.Counter(a["sido"] for a in lst)
    body = f"""
<div class="page-head"><h1>{esc(b)} 분양 단지 {len(lst)}곳 — 분양가·청약일정</h1><p>{stats_line(lst)}</p></div>
<p class="lead"><b>{esc(b)}</b>이(가) 시공사로 참여한 분양 단지는 {ASOF} 공고 기준 {len(lst)}곳({stats_line(lst)})입니다. 지역별로는 {', '.join('%s %d곳' % (k, v) for k, v in sc.most_common(5))} 순입니다.</p>
{ad()}
{table(AH, [arow(a) for a in lst])}
<p class="note">{NOTE}</p>
{chips([("건설사별", "/builder/"), ("지역별", "/region/")])}
"""
    faq = [(f"{b} 분양 단지는 몇 곳인가요?", f"{ASOF} 기준 {len(lst)}곳입니다."), (f"{b}의 최근 분양 단지는?", f"{lst[0]['name']}({lst[0]['sido']}, {dt(lst[0]['d_pub'])} 공고)입니다.")]
    write(path, layout(path, f"{b} 분양 단지 {len(lst)}곳 — 시공 아파트 분양가·청약일정", f"{b} 시공 분양 단지 {len(lst)}곳({stats_line(lst)}). 최근 분양 {lst[0]['name']}.", body, faq, [("홈", "/"), ("건설사별", "/builder/"), (b, path)]), "0.5")

def hub_builder():
    bs = [b for b in BY_BUILDER if len(BY_BUILDER[b]) >= 2]
    rows = [['<a href="/builder/%s/">%s</a>' % (BSLUG[b], esc(b)), len(BY_BUILDER[b]), "{:,}".format(sum(a["size"] for a in BY_BUILDER[b]))] for b in sorted(bs, key=lambda b: -len(BY_BUILDER[b]))]
    body = f"""
<div class="page-head"><h1>건설사별 분양 단지 — 시공사 순위</h1><p>{ASOF} · 2곳 이상 시공사 {len(bs)}개</p></div>
<p class="lead">분양 단지를 건설사(시공사)별로 모았습니다. 2곳 이상 참여한 건설사 {len(bs)}개를 분양 단지 수 순으로 보여 드립니다. 건설사를 누르면 단지 목록과 청약 일정을 볼 수 있습니다.</p>
{ad()}
{table(['건설사', '분양 단지', '공급 세대'], rows, (1, 2))}
<p class="note">{NOTE}</p>
"""
    write("/builder/", layout("/builder/", f"건설사별 분양 단지 — 시공사 {len(bs)}곳 순위", f"{ASOF} 분양 단지를 시공 건설사별로 정리. 대우건설·GS건설·현대건설 등 분양 단지 수 순위.", body, [("분양 단지가 가장 많은 건설사는?", f"{max(bs, key=lambda b: len(BY_BUILDER[b]))}이(가) {max(len(BY_BUILDER[b]) for b in bs)}곳으로 가장 많습니다.")], [("홈", "/"), ("건설사별", "/builder/")], coupang=True), "0.8")
    for b in bs: page_builder(b)

# ───────────────────────── 경쟁률·평균분양가 ─────────────────────────
def num(x):
    try: return float(x.replace(",", ""))
    except Exception: return None
def comp_txt(v):
    if v.startswith("(△") or v.startswith("△"): return "미달 " + re.sub(r"[^\d,]", "", v) + "세대"
    return v + " : 1"
CBY = collections.defaultdict(dict)
for c in COMP: CBY[c["시도"]][c["연월"]] = c
def page_comp_m(s, ym):
    c = CBY[s][ym]; path = "/competition/%s/%s/" % (s, ym)
    nat = [CBY[x].get(ym) for x in CBY if CBY[x].get(ym)]
    g_all = sum(int(n["일반공급 접수건수"].replace(",", "") or 0) for n in nat); g_sup = sum(int(n["일반공급 공급세대수"].replace(",", "") or 0) for n in nat)
    body = f"""
<div class="page-head"><h1>{esc(s)} {ym[:4]}년 {int(ym[5:])}월 청약 경쟁률 — 일반 {esc(comp_txt(c['일반공급 경쟁률']))}</h1><p>특별공급·일반공급 접수 현황</p></div>
<p class="lead"><b>{esc(SIDO_FULL.get(s, s))} {ym[:4]}년 {int(ym[5:])}월</b> 청약 경쟁률은 일반공급 <b>{esc(comp_txt(c['일반공급 경쟁률']))}</b>(공급 {c['일반공급 공급세대수']}세대에 {c['일반공급 접수건수']}건 접수), 특별공급 <b>{esc(comp_txt(c['특별공급 경쟁률']))}</b>(공급 {c['특별공급 공급세대수']}세대에 {c['특별공급 접수건수']}건 접수)입니다. 경쟁률이 ‘미달’로 표시되면 접수가 공급보다 적었다는 뜻입니다.</p>
{ad()}
{table(['구분', '공급세대', '접수건수', '경쟁률'], [['특별공급', c['특별공급 공급세대수'], c['특별공급 접수건수'], esc(comp_txt(c['특별공급 경쟁률']))], ['일반공급', c['일반공급 공급세대수'], c['일반공급 접수건수'], esc(comp_txt(c['일반공급 경쟁률']))]], (1, 2, 3))}
<p class="note">{NOTE} 지역별 청약 경쟁률은 한국부동산원 월별 통계입니다.</p>
{chips([(s + " 월별 경쟁률", "/competition/%s/" % s), (s + " 분양 단지", "/region/%s/" % s) if s in BY_SIDO else ("지역별", "/region/"), ("경쟁률", "/competition/")])}
"""
    faq = [(f"{s} {ym[:4]}년 {int(ym[5:])}월 청약 경쟁률은?", f"일반공급 {comp_txt(c['일반공급 경쟁률'])}, 특별공급 {comp_txt(c['특별공급 경쟁률'])}입니다."), ("미달은 무슨 뜻인가요?", "접수 건수가 공급 세대수보다 적어 경쟁이 발생하지 않았다는 뜻입니다.")]
    write(path, layout(path, f"{s} {ym[:4]}년 {int(ym[5:])}월 청약 경쟁률 — 일반공급 {comp_txt(c['일반공급 경쟁률'])}", f"{SIDO_FULL.get(s, s)} {ym[:4]}년 {int(ym[5:])}월 청약 경쟁률. 일반공급 {comp_txt(c['일반공급 경쟁률'])}, 특별공급 {comp_txt(c['특별공급 경쟁률'])}.", body, faq, [("홈", "/"), ("경쟁률", "/competition/"), (s, "/competition/%s/" % s), (ym, path)]), "0.4")

def page_comp_sido(s):
    rows = sorted(CBY[s].values(), key=lambda c: c["연월"], reverse=True); path = "/competition/%s/" % s
    tr = [['<a href="/competition/%s/%s/">%s</a>' % (s, c["연월"], c["연월"]), c["특별공급 공급세대수"], esc(comp_txt(c["특별공급 경쟁률"])), c["일반공급 공급세대수"], esc(comp_txt(c["일반공급 경쟁률"]))] for c in rows]
    body = f"""
<div class="page-head"><h1>{esc(SIDO_FULL.get(s, s))} 청약 경쟁률 — 월별 특별·일반공급</h1><p>{rows[-1]['연월']} ~ {rows[0]['연월']}</p></div>
<p class="lead"><b>{esc(SIDO_FULL.get(s, s))}</b>의 월별 청약 경쟁률입니다. 월을 누르면 해당 월 상세를 볼 수 있습니다. ‘미달’은 접수가 공급보다 적었다는 뜻입니다.</p>
{ad()}
{table(['연월', '특별 공급', '특별 경쟁률', '일반 공급', '일반 경쟁률'], tr, (1, 3))}
<p class="note">{NOTE}</p>
{chips([("전국 경쟁률", "/competition/"), (s + " 분양 단지", "/region/%s/" % s) if s in BY_SIDO else ("지역별", "/region/"), ("평균 분양가", "/price/%s/" % s)])}
"""
    write(path, layout(path, f"{SIDO_FULL.get(s, s)} 청약 경쟁률 — 월별 특별·일반공급 {rows[-1]['연월'][:4]}~{rows[0]['연월'][:4]}", f"{SIDO_FULL.get(s, s)} 월별 청약 경쟁률(특별·일반공급) {rows[-1]['연월']}~{rows[0]['연월']}.", body, [(f"{s} 청약 경쟁률은?", f"최근({rows[0]['연월']}) 일반공급 {comp_txt(rows[0]['일반공급 경쟁률'])}입니다.")], [("홈", "/"), ("경쟁률", "/competition/"), (s, path)], coupang=True), "0.7")
    for c in rows: page_comp_m(s, c["연월"])

def hub_comp():
    latest = max(c["연월"] for c in COMP)
    rows = [['<a href="/competition/%s/">%s</a>' % (s, SIDO_FULL.get(s, s)), CBY[s][latest]["일반공급 공급세대수"] if latest in CBY[s] else "-", esc(comp_txt(CBY[s][latest]["일반공급 경쟁률"])) if latest in CBY[s] else "-"] for s in SIDOS if s in CBY]
    body = f"""
<div class="page-head"><h1>지역별 청약 경쟁률 — {latest} 기준 전국 현황</h1><p>한국부동산원 월별 통계</p></div>
<p class="lead">시도별 월별 청약 경쟁률(특별공급·일반공급)입니다. 아래는 {latest} 기준 일반공급 현황이고 지역을 누르면 월별 추이를 볼 수 있습니다.</p>
{ad()}
{table(['시도', f'{latest} 일반공급 세대', '일반공급 경쟁률'], rows, (1, 2))}
<p class="note">{NOTE}</p>
{chips([("연령별 당첨자", "/winners/"), ("평균 분양가", "/price/"), ("지역별", "/region/")])}
"""
    write("/competition/", layout("/competition/", f"지역별 청약 경쟁률 — {latest} 전국 현황·월별 추이", "시도별 월별 청약 경쟁률(특별·일반공급)과 미달 현황. 한국부동산원 통계.", body, [("청약 경쟁률은 어떻게 계산하나요?", "접수건수를 공급세대수로 나눈 값입니다. 접수가 공급보다 적으면 미달로 표시됩니다.")], [("홈", "/"), ("경쟁률", "/competition/")], coupang=True), "0.8")
    for s in CBY: page_comp_sido(s)

def page_winners():
    rows = sorted(WIN, key=lambda r: r["연월"], reverse=True)
    def tot(r): return sum(int(r[k].replace(",", "") or 0) for k in ("30대 이하", "40대", "50대", "60대 이상"))
    tr = [[r["연월"], r["30대 이하"], r["40대"], r["50대"], r["60대 이상"], "%.0f%%" % (int(r["30대 이하"].replace(",", "") or 0) / max(tot(r), 1) * 100)] for r in rows]
    body = f"""
<div class="page-head"><h1>연령별 청약 당첨자 — 30대 이하·40대·50대·60대</h1><p>{rows[-1]['연월']} ~ {rows[0]['연월']}</p></div>
<p class="lead">월별 청약 당첨자 수를 연령대별로 정리했습니다. 가장 최근({rows[0]['연월']})에는 30대 이하 {rows[0]['30대 이하']}명, 40대 {rows[0]['40대']}명이 당첨됐습니다.</p>
{ad()}
{table(['연월', '30대 이하', '40대', '50대', '60대 이상', '30대 이하 비중'], tr, (1, 2, 3, 4, 5))}
<p class="note">{NOTE}</p>
{chips([("경쟁률", "/competition/"), ("지역별", "/region/")])}
"""
    write("/winners/", layout("/winners/", "연령별 청약 당첨자 — 30대 이하·40대·50대 월별 현황", f"월별 청약 당첨자를 연령대별로 정리({rows[-1]['연월']}~{rows[0]['연월']}). 30대 이하 비중.", body, [("청약 당첨자는 어느 연령대가 많나요?", "표의 월별 수치를 확인하세요.")], [("홈", "/"), ("연령별 당첨자", "/winners/")]), "0.6")

AVY = collections.defaultdict(lambda: collections.defaultdict(list))
for r in AVG: AVY[r["지역"]][r["연도"]].append(r)
def pv(x):
    try: return int(x.replace(",", ""))
    except Exception: return 0
def page_price_y(s, y):
    rs = sorted(AVY[s][y], key=lambda r: r["분기"]); path = "/price/%s/%s/" % (s, y)
    tr = [[r["분기"], ("{:,}만원".format(pv(r["60제곱미터 이하"]))) if pv(r["60제곱미터 이하"]) else "-", ("{:,}만원".format(pv(r["60제곱미터 초과 85제곱미터 이하"]))) if pv(r["60제곱미터 초과 85제곱미터 이하"]) else "-", ("{:,}만원".format(pv(r["85제곱미터 초과"]))) if pv(r["85제곱미터 초과"]) else "-"] for r in rs]
    v85 = [pv(r["60제곱미터 초과 85제곱미터 이하"]) for r in rs if pv(r["60제곱미터 초과 85제곱미터 이하"])]
    avg85 = sum(v85) // len(v85) if v85 else 0
    body = f"""
<div class="page-head"><h1>{esc(SIDO_FULL.get(s, s))} {y}년 평균 분양가 — 3.3㎡당 면적별</h1><p>분기별 · 60㎡ 이하·60~85㎡·85㎡ 초과</p></div>
<p class="lead"><b>{esc(SIDO_FULL.get(s, s))} {y}년</b> 아파트 평균 분양가(3.3㎡당)는 전용 60~85㎡ 기준{(' 약 <b>' + '{:,}'.format(avg85) + '만원</b>') if avg85 else ' 자료 없음'}입니다. 분기별 면적 구간별 평균은 아래 표와 같습니다. 0은 해당 분기에 분양이 없었다는 뜻입니다.</p>
{ad()}
{table(['분기', '60㎡ 이하', '60㎡ 초과~85㎡ 이하', '85㎡ 초과'], tr, (1, 2, 3))}
<p class="note">{NOTE} 단위는 3.3㎡당 만원입니다.</p>
{chips([(s + " 평균 분양가", "/price/%s/" % s), ("경쟁률", "/competition/%s/" % s) if s in CBY else ("경쟁률", "/competition/"), ("평균 분양가", "/price/")])}
"""
    faq = [(f"{s} {y}년 평균 분양가는?", f"60~85㎡ 기준 3.3㎡당 약 {avg85:,}만원입니다." if avg85 else "자료가 없습니다.")]
    write(path, layout(path, f"{SIDO_FULL.get(s, s)} {y}년 평균 분양가 — 3.3㎡당 {avg85:,}만원(60~85㎡)" if avg85 else f"{SIDO_FULL.get(s, s)} {y}년 평균 분양가", f"{SIDO_FULL.get(s, s)} {y}년 분기별 평균 분양가(3.3㎡당). 60㎡ 이하·60~85㎡·85㎡ 초과.", body, faq, [("홈", "/"), ("평균 분양가", "/price/"), (s, "/price/%s/" % s), (y, path)]), "0.5")

def page_price_s(s):
    ys = sorted(AVY[s], reverse=True); path = "/price/%s/" % s
    tr = []
    for y in ys:
        rs = AVY[s][y]; vals = [pv(r["60제곱미터 초과 85제곱미터 이하"]) for r in rs if pv(r["60제곱미터 초과 85제곱미터 이하"])]
        tr.append(['<a href="/price/%s/%s/">%s년</a>' % (s, y, y), "{:,}만원".format(sum(vals) // len(vals)) if vals else "-"])
    body = f"""
<div class="page-head"><h1>{esc(SIDO_FULL.get(s, s))} 평균 분양가 — 연도별 3.3㎡당</h1><p>60~85㎡ 기준 연평균</p></div>
<p class="lead"><b>{esc(SIDO_FULL.get(s, s))}</b>의 연도별 평균 분양가(3.3㎡당, 전용 60~85㎡ 구간)입니다. 연도를 누르면 분기별·면적별 상세를 볼 수 있습니다.</p>
{ad()}
{table(['연도', '평균 분양가(60~85㎡)'], tr, (1,))}
<p class="note">{NOTE}</p>
{chips([("평균 분양가", "/price/"), ("경쟁률", "/competition/%s/" % s) if s in CBY else ("경쟁률", "/competition/")])}
"""
    write(path, layout(path, f"{SIDO_FULL.get(s, s)} 평균 분양가 — 연도별 3.3㎡당 추이", f"{SIDO_FULL.get(s, s)} 연도별 평균 분양가(3.3㎡당, 60~85㎡) 추이.", body, [(f"{s} 분양가는 해마다 올랐나요?", "연도별 표에서 추이를 확인하세요.")], [("홈", "/"), ("평균 분양가", "/price/"), (s, path)], coupang=True), "0.7")
    for y in ys: page_price_y(s, y)

def hub_price():
    latest = max(r["연도"] for r in AVG)
    rows = []
    for s in SIDOS:
        if s not in AVY: continue
        rs = AVY[s][latest]; vals = [pv(r["60제곱미터 초과 85제곱미터 이하"]) for r in rs if pv(r["60제곱미터 초과 85제곱미터 이하"])]
        rows.append(['<a href="/price/%s/">%s</a>' % (s, SIDO_FULL[s]), "{:,}만원".format(sum(vals) // len(vals)) if vals else "-"])
    body = f"""
<div class="page-head"><h1>지역별 평균 분양가 — 3.3㎡당 시도별 현황</h1><p>{latest}년 · 60~85㎡ 기준</p></div>
<p class="lead">시도별 아파트 평균 분양가(3.3㎡당)입니다. 지역을 누르면 연도별·분기별 상세를 볼 수 있습니다.</p>
{ad()}
{table(['시도', f'{latest}년 평균 분양가(60~85㎡)'], rows, (1,))}
<p class="note">{NOTE}</p>
{chips([("경쟁률", "/competition/"), ("지역별 분양 단지", "/region/")])}
"""
    write("/price/", layout("/price/", f"지역별 평균 분양가 — {latest}년 시도별 3.3㎡당", "시도별 평균 분양가(3.3㎡당)와 연도별·분기별 추이. 한국부동산원 통계.", body, [("평균 분양가는 어떻게 집계하나요?", "한국부동산원이 분기별로 면적 구간별 3.3㎡당 평균을 집계합니다.")], [("홈", "/"), ("평균 분양가", "/price/")], coupang=True), "0.8")
    for s in AVY: page_price_s(s)

# ───────────────────────── 순위 ─────────────────────────
def page_rank(kind, y=None):
    pool = [a for a in A if (y is None or a["year"] == y)]
    if kind == "price": lst = sorted([a for a in pool if a["py_max"]], key=lambda a: -a["py_max"])[:100]; title = "분양가 높은 단지"; col = "3.3㎡당"
    else: lst = sorted(pool, key=lambda a: -a["size"])[:100]; title = "공급 규모 큰 단지"; col = "공급"
    path = "/rank/%s/%s" % (kind, ("%s/" % y) if y else "")
    ylab = ("%s년 " % y) if y else "전체 기간 "
    rows = [[i + 1, '<a href="%s">%s</a>' % (a["path"], esc(a["name"])), esc(a["sido"] + (" " + a["sg"] if a["sg"] else "")), ("%s만원" % "{:,.0f}".format(a["py_max"])) if kind == "price" else "{:,}세대".format(a["size"]), esc(a["builder"] or "-"), dt(a["d_pub"])] for i, a in enumerate(lst)]
    body = f"""
<div class="page-head"><h1>{ylab}{title} TOP {len(lst)}</h1><p>{ASOF}</p></div>
<p class="lead">{ylab}{title} 순위입니다. 1위는 <b>{esc(lst[0]['name'])}</b>({esc(lst[0]['sido'])})으로 {('3.3㎡당 약 ' + '{:,.0f}'.format(lst[0]['py_max']) + '만원') if kind == 'price' else ('{:,}세대'.format(lst[0]['size']))}입니다. {'분양가는 주택형별 최고 분양금액 기준 3.3㎡당 최고값입니다.' if kind == 'price' else ''}</p>
{ad()}
{table(['순위', '단지', '지역', col, '시공사', '공고일'], rows, (0, 3))}
<p class="note">{NOTE}</p>
{chips([("분양가 순위", "/rank/price/"), ("규모 순위", "/rank/size/"), ("지역별", "/region/")])}
"""
    write(path, layout(path, f"{ylab}{title} TOP {len(lst)} — 분양 순위", f"{ylab}{title} 순위. 1위 {lst[0]['name']}.", body, [(f"{ylab}{title} 1위는?", f"{lst[0]['name']}입니다.")], [("홈", "/"), ("순위", "/rank/"), (ylab + title, path)]), "0.6")

def hub_rank():
    ys = sorted({a["year"] for a in A}, reverse=True)
    body = f"""
<div class="page-head"><h1>분양 단지 순위 — 분양가·공급 규모</h1><p>{ASOF}</p></div>
<p class="lead">분양가가 높은 단지와 공급 규모가 큰 단지 순위를 전체 기간과 연도별로 정리했습니다.</p>
{ad()}
{chips([("분양가 순위(전체)", "/rank/price/"), ("규모 순위(전체)", "/rank/size/")] + [("%s년 분양가" % y, "/rank/price/%s/" % y) for y in ys] + [("%s년 규모" % y, "/rank/size/%s/" % y) for y in ys])}
<p class="note">{NOTE}</p>
"""
    write("/rank/", layout("/rank/", "분양 단지 순위 — 분양가 높은 단지·공급 규모 큰 단지", f"{ASOF} 분양가·공급 규모 TOP 100과 연도별 순위.", body, None, [("홈", "/"), ("순위", "/rank/")]), "0.7")

def page_home():
    recent = A[:12]
    body = f"""
<div class="hero"><h1>🏗️ 신규 분양 단지 {len(A):,}곳 — 분양가·청약일정·경쟁률</h1><p>지역별 분양 단지와 청약 일정, 분양가를 확인하세요.</p></div>
{ad()}
<div class="card-grid">
<a class="card" href="/region/"><b>📍 지역별</b><span>시도·시군구 분양 단지</span></a>
<a class="card" href="/month/"><b>📅 월별 분양 일정</b><span>연도·월별 청약 단지</span></a>
<a class="card" href="/builder/"><b>🏗️ 건설사별</b><span>시공사별 분양 단지</span></a>
<a class="card" href="/competition/"><b>🔥 청약 경쟁률</b><span>지역·월별 경쟁률</span></a>
<a class="card" href="/price/"><b>💰 평균 분양가</b><span>3.3㎡당 시도별</span></a>
<a class="card" href="/rank/"><b>🏆 순위</b><span>분양가·규모 TOP 100</span></a>
</div>
<h2 class="group-title">🆕 최근 공고 단지</h2>
{table(AH, [arow(a) for a in recent])}
<p class="lead">우아분양은 한국부동산원 청약홈 공공데이터({ASOF})로 전국 분양 단지 {len(A):,}곳의 청약 일정, 주택형별 분양가, 시공사·시행사, 규제지역 정보를 정리한 사이트입니다. 청약 경쟁률과 평균 분양가는 한국부동산원 월별·분기별 통계입니다. 자세한 기준은 <a href="/about/">데이터 설명</a>을 참고하세요.</p>
"""
    faq = [("분양 정보는 어디서 가져오나요?", "한국부동산원 청약홈이 공개한 분양정보·경쟁률·평균 분양가 공공데이터를 사용합니다."), ("최신 분양 단지도 있나요?", f"현재 데이터는 {ASOF}입니다. 최신 공고는 청약홈에서 확인하세요.")]
    write("/", layout("/", f"우아분양 — 신규 분양 단지 {len(A):,}곳 분양가·청약일정·경쟁률", f"전국 신규 분양 단지 {len(A):,}곳의 분양가·청약일정·시공사와 지역별 청약 경쟁률, 평균 분양가를 확인하세요.", body, faq), "1.0")

def page_about():
    body = f"""
<div class="page-head"><h1>데이터 설명</h1><p>정보의 출처와 한계</p></div>
<h2 class="group-title">📚 출처</h2><p class="lead">한국부동산원 청약홈 APT 분양정보(공공데이터포털 15101046)와 APT 주택형별 분양정보(15101047) {len(A):,}단지·{sum(len(a['types']) for a in A):,}개 주택형, 지역별 청약 경쟁률 정보(15110988), 지역별 평균 분양가 정보(15128701), 연령별 청약 당첨자 정보(15110981)를 사용했습니다.</p>
<h2 class="group-title">🧮 계산 값</h2><p class="lead">3.3㎡당 분양가 = 주택형별 최고 분양가(만원) ÷ (공급면적 ÷ 3.3058)입니다. 공급면적 기준이므로 전용면적 기준 가격과 다릅니다.</p>
<h2 class="group-title">⚠️ 한계</h2><p class="lead">{NOTE} 분양 정보 데이터는 {ASOF}이며 이후 공고는 포함되지 않았습니다. 지역별 경쟁률과 평균 분양가는 월·분기 통계로 개별 단지의 경쟁률과 다릅니다.</p>
<h2 class="group-title">📬 문의·정정</h2><p class="lead">오류 제보는 <a href="mailto:ingmaster83@gmail.com">ingmaster83@gmail.com</a> 으로 보내 주세요.</p>
"""
    write("/about/", layout("/about/", "데이터 설명 — 출처와 계산 방법", "우아분양 데이터 출처(한국부동산원 청약홈)와 3.3㎡당 분양가 계산 방법, 한계.", body, None, [("홈", "/"), ("데이터 설명", "/about/")]), "0.5")

def page_privacy():
    body = """
<div class="page-head"><h1>개인정보처리방침</h1></div>
<p class="lead">우아분양(wooabunyang.wooahouse.com, 이하 “서비스”)은 회원가입·로그인을 요구하지 않으며 이용자의 개인정보를 직접 수집하지 않습니다.</p>
<h3>자동 수집 정보</h3><p class="lead">서비스 개선을 위해 Google Analytics로 방문자 수·페이지뷰 등 익명 통계를 수집하며, Google AdSense와 쿠팡 파트너스는 맞춤 광고를 위해 쿠키를 사용할 수 있습니다. 쿠키는 브라우저 설정에서 비활성화할 수 있습니다. (<a href="https://policies.google.com/privacy">Google 개인정보처리방침</a>, <a href="https://policies.google.com/technologies/ads">Google 광고 정책</a>)</p>
<h3>쿠팡 파트너스</h3><p class="lead">일부 페이지에는 쿠팡 파트너스 활동의 일환으로 광고가 포함되어 있으며 이에 따른 수수료를 제공받을 수 있습니다.</p>
<h3>문의</h3><p class="lead"><a href="mailto:ingmaster83@gmail.com">ingmaster83@gmail.com</a></p>
<p class="note">최종 수정일: 2026년 10월 24일</p>
"""
    write("/privacy/", layout("/privacy/", "개인정보처리방침", "우아분양 개인정보처리방침", body, None, [("홈", "/"), ("개인정보처리방침", "/privacy/")]), sitemap=False)

def make_og():
    f = ROOT / "assets" / "og-image.png"
    if f.exists(): return
    try: from PIL import Image, ImageDraw, ImageFont
    except Exception: return
    im = Image.new("RGB", (1200, 630), (180, 83, 9)); dr = ImageDraw.Draw(im)
    def font(sz):
        for n in ("malgunbd.ttf", "malgun.ttf", "NanumGothicBold.ttf"):
            try: return ImageFont.truetype(n, sz)
            except Exception: pass
        return ImageFont.load_default()
    dr.rounded_rectangle((90, 90, 1110, 540), 40, fill=(255, 251, 235))
    dr.text((150, 150), "우아분양", font=font(110), fill=(120, 53, 15))
    dr.text((150, 300), "신규 분양 단지 · 분양가", font=font(54), fill=(31, 41, 55))
    dr.text((150, 380), "청약일정 · 경쟁률", font=font(54), fill=(31, 41, 55))
    dr.text((150, 470), "wooabunyang.wooahouse.com", font=font(34), fill=(107, 114, 128))
    im.save(f)

def main():
    t0 = time.time(); make_og()
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "assets", OUT / "assets", dirs_exist_ok=True)
    for nf in ROOT.glob("naver*.html"): shutil.copy(nf, OUT / nf.name)
    for a in A: page_apt(a)
    for s in SIDOS:
        if BY_SIDO.get(s): page_sido(s)
    hub_region()
    for y in sorted({a["year"] for a in A}): page_year(y)
    hub_month(); hub_move(); hub_builder(); hub_comp(); page_winners(); hub_price()
    for k in ("price", "size"):
        page_rank(k)
        for y in sorted({a["year"] for a in A}): page_rank(k, y)
    hub_rank(); page_home(); page_about(); page_privacy()
    today = time.strftime("%Y-%m-%d")
    urls = "".join("<url><loc>%s%s</loc><lastmod>%s</lastmod><priority>%s</priority></url>" % (BASE, q(p), today, pr) for p, pr in WRITTEN)
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>\n' % urls, encoding="utf-8")
    (OUT / "robots.txt").write_text("User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % BASE, encoding="utf-8")
    (OUT / "CNAME").write_text("wooabunyang.wooahouse.com\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    nf = layout("/404.html", "페이지를 찾을 수 없습니다", "요청한 페이지를 찾을 수 없습니다.", '<div class="page-head"><h1>페이지를 찾을 수 없습니다</h1></div><div class="chips"><a class="chip" href="/">홈</a><a class="chip" href="/region/">지역별 분양</a></div>', None, None, noindex=True)
    (OUT / "404.html").write_text(nf, encoding="utf-8")
    print("pages", len(WRITTEN), "elapsed", round(time.time() - t0), "s")

if __name__ == "__main__":
    main()
