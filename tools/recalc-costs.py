# -*- coding: utf-8 -*-
"""复现 / 重算马氏积分的参赛扣分链。

模型（与 index.html 里的 remain() 一致）：
  单条积分账户 e = {date, V, grace, spends:[[date, amount], ...]}
  remain(e, day) = max(0, V - Σ spends(<=day) - max(0, (day-date) - grace))
  balance(day)   = Σ remain(e, day)

扣分是「先进先出消耗」：按日期顺序处理每个赛事，从最老的仍有余额的账户里扣。

用法：
  python tools/recalc-costs.py --check          # 用现有日期复算，和存量数据比对
  python tools/recalc-costs.py --by-start --dry-run
  python tools/recalc-costs.py --by-start       # 真正写回
"""
import argparse
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_HTML = os.path.join(ROOT, "index.html")
DATA_RE = re.compile(r"^const D = (\{.*\});[ \t]*$", re.M)

EPOCH = datetime.date(1970, 1, 1)


def dnum(s):
    y, m, d = (int(x) for x in s.split("-"))
    return (datetime.date(y, m, d) - EPOCH).days


def remain(e, day, spends):
    """spends: {entry_index: [[date, amount], ...]}"""
    elapsed = dnum(day) - dnum(e["date"])
    if elapsed < 0:
        return None
    spent = sum(a for d, a in spends.get(id(e), []) if dnum(d) <= dnum(day))
    return max(0, e["V"] - spent - max(0, elapsed - e["grace"]))


def balance(entries, spends, day):
    t = 0
    for e in entries:
        r = remain(e, day, spends)
        if r is not None:
            t += r
    return t


def rebuild(entries, costs, cost_dates, verbose=False):
    """按 cost_dates 重算 spends / before / after / applied。

    注意：FIFO 必须按「新日期」的先后顺序处理，不能沿用原数组顺序——
    把扣分日从结束日改到首局日后，两者顺序会不一致。
    返回的 out 仍与输入 costs 一一对齐，方便逐条比对。
    """
    spends = {id(e): [] for e in entries}
    out = [None] * len(cost_dates)
    order = sorted(range(len(cost_dates)), key=lambda i: (cost_dates[i][1], i))
    for i in order:
        c, day = cost_dates[i]
        avail = balance(entries, spends, day)
        need = c["need"]
        applied = avail >= need
        if applied:
            left = need
            for e in sorted(entries, key=lambda x: (x["date"], entries.index(x))):
                if e["date"] > day:
                    continue
                r = remain(e, day, spends)
                if not r:
                    continue
                take = min(r, left)
                spends[id(e)].append([day, take])
                left -= take
                if left == 0:
                    break
            assert left == 0, "FIFO 未扣满：%s 缺 %d" % (c["tour"], left)
        out[i] = {
            "date": day,
            "tour": c["tour"],
            "need": need,
            "before": avail,
            "applied": applied,
            "after": avail - need if applied else avail,
        }
        if verbose:
            print("  %s need=%-3d before=%-4d %s" % (day, need, avail, "扣" if applied else "不扣"))
    return out, spends


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", default=DEFAULT_HTML)
    ap.add_argument("--check", action="store_true", help="用现有日期复算并比对")
    ap.add_argument("--by-start", action="store_true", help="扣分日改成首局日")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    text = open(a.html, encoding="utf-8").read()
    m = DATA_RE.search(text)
    D = json.loads(m.group(1))
    entries, costs = D["entries"], D["costs"]
    tours = {t["name"]: t for t in D["tours"]}

    # 现有日期
    cur = [(c, c["date"]) for c in costs]
    # 首局日：该赛事第一盘棋的日期
    first_game = {}
    for t in D["tours"]:
        if t["games"]:
            first_game[t["name"]] = min(g["date"] for g in t["games"])
    # 参赛扣分应发生在「参赛」之时：取「已知报名日」与「首局日」中较早者。
    # 报名日通常早于首局（春兰杯、南洋杯等），首局日是没有报名日时的最佳近似；
    # 两者都远早于「结束日」——原数据有 28 条错用了结束日。
    by_start = []
    for c in costs:
        fg = first_game.get(c["tour"]) or tours[c["tour"]]["start"]
        by_start.append((c, min(c["date"], fg)))

    if a.check:
        out, spends = rebuild(entries, costs, cur)
        bad = 0
        for got, want in zip(out, costs):
            if (got["before"], got["after"], got["applied"]) != (want["before"], want["after"], want["applied"]):
                bad += 1
                print("  ✗ %-28s 算得 before=%-4d after=%-4d %s | 存量 before=%-4d after=%-4d %s" % (
                    got["tour"][:26], got["before"], got["after"], got["applied"],
                    want["before"], want["after"], want["applied"]))
        # spends 比对
        sp_bad = 0
        for e in entries:
            old = sorted(e.get("spends", []))
            new = sorted(spends[id(e)])
            if old != new:
                sp_bad += 1
                if sp_bad <= 5:
                    print("  ✗ spends 不一致 %s %s\n      存量 %s\n      算得 %s" % (
                        e["date"], e["label"], old[:4], new[:4]))
        print("\ncosts 字段不一致 %d / %d；spends 不一致 %d / %d" % (bad, len(costs), sp_bad, len(entries)))
        return

    if not a.by_start:
        ap.error("需要 --check 或 --by-start")

    # 先看差异
    out, spends = rebuild(entries, costs, by_start, verbose=False)
    print("按首局日重算（前 6 条对比）：")
    for (c, day), got in list(zip(by_start, out))[:6]:
        print("  %-26s %s -> %s   before %d -> %d  %s" % (
            c["tour"][:26], c["date"], day, c["before"], got["before"],
            "" if c["applied"] == got["applied"] else ("【扣/不扣 变了：%s -> %s】" % (c["applied"], got["applied"]))))
    chg = sum(1 for c, g in zip(costs, out) if (c["before"], c["after"], c["applied"]) != (g["before"], g["after"], g["applied"]))
    print("字段变化 %d / %d 条" % (chg, len(costs)))

    # 官方三个校准实例必须仍然成立
    sp = {id(e): list(spends[id(e)]) for e in entries}
    chunlan = next((g for g in out if "第16届春兰杯" in g["tour"]), None)
    checks = [
        ("实例1 · 2026-04-08 应为 90", balance(entries, sp, "2026-04-08"), 90),
        ("实例2 · 春兰杯报名前应为 90", chunlan["before"] if chunlan else None, 90),
        ("实例3 · 2026-05-08 应为 0", balance(entries, sp, "2026-05-08"), 0),
    ]
    print("\n官方校准：")
    for name, got, want in checks:
        print("  %s %s  实际 %s" % ("✓" if got == want else "✗", name, got))

    if a.dry_run:
        print("dry-run：未写入")
        return

    # 写回：costs 按日期排序，表格才会按时间顺序显示
    for e in entries:
        e["spends"] = sorted(spends[id(e)])
    D["costs"] = sorted(out, key=lambda c: c["date"])
    payload = json.dumps(D, ensure_ascii=False, separators=(",", ":"))
    new = text[:m.start(1)] + payload + text[m.end(1):]
    import shutil
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(a.html, os.path.join(os.path.dirname(a.html), "index.backup.%s-recalc.html" % ts))
    open(a.html, "w", encoding="utf-8", newline="\n").write(new)
    print("✓ 已写回 %s" % a.html)


if __name__ == "__main__":
    main()
