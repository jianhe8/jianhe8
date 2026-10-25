#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
柯洁 · 战绩与马氏积分档案 —— 数据维护工具 (kejie.py)

直接读写 index.html 里内嵌的 `const D = {...}`，不引入任何外部数据文件，
保证站点始终是「单文件、可直接双击打开」。

设计目标：易操作 + 覆盖边界情况
  * 新比赛       -> add-tour（自动推断 tier、自动判「进行中」）
  * 王中王类型   -> tier-rules.json 里的 overrides 显式覆盖
  * 未完赛后续   -> add-game 自动延长 end、重算战绩；再 set-result 收尾
  * 讲解视频     -> add-video --tour / --game / --group / --net
  * 明玥新视频   -> add-video --bvid BVxxxx --net
  * 网棋         -> --net 直接进「野狐网棋 · 网络对局」分组
  * 对手志       -> 页面运行时由对局实时聚合，加完对局自动更新，无需额外处理

每次写入前自动备份为 index.backup.<时间戳>.html，可随时回滚。

用法示例：
  python tools/kejie.py list --year 2026
  python tools/kejie.py show 春兰杯
  python tools/kejie.py guess-tier "第1届棋仙战世界围棋公开赛预选"
  python tools/kejie.py add-tour "第1届棋仙战" --start 2026-11-02 --end 2026-11-06
  python tools/kejie.py add-game 春兰杯 --date 2026-12-07 --opp 申真谞 --color B --result win --label 八强战
  python tools/kejie.py set-result 春兰杯 八强
  python tools/kejie.py add-video --bvid BV1hVH56jE5E --net --title "..." --date 2026-10-25
  python tools/kejie.py add-video --tour 王中王 --bvid BVxxxx --title "..."
  python tools/kejie.py add-video --game "2026-05-25|申真谞" --bvid BVxxxx --title "..."
  python tools/kejie.py merge-groups 其他对局 野狐网棋
  python tools/kejie.py add-countdown "棋仙战 · 预选" 2026-11-02 --note "世界棋仙战预选"
  python tools/kejie.py validate
  python tools/kejie.py stats
