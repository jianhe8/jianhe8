# 柯洁 · 战绩与马氏积分档案

2008-07-10 到 2026-07-30 的 257 项赛事、1127 局正式对局（767 胜 359 负 1 无胜负），以及按 2012 版国家队参赛积分条例（马氏积分）逐日重算的积分账户。页面和数据都在 `index.html` 里。

## 页面结构

| Tab     | 内容                                                                |
| ------- | ----------------------------------------------------------------- |
| 赛事时间线   | 8(9) 个世界冠军卡片，点开是逐轮晋级之路；下面是 257 项赛事，逐局记录对手、执色、手数、结果，可按年份、级别、积分变动筛选 |
| 积分曲线    | 马氏积分逐日余额，悬停看当日明细                                                  |
| 按日查询    | 任选一天，查余额、有效账户数、累计消耗与衰减                                            |
| 数据校验    | 逐条校验结果、积分引擎自检、与外部计算的差异说明                                          |
| 棋谱 · 讲解 | 明玥谈棋的投稿按赛事归组；「谱」按钮打开星阵棋谱库的交互式棋盘                                   |
| 对手志     | 交手记录、按赛事级别的胜负、执色对比、宿敌专题、逐年战绩                                      |
| 规则与校准   | 2012 版条例原文、赋分明细、参赛扣分逐条判定、外卡记录                                     |

导航右上角的「配色」可以换主色（金 / 朱 / 靛 / 松 / 紫 / 赭 / 墨，也可以自己取色）和纸色（米白 / 冷白 / 暖黄 / 灰调）。选择只写进 `localStorage` 的 `kejie.theme`，不改 `index.html`。

## 关于「8(9) 冠」

官方确认的世界冠军是 8 个：三星杯 4、百灵杯 2、梦百合杯 1、新奥杯 1。

第 9 冠指 2025 年 1 月第 29 届 LG 杯。决赛首局柯洁执黑 2.5 目先下一城，次局因两次提子未放在棋盒盖上被判负，决胜局退赛，中国围棋协会表示不接受该结果。所以站里既不写 8 也不写 9，统一记作 8(9)。

## 积分模型

每条积分是独立账户：满宽限天数后每日 −1，减到 0 为止。

| 类别   | 宽限    |
| ---- | ----- |
| 世界冠军 | 420 日 |
| 奖励积分 | 250 日 |
| 其余   | 300 日 |

参赛扣分不是记负分，而是先进先出地消耗已有账户，所以任何一天余额都不会小于 0。种子名额先有分才给；余额不够门槛时只能走预选、选拔或外卡，这三条路都不扣分。

## 本地打开

双击 `index.html` 即可，也可以 `open index.html`（macOS）或 `start index.html`（Windows）。没有 npm install，没有 dev server。唯一的外部资源是 `shots/` 下的 6 张条例截图。

## 数据维护

数据内嵌在 `index.html` 的 `const D = {...}` 里，由 `tools/kejie.py` 读写。只用标准库，Python 3.8+ 即可，不装任何包。

```bash
python tools/kejie.py --help
```

每次写入前会备份成 `index.backup.<时间戳>.html`，写坏了直接拷回来。

### 常用命令

```bash
# 示例里的「某杯」「某九段」「BV1xxxxxxxxx」都是占位；日期一律取已发生的，
# 只有倒计时那条用未来日期。

# 查看
python tools/kejie.py stats
python tools/kejie.py list --year 2026
python tools/kejie.py show 第16届春兰杯

# 新赛事（自动推断级别，按日期判「进行中 / 待补结果」）
python tools/kejie.py guess-tier "第1届某杯世界围棋公开赛预选"
python tools/kejie.py add-tour "第1届某杯世界围棋公开赛" --start 2024-03-01 --end 2024-03-05

# 加一局（自动延长赛期、重算战绩）
python tools/kejie.py add-game 第16届春兰杯 --date 2026-05-26 --opp 某九段 \
    --color B --result win --label 八强战 --result-text "黑中盘胜"

# 改单局结果（超时、判负等）
python tools/kejie.py set-game-result 第26届农心辛拉面杯 \
    --date 2024-09-07 --opp 金明训 --result "黑超时胜"

# 挂棋谱（写进内嵌棋谱库并登记映射）
python tools/kejie.py add-sgf 第25届应氏杯世界青少年围棋锦标赛 \
    --date 2008-07-10 --opp 一力辽 --file game.sgf

# 收尾未完赛、删重复局
python tools/kejie.py set-result "第1届某杯世界围棋公开赛" 四强
python tools/kejie.py del-game 2012年中国段位赛 --date 2012-07-18 --opp 吴树浩 \
    --label "2012年中国段位赛"

# 视频：挂到具体对局 / 某赛事 / 网棋组
python tools/kejie.py add-video --bvid BV1xxxxxxxxx --title "..." --date 2026-10-09 --net
python tools/kejie.py add-video --tour 王中王 --bvid BV1xxxxxxxxx --title "..."
python tools/kejie.py add-video --game "2026-05-25|福冈航太朗" --bvid BV1xxxxxxxxx --title "..."

# 删视频（bvid 或标题片段）
python tools/kejie.py del-video BV1xxxxxxxxx
python tools/kejie.py del-video "王中之王2" --all

# 倒计时
python tools/kejie.py list-countdown
python tools/kejie.py add-countdown "棋仙战 · 预选" 2026-11-02 --note "第 2 届世界围棋棋仙战 预选"

# 一言（首页随机语录）
python tools/kejie.py list-quotes
python tools/kejie.py add-quote "我柯洁在棋上什么大风大浪没见过？" --src "2016 · 微博"
python tools/kejie.py del-quote 12            # 按序号
python tools/kejie.py del-quote 大风大浪        # 或按引文片段

# 体检
python tools/kejie.py validate          # 加 --strict 才把「同日重复对手」算错误
python tools/kejie.py sync              # 重算战绩、排序、对齐计数
```

