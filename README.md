# 柯洁 · 战绩与马氏积分档案

一个单文件的柯洁围棋生涯档案：**257 项赛事、1127 局可核对的正式对局、8(9) 个世界冠军**，以及按 2012 版国家队参赛积分条例（马氏积分）逐日重算的积分账户。

整个站点就是一个 `index.html`，无构建、无依赖、无后端，双击即开，也可以直接丢到 GitHub Pages。

```
257 项赛事 · 1127 局（767 胜 359 负 1 无胜负）· 8(9) 冠 · 189 个讲解视频
2008-07-10 — 2026-07-30
```

---

## 页面结构

| Tab | 内容 |
| --- | --- |
| 赛事时间线 | 8(9) 个世界冠军卡片 + 257 项赛事的时间线，逐局对手 / 执色 / 手数 / 结果，可按年份、级别、积分变动筛选 |
| 积分曲线 | 马氏积分逐日余额曲线，悬停看每日明细 |
| 按日查询 | 任选一天，查当日余额、有效账户数、累计消耗与衰减 |
| 数据校验 | 1567 项自动检查的结果、积分引擎 8 项自检、与外部计算的差异说明 |
| 棋谱 · 讲解 | 明玥谈棋 189 个投稿按赛事归组；「谱」按钮可打开星阵棋谱库的交互式棋谱 |
| 对手志 | 交手记录、按赛事级别的胜负、逐年战绩 |
| 规则与校准 | 2012 版条例原文、赋分明细、参赛扣分逐条判定、外卡记录 |

## 关于「8(9) 冠」

官方确认的世界冠军是 **8 个**（三星杯 4、百灵杯 2、梦百合杯 1、新奥杯 1）。

第 9 冠指 **2025 年 1 月第 29 届 LG 杯**：决赛首局柯洁执黑 2.5 目先下一城，次局因两次提子未放在棋盒盖上被判负，决胜局退赛，中国围棋协会表示不接受该结果。因此本站既不写 8 也不写 9，统一记作 **8(9)**。

代码里只有一个常量控制它：

```js
// index.html
const CHAMP_TXT = worldChamp === 8 ? '8(9)' : String(worldChamp);
```

若第 9 冠将来被正式承认，改这一处即可。

## 积分模型（简述）

每条积分是**独立账户**：满宽限天数后每日 −1，减到 0 为止。

| 类别 | 宽限 |
| --- | --- |
| 世界冠军 | 420 日 |
| 奖励积分 | 250 日 |
| 其余 | 300 日 |

参赛扣分不是「负积分」，而是**先进先出消耗**已有账户，所以任何一天余额都不会为负。种子名额「先有分才给」，余额不足门槛时只能走预选 / 选拔 / 外卡，这三条路都不扣分。

---

## 本地打开

```bash
# 直接双击，或
open index.html          # macOS
start index.html         # Windows
```

没有 npm install，没有 dev server。唯一的外部资源是 `shots/` 下的 6 张条例截图。

## 部署到 GitHub Pages

仓库根目录需要有 `index.html`。`.nojekyll` 用来关掉 Jekyll，避免中文文件名被处理。

```bash
git clone <your-repo> && cd <your-repo>
# 把 index.html、.nojekyll、shots/ 放到根目录
git add . && git commit -m "init" && git push
```

然后在仓库 **Settings → Pages → Source** 选 `main` / `/ (root)`，等一分钟即可。

也可以直接解压 `dist/kejie-site.zip`，把里面 `kejie-site/` 的内容推到根目录。

---

## 数据维护

数据内嵌在 `index.html` 的 `const D = {...}` 里，由 `tools/kejie.py` 读写。**只用标准库，Python 3.8+ 即可**，不装任何包。

```bash
python tools/kejie.py --help
```

每次写入前会自动备份为 `index.backup.<时间戳>.html`，可随时回滚。

### 常用命令

```bash
# 查看
python tools/kejie.py stats
python tools/kejie.py list --year 2026
python tools/kejie.py show 第16届春兰杯

# 新赛事（自动推断级别、自动判「进行中」）
python tools/kejie.py guess-tier "第1届棋仙战世界围棋公开赛预选"
python tools/kejie.py add-tour "第1届棋仙战" --start 2026-11-02 --end 2026-11-06

# 加一局（自动延长赛期、重算战绩）
python tools/kejie.py add-game 第16届春兰杯 --date 2026-12-07 --opp 申真谞 \
    --color B --result win --label 八强战 --result-text "黑中盘胜"

# 改单局结果（超时 / 判负等）
python tools/kejie.py set-game-result 第26届农心辛拉面杯 \
    --date 2024-09-07 --opp 金明训 --result "黑超时胜"

# 收尾未完赛 / 删重复局
python tools/kejie.py set-result 第16届春兰杯 八强
python tools/kejie.py del-game 2012年中国段位赛 --date 2012-07-18 --opp 吴树浩 \
    --label "2012年中国段位赛"

# 视频：挂到具体对局 / 某赛事 / 网棋组
python tools/kejie.py add-video --bvid BV1hVH56jE5E --title "..." --date 2026-10-25 --net
python tools/kejie.py add-video --tour 王中王 --bvid BVxxxx --title "..."
python tools/kejie.py add-video --game "2026-05-25|福冈航太朗" --bvid BVxxxx --title "..."

# 倒计时
python tools/kejie.py list-countdown
python tools/kejie.py add-countdown "棋仙战 · 预选" 2026-11-02 --note "世界棋仙战预选"

# 体检
python tools/kejie.py validate          # 有 --strict 才把「同日重复对手」算错误
python tools/kejie.py sync              # 重算战绩、排序、对齐计数
```