"""

import argparse
import base64
import datetime
import gzip
import json
import os
import re
import shutil
import sys

# ---------------------------------------------------------------- 基础

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_HTML = os.path.join(ROOT, "index.html")
RULES_PATH = os.path.join(ROOT, "tools", "tier-rules.json")

# 站点里已存在的 tier 取值（新增值需同步改前端配色，故先约束住）
KNOWN_TIERS = [
    "世界大赛", "世界大赛选拔", "世界团体赛", "世界团体赛选拔",
    "其他国际赛", "国内头衔战", "国内邀请赛/其他", "国内预选/网选",
    "围甲联赛", "其他赛事",
]

DATA_RE = re.compile(r"^const D = (\{.*\});[ \t]*$", re.M)


def setup_stdout():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def die(msg, code=2):
    print("✗ " + msg, file=sys.stderr)
    sys.exit(code)


def ok(msg):
    print("✓ " + msg)


def warn(msg):
    print("! " + msg)


def today_str():
    return datetime.date.today().isoformat()


def parse_date(s):
    try:
        return datetime.date.fromisoformat(s)
    except ValueError:
        die("日期格式必须是 YYYY-MM-DD，收到：%r" % s)


# ---------------------------------------------------------------- 读写

class Doc:
    """index.html 与其中内嵌 JSON 的读写封装。"""

    def __init__(self, path):
        self.path = path
        with open(path, encoding="utf-8") as f:
            self.text = f.read()
        m = DATA_RE.search(self.text)
        if not m:
            die("在 %s 里找不到 `const D = {...};` 这一行" % path)
        self.m = m
        try:
            self.D = json.loads(m.group(1))
        except json.JSONDecodeError as e:
            die("内嵌 JSON 解析失败：%s" % e)

    # -- 便捷访问
    @property
    def tours(self):
        return self.D.setdefault("tours", [])

    @property
    def groups(self):
        return self.D.setdefault("bili_groups", [])

    def save(self, dry=False, backup=True, note=""):
        payload = json.dumps(self.D, ensure_ascii=False, separators=(",", ":"))
        new_text = self.text[:self.m.start(1)] + payload + self.text[self.m.end(1):]
        if dry:
            warn("dry-run：未写入。变更摘要见上。")
            return
        if backup:
            ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            dst = os.path.join(os.path.dirname(self.path), "index.backup.%s.html" % ts)
            n = 1
            while os.path.exists(dst):  # 极端情况下也不覆盖已有备份
                dst = os.path.join(os.path.dirname(self.path),
                                   "index.backup.%s-%d.html" % (ts, n))
                n += 1
            shutil.copy2(self.path, dst)
            print("  备份 -> %s" % os.path.basename(dst))
        with open(self.path, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_text)
        self.text = new_text
        self.m = DATA_RE.search(new_text)
        ok("已写入 %s%s" % (os.path.basename(self.path), ("（" + note + "）") if note else ""))


# ---------------------------------------------------------------- 查找

def norm(s):
    return re.sub(r"\s+", "", s or "").lower()


def find_tour(D, sel, required=True):
    """按序号 / 精确名 / 唯一子串定位赛事。"""
    tours = D["tours"]
    if sel is None:
        return None
    s = str(sel).strip()
    if s.isdigit():
        i = int(s)
        if 0 <= i < len(tours):
            return tours[i]
        die("序号 %d 越界（0..%d）" % (i, len(tours) - 1))
    # 精确
    for t in tours:
        if t["name"] == s:
            return t
    # 子串
    cand = [t for t in tours if norm(s) in norm(t["name"])]
    if len(cand) == 1:
        return cand[0]
    if len(cand) > 1:
        print("匹配到 %d 项，请更精确或改用序号：" % len(cand))
        for t in cand:
            print("  [%d] %s  (%s)" % (tours.index(t), t["name"], t.get("start", "")))
        sys.exit(3)
    if required:
        die("找不到赛事：%r（用 `list` 看看有哪些）" % sel)
    return None


def find_group(D, sel, required=True):
    groups = D["bili_groups"]
    s = str(sel).strip()
    if s.isdigit():
        i = int(s)
        if 0 <= i < len(groups):
            return groups[i]
    for g in groups:
        if g["name"] == s:
            return g
    cand = [g for g in groups if norm(s) in norm(g["name"])]
    if len(cand) == 1:
        return cand[0]
    if len(cand) > 1:
        print("匹配到 %d 个分组：" % len(cand))
        for g in cand:
            print("  [%d] %s" % (groups.index(g), g["name"]))
        sys.exit(3)
    if required:
        die("找不到分组：%r" % sel)
    return None


# ---------------------------------------------------------------- 战绩重算

def recompute_tour(t):
    games = t.get("games", [])
    t["wins"] = sum(1 for g in games if g.get("win") and not g.get("void"))
    t["losses"] = sum(1 for g in games if (not g.get("win")) and not g.get("void"))
    t["voids"] = sum(1 for g in games if g.get("void"))
    if games:
        ds = sorted(g["date"] for g in games)
        t["start"] = min(t.get("start") or ds[0], ds[0])
        t["end"] = max(t.get("end") or ds[-1], ds[-1])


def sort_tours(tours):
    tours.sort(key=lambda t: (t.get("start") or "", t.get("end") or "", t.get("name") or ""))


def tour_sub(t):
    a, b = t.get("start", ""), t.get("end", "")
    span = a if a == b else "%s–%s" % (a, b)
    return "%s · %s" % (span, t.get("result") or "进行中")


# ---------------------------------------------------------------- tier 推断

def load_rules():
    if not os.path.exists(RULES_PATH):
        return {"overrides": [], "rules": [], "default": {"tier": "其他赛事", "why": "默认"}}
    with open(RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def infer_tier(name, rules=None):
    rules = rules or load_rules()
    for r in rules.get("overrides", []):
        if re.search(r["pattern"], name):
            return r["tier"], "override：" + r.get("why", r["pattern"])
    for r in rules.get("rules", []):
        if re.search(r["pattern"], name):
            return r["tier"], r.get("why", r["pattern"])
    d = rules.get("default", {"tier": "其他赛事", "why": "未命中"})
    return d["tier"], d["why"]


# ---------------------------------------------------------------- 命令：查看

def cmd_list(a):
    doc = Doc(a.html)
    tours = doc.tours
    rows = []
    for i, t in enumerate(tours):
        if a.year and not (t.get("start", "").startswith(a.year) or t.get("end", "").startswith(a.year)):
            continue
        if a.tier and t.get("tier") != a.tier:
            continue
        if a.grep and norm(a.grep) not in norm(t["name"]):
            continue
        rows.append((i, t))
    print("%-4s %-10s %-10s %-14s %-6s %-5s %s" % ("idx", "start", "end", "tier", "战绩", "局数", "name"))
    for i, t in rows:
        rec = "%d-%d" % (t.get("wins", 0), t.get("losses", 0))
        if t.get("voids"):
            rec += "·%d空" % t["voids"]
        print("%-4d %-10s %-10s %-14s %-6s %-5d %s" % (
            i, t.get("start", ""), t.get("end", ""), t.get("tier", ""),
            rec, len(t.get("games", [])), t["name"]))
    print("\n共 %d 项赛事（筛选后 %d）" % (len(tours), len(rows)))


def cmd_show(a):
    doc = Doc(a.html)
    t = find_tour(doc.D, a.tour)
    i = doc.tours.index(t)
    print("[%d] %s" % (i, t["name"]))
    print("  级别 : %s" % t.get("tier"))
    print("  结果 : %s" % t.get("result"))
    print("  日期 : %s ~ %s" % (t.get("start"), t.get("end")))
    print("  战绩 : %d 胜 %d 负%s" % (t.get("wins", 0), t.get("losses", 0),
                                    (" %d 无胜负" % t["voids"]) if t.get("voids") else ""))
    print("  积分 : cost=%s  awards=%d" % (t.get("cost", 0), len(t.get("awards", []))))
    if t.get("note"):
        print("  备注 : %s" % t["note"])
    print("  对局 %d 局：" % len(t.get("games", [])))
    for g in t.get("games", []):
        r = "空" if g.get("void") else ("胜" if g.get("win") else "负")
        print("    %s  %s 执%s  %-8s %s%s%s" % (
            g["date"], r, g.get("color", "?"), g.get("opp", ""),
            g.get("label", ""),
            ("  [%s]" % g["result"]) if g.get("result") else "",
            ("  ▶%d 视频" % len(g["bili"])) if g.get("bili") else ""))
    # 关联的视频分组
    for g in doc.groups:
        if g.get("kind") == "tour" and g.get("name") == t["name"]:
            print("  视频分组：%s（%d 个）" % (g["name"], len(g.get("items", []))))


def cmd_guess_tier(a):
    tier, why = infer_tier(a.name)
    print("%s\n  -> %s\n  依据：%s" % (a.name, tier, why))
    if tier not in KNOWN_TIERS and tier != "网络对局":
        warn("该 tier 不在站点已知列表内，前端配色可能缺失")


def cmd_stats(a):
    doc = Doc(a.html)
    T = doc.tours
    w = sum(t.get("wins", 0) for t in T)
    l = sum(t.get("losses", 0) for t in T)
    v = sum(t.get("voids", 0) for t in T)
    champs = [t for t in T if t.get("tier") == "世界大赛" and t.get("result") == "冠军"]
    print("赛事 %d 项 / 对局 %d 局（%d 胜 %d 负 %d 无胜负）" % (len(T), w + l + v, w, l, v))
    print("世界冠军 %d 个" % len(champs))
    print("时间跨度 %s ~ %s" % (min(t.get("start", "") for t in T), max(t.get("end", "") for t in T)))
    print("视频分组 %d 组 / 视频 %d 个" % (len(doc.groups), sum(len(g.get("items", [])) for g in doc.groups)))


# ---------------------------------------------------------------- 命令：写入

def cmd_add_tour(a):
    doc = Doc(a.html)
    if find_tour(doc.D, a.name, required=False):
        die("已存在同名赛事：%s" % a.name)
    start = parse_date(a.start)
    end = parse_date(a.end) if a.end else start
    if end < start:
        die("end (%s) 早于 start (%s)" % (end, start))

    if a.tier:
        tier, why = a.tier, "手动指定"
    else:
        tier, why = infer_tier(a.name)
    if tier not in KNOWN_TIERS:
        if tier == "网络对局":
            warn("「网络对局」不进赛事时间线。网棋请用 add-video --net 挂到视频分组。")
        else:
            warn("tier=%r 不在已知列表 %s" % (tier, KNOWN_TIERS))

    result = a.result
    if result is None:
        result = "进行中" if end >= datetime.date.today() else "待补结果"

    t = {
        "name": a.name,
        "tier": tier,
        "result": result,
        "awards": [],
        "cost": a.cost,
        "note": a.note or "",
        "double": bool(a.double),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "wins": 0, "losses": 0, "voids": 0,
        "games": [],
        "entry": "",
        "bili_rest": [],
        "vfail": 0, "vwarn": 0, "vissues": [],
    }
    doc.tours.append(t)
    sort_tours(doc.tours)
    ok("新增赛事：%s  [%s]  %s ~ %s  结果=%s" % (a.name, tier, t["start"], t["end"], result))
    print("  tier 依据：%s" % why)
    print("  当前序号：%d" % doc.tours.index(t))
    doc.save(dry=a.dry_run, backup=not a.no_backup, note="add-tour")


def cmd_add_game(a):
    doc = Doc(a.html)
    t = find_tour(doc.D, a.tour)
    d = parse_date(a.date)

    if a.result not in ("win", "loss", "void"):
        die("--result 只能是 win / loss / void")
    void = a.result == "void"
    win = (a.result == "win")

    for g in t.get("games", []):
        if g.get("date") == d.isoformat() and g.get("opp") == a.opp:
            die("该赛事已有 %s 对 %s 的对局，若要覆盖请先手工删掉或加 --force 前先确认" % (a.date, a.opp))

    g = {
        "date": d.isoformat(),
        "label": a.label or ("%s 对%s" % (t["name"], a.opp)),
        "opp": a.opp,
        "color": a.color,
        "win": win,
        "void": void,
        "moves": a.moves or 0,
        "id": a.id or 0,
        "result": a.result_text or ("和棋" if void else ""),
        "bili": [],
    }
    t.setdefault("games", []).append(g)
    t["games"].sort(key=lambda x: x["date"])
    before = (t.get("start"), t.get("end"))
    recompute_tour(t)

    ok("已加对局：%s 执%s 对%s  %s" % (d.isoformat(), a.color, a.opp,
                                    "胜" if win else ("负" if not void else "无胜负")))
    if before != (t.get("start"), t.get("end")):
        print("  赛期自动调整：%s ~ %s -> %s ~ %s" % (before[0], before[1], t["start"], t["end"]))
    print("  当前战绩：%d 胜 %d 负%s" % (t["wins"], t["losses"],
                                    (" %d 无胜负" % t["voids"]) if t["voids"] else ""))
    if not g["id"]:
        warn("未提供 --id（星阵棋谱号），该局不会出现「谱」按钮；有谱号可事后补：add-game 同参数 + --id")
    if a.result_text == "" and not void:
        warn("未提供 --result-text（如「黑中盘胜」），对局明细会空着这一列")
    sync_group_sub(doc, t)
    doc.save(dry=a.dry_run, backup=not a.no_backup, note="add-game")


def cmd_del_game(a):
    """删除一局（用于清理重复录入）。默认一次只删一局，--all 才全删。"""
    doc = Doc(a.html)
    t = find_tour(doc.D, a.tour)
    games = t.get("games", [])
    keep, removed = [], []
    for g in games:
        hit = (g.get("date") == a.date and g.get("opp") == a.opp)
        if hit and a.label is not None:
            hit = a.label in (g.get("label") or "")
        if hit and a.color:
            hit = g.get("color") == a.color
        (removed if hit else keep).append(g)
    if not removed:
        die("没有匹配的对局（%s 对 %s%s）"
            % (a.date, a.opp, ("，label 含 %r" % a.label) if a.label else ""))
    if len(removed) > 1 and not a.all:
        print("匹配到 %d 局，请用 --label / --color 缩小范围，或加 --all 全删：" % len(removed))
        for g in removed:
            print("  %s 执%s  %s" % (g["date"], g.get("color"), g.get("label")))
        sys.exit(3)
    t["games"] = keep
    recompute_tour(t)
    ok("已从「%s」删除 %d 局：" % (t["name"], len(removed)))
    for g in removed:
        print("  - %s 执%s  %s" % (g["date"], g.get("color"), g.get("label")))
    print("  当前战绩：%d 胜 %d 负（共 %d 局）" % (t["wins"], t["losses"], len(keep)))
    doc.save(dry=a.dry_run, backup=not a.no_backup, note="del-game")


def cmd_set_game_result(a):
    """改单局的结果文字（如把「黑中盘胜」改成「黑超时胜」）。"""
    doc = Doc(a.html)
    t = find_tour(doc.D, a.tour)
    hits = [g for g in t.get("games", [])
            if g.get("date") == a.date and g.get("opp") == a.opp
            and (not a.label or a.label in (g.get("label") or ""))]
    if not hits:
        die("找不到对局：%s 对 %s" % (a.date, a.opp))
    if len(hits) > 1:
        print("匹配到 %d 局，请加 --label 缩小范围：" % len(hits))
        for g in hits:
            print("  %s 执%s %s | %s" % (g["date"], g.get("color"), g.get("label"), g.get("result")))
        sys.exit(3)
    g = hits[0]
    old = g.get("result")
    g["result"] = a.result
    ok("%s 对 %s：%s -> %s" % (g["date"], g["opp"], old or "(空)", a.result))
    doc.save(dry=a.dry_run, backup=not a.no_backup, note="set-game-result")


def cmd_set_result(a):
    doc = Doc(a.html)
    t = find_tour(doc.D, a.tour)
    old = t.get("result")
    t["result"] = a.result
    if a.end:
        t["end"] = parse_date(a.end).isoformat()
    sync_group_sub(doc, t)
    ok("%s\n  结果：%s -> %s" % (t["name"], old, a.result))
    doc.save(dry=a.dry_run, backup=not a.no_backup, note="set-result")


def cmd_set_group(a):
    doc = Doc(a.html)
    g = find_group(doc.D, a.group)
    if a.name:
        g["name"] = a.name
    if a.sub is not None:
        g["sub"] = a.sub
    if a.tier is not None:
        g["tier"] = a.tier
    ok("分组已更新：%s | %s" % (g["name"], g.get("sub", "")))
    doc.save(dry=a.dry_run, backup=not a.no_backup, note="set-group")


def cmd_merge_groups(a):
    doc = Doc(a.html)
    src = find_group(doc.D, a.src)
    dst = find_group(doc.D, a.dst)
    if src is dst:
        die("源与目标相同")
    have = {it.get("bvid") for it in dst.get("items", []) if it.get("bvid")}
    moved = skipped = 0
    for it in list(src.get("items", [])):
        if it.get("bvid") and it["bvid"] in have:
            skipped += 1
            continue
        dst.setdefault("items", []).append(it)
        if it.get("bvid"):
            have.add(it["bvid"])
        moved += 1
    dst["items"].sort(key=lambda x: x.get("date", ""))
    doc.groups.remove(src)
    ok("合并「%s」-> 「%s」：移入 %d 个，去重跳过 %d 个" % (src["name"], dst["name"], moved, skipped))
    print("  源分组已删除；目标现有 %d 个视频" % len(dst["items"]))
    doc.save(dry=a.dry_run, backup=not a.no_backup, note="merge-groups")


def cmd_add_video(a):
    doc = Doc(a.html)
    if not a.bvid:
        die("必须给 --bvid")
    bvid = a.bvid.strip()
    if not re.fullmatch(r"BV[0-9A-Za-z]{10}", bvid):
        warn("bvid 格式不像标准 BV 号：%s" % bvid)
    # 全局去重
    for g in doc.groups:
        for it in g.get("items", []):
            if it.get("bvid") == bvid:
                die("该视频已在分组「%s」里：%s" % (g["name"], it.get("title", "")))

    item = {
        "bvid": bvid,
        "title": a.title or bvid,
        "date": (parse_date(a.date).isoformat() if a.date else today_str()),
        "url": "https://www.bilibili.com/video/%s" % bvid,
        "kind": a.kind or "对局",
    }
    if not a.title:
        warn("未提供 --title，标题会显示成 BV 号")

    # 目标一：某局的 bili 数组
    if a.game:
        if "|" not in a.game:
            die('--game 格式为 "YYYY-MM-DD|对手名"')
        dstr, opp = a.game.split("|", 1)
        found = None
        for t in doc.tours:
            for g in t.get("games", []):
                if g.get("date") == dstr and g.get("opp") == opp:
                    found = g
        if not found:
            die("找不到对局：%s 对 %s" % (dstr, opp))
        item["why"] = a.why or "讲解"
        found.setdefault("bili", []).append(item)
        ok("已挂到对局 %s 对 %s" % (dstr, opp))
        doc.save(dry=a.dry_run, backup=not a.no_backup, note="add-video")
        return

    # 目标二：某赛事的分组
    if a.tour:
        t = find_tour(doc.D, a.tour)
        g = None
        for x in doc.groups:
            if x.get("kind") == "tour" and x.get("name") == t["name"]:
                g = x
        if g is None:
            g = {"kind": "tour", "name": t["name"], "sub": tour_sub(t),
                 "tier": t.get("tier", ""), "sort": t.get("end", ""), "items": []}
            doc.groups.append(g)
            print("  为赛事新建视频分组")
        item["tour"] = t["name"]
        g.setdefault("items", []).append(item)
        g["items"].sort(key=lambda x: x.get("date", ""))
        ok("已加入分组「%s」（现 %d 个）" % (g["name"], len(g["items"])))
        doc.save(dry=a.dry_run, backup=not a.no_backup, note="add-video")
        return

    # 目标三：--net 或 --group
    if a.net:
        g = find_group(doc.D, "网棋", required=False)
        if g is None:
            g = {"kind": "kind", "name": "野狐网棋 · 网络对局",
                 "sub": "线上对局：野狐人气争霸赛、潜伏激斗传、中日棋圣大战等（网络对局）",
                 "tier": "", "sort": "", "items": []}
            doc.groups.append(g)
            print("  新建「野狐网棋 · 网络对局」分组")
        if not item["kind"] or item["kind"] == "对局":
            item["kind"] = "野狐网棋"
    elif a.group:
        g = find_group(doc.D, a.group)
    else:
        die("请指定视频去处：--game / --tour / --net / --group")

    g.setdefault("items", []).append(item)
    g["items"].sort(key=lambda x: x.get("date", ""))
    ok("已加入分组「%s」（现 %d 个）" % (g["name"], len(g["items"])))
    doc.save(dry=a.dry_run, backup=not a.no_backup, note="add-video")


def sync_group_sub(doc, t):
    """把赛事分组的 sub 与赛事本体对齐。"""
    for g in doc.groups:
        if g.get("kind") == "tour" and g.get("name") == t["name"]:
            g["sub"] = tour_sub(t)
            g["tier"] = t.get("tier", "")


# ---------------------------------------------------------------- 倒计时

def cmd_list_countdown(a):
    doc = Doc(a.html)
    cds = doc.D.get("countdowns", [])
    if not cds:
        print("（暂无倒计时）")
        return
    today = datetime.date.today()
    for i, c in enumerate(cds):
        d = parse_date(c["date"])
        n = (d - today).days
        state = ("还有 %d 天" % n) if n > 0 else ("就是今天" if n == 0 else "已过 %d 天" % -n)
        print("[%d] %-22s %s  %s  %s" % (i, c.get("name", ""), c["date"], state, c.get("note", "")))


def cmd_add_countdown(a):
    doc = Doc(a.html)
    d = parse_date(a.date)
    cds = doc.D.setdefault("countdowns", [])
    for c in cds:
        if c.get("name") == a.name:
            c["date"] = d.isoformat()
            c["note"] = a.note or c.get("note", "")
            ok("已更新倒计时：%s -> %s" % (a.name, d.isoformat()))
            doc.save(dry=a.dry_run, backup=not a.no_backup, note="add-countdown")
            return
    cds.append({"name": a.name, "date": d.isoformat(), "note": a.note or ""})
    cds.sort(key=lambda c: c["date"])
    ok("已新增倒计时：%s  %s" % (a.name, d.isoformat()))
    doc.save(dry=a.dry_run, backup=not a.no_backup, note="add-countdown")


def cmd_del_countdown(a):
    doc = Doc(a.html)
    cds = doc.D.get("countdowns", [])
    keep = [c for c in cds if c.get("name") != a.name]
    if len(keep) == len(cds):
        die("没有名为 %r 的倒计时" % a.name)
    doc.D["countdowns"] = keep
    ok("已删除倒计时：%s" % a.name)
    doc.save(dry=a.dry_run, backup=not a.no_backup, note="del-countdown")


# ---------------------------------------------------------------- 校验

SGFZ_RE = re.compile(r"const SGFZ = '([A-Za-z0-9+/=]+)';")


def _sgf_db(doc):
    """解出内嵌棋谱库：{星阵id: sgf文本}。"""
    m = SGFZ_RE.search(doc.text)
    if not m:
        die("找不到内嵌棋谱块 `const SGFZ = '...'`")
    try:
        db = json.loads(gzip.decompress(base64.b64decode(m.group(1))).decode("utf-8"))
    except Exception as e:
        die("棋谱块解压失败：%s" % e)
    return m, db


def _sgf_put(doc, m, db):
    """把棋谱库压回去，替换 doc.text 里的 base64。"""
    raw = json.dumps(db, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    b64 = base64.b64encode(gzip.compress(raw, 9)).decode("ascii")
    doc.text = doc.text[:m.start(1)] + b64 + doc.text[m.end(1):]
    return len(b64)


def cmd_add_sgf(a):
    """给某一局挂上 SGF（写进内嵌棋谱库 + 登记 gl 映射）。"""
    doc = Doc(a.html)
    t = find_tour(doc.D, a.tour)
    hits = [g for g in t.get("games", [])
            if g.get("date") == a.date and g.get("opp") == a.opp]
    if not hits:
        die("找不到对局：%s 对 %s" % (a.date, a.opp))
    if len(hits) > 1:
        print("匹配到 %d 局，请加 --label 区分：" % len(hits))
        for g in hits:
            print("  %s 执%s %s" % (g["date"], g.get("color"), g.get("label")))
        sys.exit(3)
    g = hits[0]

    if not os.path.exists(a.file):
        die("找不到 SGF 文件：%s" % a.file)
    with open(a.file, encoding="utf-8", errors="replace") as f:
        sgf = f.read().strip()
    if "(;" not in sgf:
        die("这不像 SGF：开头没有 `(;`")
    nmv = len(re.findall(r";\s*[BW]\[[a-z]{0,2}\]", sgf))
    if nmv < 2:
        die("SGF 里只识别到 %d 手，检查一下文件" % nmv)

    m, db = _sgf_db(doc)
    key = "%s|%s" % (g["date"], g["opp"])
    old = (doc.D.get("gl") or {}).get(key)

    if a.id:
        gid = str(a.id)
        if gid in db and not a.force:
            die("棋谱库里已有 id=%s，换个 --id 或加 --force 覆盖" % gid)
    elif old is not None:
        gid = str(old)          # 这局本来就登记过，直接覆盖原条目
    else:
        nums = [int(k) for k in db if k.isdigit()]
        gid = str(max(nums) + 1 if nums else 1)

    db[gid] = sgf
    size = _sgf_put(doc, m, db)

    doc.D.setdefault("gl", {})[key] = int(gid)
    g["id"] = int(gid)

    ok("%s 对 %s：已挂棋谱 id=%s（%d 手，%d 字符）" % (g["date"], g["opp"], gid, nmv, len(sgf)))
    print("  棋谱库 %d 局，压缩后 base64 %.0f KB" % (len(db), size / 1024))
    if old is not None and str(old) != gid:
        print("  原登记 id=%s 已被替换" % old)
    doc.save(dry=a.dry_run, backup=not a.no_backup, note="add-sgf")


def cmd_list_quotes(a):
    doc = Doc(a.html)
    qs = doc.D.get("quotes", [])
    if not qs:
        print("（暂无一言）")
        return
    for i, q in enumerate(qs):
        print("[%2d] %s" % (i, q.get("t", "")))
        print("      —— %s" % (q.get("s") or "（无出处）"))
    print("\n共 %d 条" % len(qs))


def cmd_add_quote(a):
    doc = Doc(a.html)
    qs = doc.D.setdefault("quotes", [])
    t = (a.text or "").strip()
    if not t:
        die("引文不能为空")
    for i, q in enumerate(qs):
        if q.get("t") == t:
            die("这条一言已存在（第 %d 条）" % i)
    if not a.src:
        warn("未给 --src，出处会显示成空")
    qs.append({"t": t, "s": a.src or ""})
    if a.sort:
        qs.sort(key=lambda x: x.get("s", ""))
    ok("已加入一言（现 %d 条）：%s" % (len(qs), t[:44]))
    doc.save(dry=a.dry_run, backup=not a.no_backup, note="add-quote")


def cmd_del_quote(a):
    doc = Doc(a.html)
    qs = doc.D.get("quotes", [])
    if not qs:
        die("暂无一言")
    sel = (a.sel or "").strip()
    if sel.isdigit():
        i = int(sel)
        if not 0 <= i < len(qs):
            die("序号 %d 越界（0..%d）" % (i, len(qs) - 1))
        removed = qs.pop(i)
    else:
        hits = [q for q in qs if sel in q.get("t", "")]
        if not hits:
            die("没有包含 %r 的一言" % sel)
        if len(hits) > 1:
            print("匹配到 %d 条，请用序号删除：" % len(hits))
            for q in hits:
                print("  [%d] %s" % (qs.index(q), q.get("t", "")[:50]))
            sys.exit(3)
        removed = hits[0]
        qs.remove(removed)
    ok("已删除一言（剩 %d 条）：%s" % (len(qs), removed.get("t", "")[:44]))
    doc.save(dry=a.dry_run, backup=not a.no_backup, note="del-quote")


def cmd_validate(a):
    doc = Doc(a.html)
    D = doc.D
    errs, warns = [], []

    names = set()
    for i, t in enumerate(doc.tours):
        tag = "[%d] %s" % (i, t.get("name", "?"))
        if t.get("name") in names:
            errs.append("%s 赛事名重复" % tag)
        names.add(t.get("name"))
        if t.get("tier") not in KNOWN_TIERS:
            warns.append("%s tier=%r 不在已知列表" % (tag, t.get("tier")))
        games = t.get("games", [])
        w = sum(1 for g in games if g.get("win") and not g.get("void"))
        l = sum(1 for g in games if (not g.get("win")) and not g.get("void"))
        v = sum(1 for g in games if g.get("void"))
        if (w, l, v) != (t.get("wins"), t.get("losses"), t.get("voids")):
            errs.append("%s 战绩字段 %s 与实际对局 (%d,%d,%d) 不符" %
                        (tag, (t.get("wins"), t.get("losses"), t.get("voids")), w, l, v))
        seen = set()
        for g in games:
            k = (g.get("date"), g.get("opp"))
            if k in seen:
                # 既有数据里确有「同一局录了两遍」的历史遗留，默认只提醒；
                # 加 --strict 时才算错误。
                (errs if a.strict else warns).append(
                    "%s 同一天重复对同一对手：%s %s" % (tag, k[0], k[1]))
            seen.add(k)
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", g.get("date", "")):
                errs.append("%s 对局日期非法：%r" % (tag, g.get("date")))
            elif not (t.get("start", "") <= g["date"] <= t.get("end", "")):
                errs.append("%s 对局 %s 超出赛期 %s~%s" %
                            (tag, g["date"], t.get("start"), t.get("end")))
            if g.get("color") not in ("B", "W"):
                errs.append("%s 对局 %s 颜色非法：%r" % (tag, g.get("date"), g.get("color")))
        if t.get("start", "") > t.get("end", ""):
            errs.append("%s start 晚于 end" % tag)

    # 视频
    seen_bv = {}
    total_items = 0
    for g in doc.groups:
        for it in g.get("items", []):
            total_items += 1
            bv = it.get("bvid")
            if bv:
                if bv in seen_bv:
                    errs.append("视频 %s 同时出现在「%s」和「%s」" % (bv, seen_bv[bv], g["name"]))
                seen_bv[bv] = g["name"]
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", it.get("date", "")):
                errs.append("「%s」里 %s 日期非法：%r" % (g["name"], bv, it.get("date")))
        if g.get("kind") == "tour" and g.get("name") not in names:
            errs.append("视频分组「%s」对应的赛事不存在" % g.get("name"))

    if D.get("bili_total") and D["bili_total"] != total_items:
        warns.append("bili_total=%d 与实际视频数 %d 不符（页面「共 N 个」会不准）"
                     % (D["bili_total"], total_items))

    # 一言
    qs = D.get("quotes") or []
    if len(qs) < 2:
        warns.append("一言只有 %d 条，随机换句至少需要 2 条" % len(qs))
    seen_q = {}
    for i, q in enumerate(qs):
        t = (q.get("t") or "").strip()
        if not t:
            errs.append("一言第 %d 条内容为空" % i)
        if not (q.get("s") or "").strip():
            warns.append("一言第 %d 条没有出处：%s" % (i, t[:20]))
        if t in seen_q:
            errs.append("一言重复（第 %d 与第 %d 条）：%s" % (seen_q[t], i, t[:24]))
        seen_q[t] = i

    # verify_summary 是否过期
    vs = D.get("verify_summary") or {}
    tw = sum(len(t.get("games", [])) for t in doc.tours)
    if vs.get("tours") not in (None, len(doc.tours)):
        warns.append("verify_summary.tours=%s 与现有 %d 项赛事不符" % (vs.get("tours"), len(doc.tours)))
    if vs.get("games") not in (None, tw):
        warns.append("verify_summary.games=%s 与现有 %d 局不符" % (vs.get("games"), tw))

    print("赛事 %d 项 / 对局 %d 局 / 视频 %d 个（%d 组）" %
          (len(doc.tours), tw, total_items, len(doc.groups)))
    if errs:
        print("\n✗ 错误 %d 条：" % len(errs))
        for e in errs:
            print("  - " + e)
    if warns:
        print("\n! 提醒 %d 条：" % len(warns))
        for w in warns:
            print("  - " + w)
    if not errs and not warns:
        print("\n✓ 全部通过")
    sys.exit(1 if errs else 0)


def cmd_sync(a):
    doc = Doc(a.html)
    n = 0
    for t in doc.tours:
        before = (t.get("wins"), t.get("losses"), t.get("voids"))
        recompute_tour(t)
        if before != (t.get("wins"), t.get("losses"), t.get("voids")):
            n += 1
    sort_tours(doc.tours)
    for t in doc.tours:
        sync_group_sub(doc, t)
    total_items = sum(len(g.get("items", [])) for g in doc.groups)
    doc.D["bili_total"] = total_items
    vs = doc.D.get("verify_summary")
    if isinstance(vs, dict):
        vs["tours"] = len(doc.tours)
        vs["games"] = sum(len(t.get("games", [])) for t in doc.tours)
    ok("同步完成：重算 %d 项赛事战绩，bili_total=%d，verify_summary 计数已对齐" % (n, total_items))
    warn("verify_summary 里的 checks/passed/failed 是历史校验结果，新增对局后建议重跑校验脚本")
    doc.save(dry=a.dry_run, backup=not a.no_backup, note="sync")


# ---------------------------------------------------------------- CLI

def build_parser():
    p = argparse.ArgumentParser(
        prog="kejie.py",
        description="柯洁档案维护工具：直接改 index.html 内嵌数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    p.add_argument("--html", default=DEFAULT_HTML, help="index.html 路径")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp):
        sp.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
        sp.add_argument("--no-backup", action="store_true", help="不生成备份")

    sp = sub.add_parser("list", help="列出赛事")
    sp.add_argument("--year")
    sp.add_argument("--tier")
    sp.add_argument("--grep")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("show", help="查看单个赛事详情")
    sp.add_argument("tour")
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("guess-tier", help="推断赛事级别")
    sp.add_argument("name")
    sp.set_defaults(func=cmd_guess_tier)

    sp = sub.add_parser("stats", help="总量统计")
    sp.set_defaults(func=cmd_stats)

    sp = sub.add_parser("add-tour", help="新增赛事")
    sp.add_argument("name")
    sp.add_argument("--start", required=True)
    sp.add_argument("--end")
    sp.add_argument("--tier", help="不给则自动推断")
    sp.add_argument("--result", help="不给则按日期自动判（进行中 / 待补结果）")
    sp.add_argument("--note", default="")
    sp.add_argument("--cost", type=int, default=0)
    sp.add_argument("--double", action="store_true")
    add_common(sp)
    sp.set_defaults(func=cmd_add_tour)

    sp = sub.add_parser("add-game", help="给赛事追加一局")
    sp.add_argument("tour")
    sp.add_argument("--date", required=True)
    sp.add_argument("--opp", required=True)
    sp.add_argument("--color", required=True, choices=["B", "W"])
    sp.add_argument("--result", required=True, choices=["win", "loss", "void"])
    sp.add_argument("--moves", type=int, default=0)
    sp.add_argument("--label", default="")
    sp.add_argument("--id", type=int, default=0, help="星阵棋谱号，用于「谱」按钮")
    sp.add_argument("--result-text", default="", help="如「黑中盘胜」")
    add_common(sp)
    sp.set_defaults(func=cmd_add_game)

    sp = sub.add_parser("del-game", help="删除一局（清理重复录入）")
    sp.add_argument("tour")
    sp.add_argument("--date", required=True)
    sp.add_argument("--opp", required=True)
    sp.add_argument("--label", help="只删 label 含该子串的（用于区分同日的简写/详写两条）")
    sp.add_argument("--color", choices=["B", "W"])
    sp.add_argument("--all", action="store_true", help="匹配到多局时全部删除")
    add_common(sp)
    sp.set_defaults(func=cmd_del_game)

    sp = sub.add_parser("set-game-result", help="改单局结果文字（超时 / 判负等）")
    sp.add_argument("tour")
    sp.add_argument("--date", required=True)
    sp.add_argument("--opp", required=True)
    sp.add_argument("--result", required=True)
    sp.add_argument("--label")
    add_common(sp)
    sp.set_defaults(func=cmd_set_game_result)

    sp = sub.add_parser("set-result", help="更新赛事结果 / 收尾未完赛")
    sp.add_argument("tour")
    sp.add_argument("result")
    sp.add_argument("--end", help="同时修正结束日期")
    add_common(sp)
    sp.set_defaults(func=cmd_set_result)

    sp = sub.add_parser("set-group", help="改视频分组的名称/说明")
    sp.add_argument("group")
    sp.add_argument("--name")
    sp.add_argument("--sub")
    sp.add_argument("--tier")
    add_common(sp)
    sp.set_defaults(func=cmd_set_group)

    sp = sub.add_parser("merge-groups", help="把源分组并入目标分组并删除源")
    sp.add_argument("src")
    sp.add_argument("dst")
    add_common(sp)
    sp.set_defaults(func=cmd_merge_groups)

    sp = sub.add_parser("add-video", help="挂视频（对局 / 赛事 / 网棋 / 指定分组）")
    sp.add_argument("--bvid", required=True)
    sp.add_argument("--title", default="")
    sp.add_argument("--date", default="")
    sp.add_argument("--kind", default="")
    sp.add_argument("--why", default="")
    sp.add_argument("--game", help='"YYYY-MM-DD|对手"')
    sp.add_argument("--tour")
    sp.add_argument("--net", action="store_true", help="进「野狐网棋」分组")
    sp.add_argument("--group")
    add_common(sp)
    sp.set_defaults(func=cmd_add_video)

    sp = sub.add_parser("list-countdown", help="列出倒计时")
    sp.set_defaults(func=cmd_list_countdown)

    sp = sub.add_parser("add-countdown", help="新增/更新倒计时")
    sp.add_argument("name")
    sp.add_argument("date")
    sp.add_argument("--note", default="")
    add_common(sp)
    sp.set_defaults(func=cmd_add_countdown)

    sp = sub.add_parser("del-countdown", help="删除倒计时")
    sp.add_argument("name")
    add_common(sp)
    sp.set_defaults(func=cmd_del_countdown)

    sp = sub.add_parser("add-sgf", help="给某局挂 SGF 棋谱")
    sp.add_argument("tour")
    sp.add_argument("--date", required=True)
    sp.add_argument("--opp", required=True)
    sp.add_argument("--file", required=True, help="SGF 文件路径")
    sp.add_argument("--id", type=int, help="星阵棋谱号，不给则自动分配")
    sp.add_argument("--force", action="store_true", help="允许覆盖已有 id")
    add_common(sp)
    sp.set_defaults(func=cmd_add_sgf)

    sp = sub.add_parser("list-quotes", help="列出一言")
    sp.set_defaults(func=cmd_list_quotes)

    sp = sub.add_parser("add-quote", help="新增一条一言")
    sp.add_argument("text")
    sp.add_argument("--src", default="", help="出处，如「2020.1 · 《君品谈》」")
    sp.add_argument("--sort", action="store_true", help="按出处排序后写入")
    add_common(sp)
    sp.set_defaults(func=cmd_add_quote)

    sp = sub.add_parser("del-quote", help="删除一言（按序号或引文片段）")
    sp.add_argument("sel")
    add_common(sp)
    sp.set_defaults(func=cmd_del_quote)

    sp = sub.add_parser("validate", help="一致性校验")
    sp.add_argument("--strict", action="store_true", help="把「同日重复对手」也算错误")
    sp.set_defaults(func=cmd_validate)

    sp = sub.add_parser("sync", help="重算战绩、排序、对齐分组说明与计数")
    add_common(sp)
    sp.set_defaults(func=cmd_sync)

    return p


def main():
    setup_stdout()
    p = build_parser()
    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()