### 加棋谱（SGF）

棋谱不是独立文件，而是压进 `index.html` 的一个 gzip + base64 块（`const SGFZ`）。`add-sgf` 做三件事：

1. 把 SGF 写进棋谱库，不给 `--id` 就取现有最大 id 加一
2. 在 `D.gl` 里登记 `"日期|对手" → id`
3. 回写该局的 `id` 字段

之后时间线上那一行会出现「谱」按钮，点开是交互式棋盘，能前进、后退、跳转、自动播放。

SGF 要是标准格式（以 `(;` 开头），工具会数一遍手数做基本校验。同一局已经有棋谱时，不加 `--id` 会覆盖原条目；想换新 id 就显式给 `--id`，配 `--force`。

每加一局 `index.html` 会大几 KB。重压缩用 gzip -9，通常比原块还小一点。

### 边界情况

| 场景            | 行为                                                                     |
| ------------- | ---------------------------------------------------------------------- |
| 王中王算什么级别      | `tier-rules.json` 里 override 成「国内头衔战」，不被「争霸赛」带偏；但不计入马氏积分（邀请赛制），夺冠赋 0 分 |
| 带「预选 / 选拔」的赛事 | 规则顺序保证「选拔 / 预选」先于「世界大赛名」命中，不会被判成正赛                                     |
| 同名赛事歧义        | 输入「春兰杯」会列出 6 届让你选序号，不瞎猜                                                |
| 未完赛的后续        | `add-game` 把 `end` 往后延并重算战绩，`set-result` 收尾                            |
| 缺棋谱号          | 只警告，不影响入档，之后可以补 `--id`                                                 |
| 网棋            | `--net` 直接进「野狐网棋 · 网络对局」分组，不进赛事时间线                                     |
| 视频重复          | 按 bvid 去重；对局上的老数据只有 `url`，会从链接里反解 bvid 再比                              |
| 视频计数          | `add-video`、`del-video`、`merge-groups` 都会重算 `bili_total`，不会和实际条数脱节     |
| 同一视频双链接       | 既在赛事分组里、又挂在具体对局上，是有意设计；查重只在同类容器内做                                      |
| 删视频歧义         | 同一个 bvid 命中「分组 + 对局」两处时，不加 `--all` 只列候选，不会误删                           |
| 对手志           | 页面运行时从对局实时聚合，加完对局自动更新                                                  |

### tier 推断

规则在 `tools/tier-rules.json`，判定顺序是 `overrides` → `rules`（按数组顺序，首个命中生效）→ `default`。加新比赛类型只要加一条，不用改代码：

```json
{ "pattern": "王中王", "tier": "国内头衔战", "why": "…" }
```

推断不出来的多是「国内头衔战 / 国内邀请赛 / 其他赛事」这种本来就边界模糊的，用 `--tier` 手动覆盖。

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

其余顶层键：`entries`（积分记录）、`costs`（参赛扣分记录）、`bili_groups`（讲解视频分组）、`quotes`（一言）、`countdowns`、`grace`、`gl`（对局 → 星阵 id 映射）、`verify_*`（校验结果快照）。

## 口径

- 对局数：只收能核到棋谱与轮次的正式对局。另有统计作「1241 局（848 胜 392 负 1 和）」，多出的约 110 局主要是网络对局、让子 / 指导棋、双人赛和部分不计等级分的邀请赛，本档不并入。
- 结果文字：绝大多数是「中盘胜 / 目胜 / 子胜」。本地数据没有 SGF 的 `RE[]` 标签，没法批量判超时，目前只有 4 局标了超时（2014-07-02 常昊、2017-06-19 姜儒泽、2024-09-07 金明训、2024-11-02 朴廷桓），其余按公开报道逐条核对。
- 校验快照：`verify_summary` 是历史结果，新增对局后要重跑校验；`sync` 只对齐 `tours` / `games` 的计数。
- 2012 年中国段位赛：曾有 4 组「同日同对手」重复录入（一简一详），保留带轮次与手数的一条，删掉简写的一条。
- 弘通围棋（原对局数据源）2026 年下线，之后没法回补。

## 数据来源

- 弘通围棋对局库，抓取 1150 条，剔除 23 条重复 / 残缺，得 1127 局
- 新浪体育、体坛周报（马晓春积分制的历年报道）
- @晚春 微博、《围棋爱柯洁》披露的 2012 版条例与 2026 年实战积分榜
- B 站 UP 主「明玥谈棋」的柯洁相关投稿
- 星阵围棋（golaxy）公共棋谱库，用于「谱」按钮的交互式棋盘

## 目录

```
.
├── index.html              # 站点本体，数据内嵌
├── shots/                  # 条例截图 rule1-6.png
├── .nojekyll               # 关闭 Jekyll 处理
├── tools/
│   ├── kejie.py            # 数据维护 CLI
│   ├── recalc-costs.py     # 参赛扣分重算
│   ├── tier-rules.json     # 级别推断规则
│   └── package.py          # 打包成可部署 zip
└── dist/kejie-site.zip     # 部署包
```

## 说明

非官方档案，供查阅用。数据尽力核对，但不保证和任何官方口径完全一致。
