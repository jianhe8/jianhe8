# -*- coding: utf-8 -*-
"""把站点打包成可直接丢到 GitHub Pages 的 zip。

产物结构（解压后整目录推到仓库根即可）：
    kejie-site/
      index.html
      .nojekyll            # 关掉 Jekyll，避免中文文件名/下划线被处理
      shots/rule1..6.png   # 「规则与校准」页引用的截图
      tools/kejie.py       # 维护工具（可选，Pages 不会执行）
      tools/tier-rules.json
"""
import os, sys, zipfile, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'dist')
NAME = 'kejie-site'
ZIP = os.path.join(OUT, NAME + '.zip')


def add(zf, src, arc):
    if os.path.isfile(src):
        zf.write(src, arc)
        return 1
    n = 0
    for base, _, files in os.walk(src):
        for f in files:
            p = os.path.join(base, f)
            rel = os.path.relpath(p, src)
            zf.write(p, os.path.join(arc, rel).replace('\\', '/'))
            n += 1
    return n


def main():
    os.makedirs(OUT, exist_ok=True)
    idx = os.path.join(ROOT, 'index.html')
    if not os.path.exists(idx):
        sys.exit('找不到 index.html')

    count = 0
    with zipfile.ZipFile(ZIP, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(idx, NAME + '/index.html'); count += 1
        # .nojekyll 必须是空文件
        zf.writestr(NAME + '/.nojekyll', ''); count += 1
        for f in ('README.md', '.gitignore'):
            p = os.path.join(ROOT, f)
            if os.path.exists(p):
                zf.write(p, NAME + '/' + f); count += 1
        shots = os.path.join(ROOT, 'shots')
        if os.path.isdir(shots):
            count += add(zf, shots, NAME + '/shots')
        for f in ('kejie.py', 'tier-rules.json'):
            p = os.path.join(ROOT, 'tools', f)
            if os.path.exists(p):
                zf.write(p, NAME + '/tools/' + f); count += 1

    size = os.path.getsize(ZIP)
    print('打包完成：%s' % ZIP)
    print('  文件数 %d，压缩包 %.1f KB' % (count, size / 1024))
    print('  解压后把 %s/ 里的内容推到仓库根目录即可，GitHub Pages 会直接读 index.html' % NAME)


if __name__ == '__main__':
    main()