### 边界情况怎么处理

| 场景 | 行为 |
| --- | --- |
| 王中王算什么级别 | `tier-rules.json` 里 override 成「国内头衔战」，不被「争霸赛」带偏 |
| 棋仙战预选 | 规则顺序保证「选拔 / 预选」先于「世界大赛名」命中 |
| 同名赛事歧义 | 输入「春兰杯」会列出 6 届让你选序号，不瞎猜 |
| 未完赛的后续 | `add-game` 自动把 `end` 往后延并重算战绩，`set-result` 收尾 |
| 缺棋谱号 | 只警告，不影响入档；之后可补 `--id` |
| 网棋 | `--net` 直接进「野狐网棋 · 网络对局」分组，不进赛事时间线 |
| 视频重复 | 按 bvid 全局去重 |
| 对手志 | 页面运行时从对局实时聚合，加完对局自动更新，无需额外操作 |

### tier 推断规则

`tools/tier-rules.json`，判定顺序：`overrides` → `rules`（按数组顺序，首个命中生效）→ `default`。

加新比赛类型只要加一条，不用改代码：

```json
{ "pattern": "王中王", "tier": "国内头衔战", "why": "…" }
```

对现有 257 项赛事的复现率约 **86%**，剩余差异集中在「国内头衔战 / 国内邀请赛 / 其他赛事」本身边界模糊的地方，用 `--tier` 手动覆盖即可。

---

## 数据结构

```jsonc
// D.tours[]
{
  "name": "第16届春兰杯世界围棋锦标赛",
  "tier": "世界大赛",              // 见 tier-rules.json
  "result": "进行中",
  "awards": [],                    // 积分奖励 [{date, points, label}]
  "cost": 90,                      // 参赛扣分门槛
  "note": "",
  "double": false,
  "start": "2026-05-25",
  "end": "2026-05-25",
  "wins": 1, "losses": 0, "voids": 0,
  "games": [{
    "date": "2026-05-25",
    "label": "第16届春兰杯世界围棋锦标赛16强战",
    "opp": "福冈航太朗",
    "color": "B",                  // B / W
    "win": true,
    "void": false,
    "moves": 0,
    "id": 0,                       // 星阵棋谱号，0 表示无谱
    "result": "黑中盘胜",
    "bili": []                     // 挂在该局的讲解视频
  }],
  "entry": "", "bili_rest": [],
  "vfail": 0, "vwarn": 0, "vissues": []
}
```

其余顶层键：`entries`（59 条积分记录）、`costs`（33 条扣分记录）、`bili_groups`（72 组 / 189 个视频）、`countdowns`、`grace`、`gl`（对局 → 星阵 id 映射）、`verify_*`（校验结果快照）。

---

## 口径与已知问题

- **对局数**：只收「能核到棋谱与轮次」的正式对局。另有统计作「1241 局（848 胜 392 负 1 和）」，多出的约 110 局主要是网络对局、让子 / 指导棋、双人赛与部分不计等级分的邀请赛，本档不并入。
- **结果文字**：绝大多数是「中盘胜 / 目胜 / 子胜」。本地数据没有 SGF 的 `RE[]` 标签，**无法批量判定超时**，目前只有 3 局标注超时（2014-07-02 常昊、2017-06-19 姜儒泽、2024-09-07 金明训），其余按公开报道逐条核对。
- **校验快照**：`verify_summary` 是历史校验结果，新增对局后需重跑校验脚本；`sync` 只对齐 `tours` / `games` 计数。
- **2012 年中国段位赛**：曾有 4 组「同日同对手」重复录入（一简一详），已保留带轮次与手数的一条、删除简写的一条。
- **弘通围棋**（原对局数据源）已于 2026 年下线，后续无法回补。

## 数据来源

- 弘通围棋对局库（抓取 1150 条，剔除 23 条重复 / 残缺记录，得 1127 局）
- 新浪体育 / 体坛周报（马晓春积分制历年报道）
- @晚春 微博、《围棋爱柯洁》披露的 2012 版条例及 2026 年实战积分榜
- B 站 UP 主「明玥谈棋」的全部柯洁相关投稿
- 星阵围棋（golaxy）公共棋谱库，用于「谱」按钮的交互式棋谱

## 目录

```
.
├── index.html              # 站点本体（单文件，数据内嵌）
├── shots/                  # 条例截图 rule1-6.png
├── .nojekyll               # GitHub Pages 用
├── tools/
│   ├── kejie.py            # 数据维护 CLI
│   ├── tier-rules.json     # 级别推断规则
│   └── package.py          # 打包成可部署 zip
└── dist/kejie-site.zip     # 部署包（可选）
```

`tools/` 下另有若干一次性脚本（截图比对、规则复现率检查、溢出检测等），不影响站点运行，可删。

## 声明

非官方档案，仅供学习与查阅。对局与积分数据尽力核对，但不保证与任何官方口径完全一致；发现错漏欢迎提 issue。
