# 古籍残页转写拼接 API

- **`POST /api/align`**：提交两段含 `?`（未辨认字）的转写文本，将**左段后缀与右段前缀**做最优重叠对齐，
返回最高分对齐的原文区间、逐列对齐和拼接文本。
- **`POST /api/assemble`**：提交按阅读顺序排列的 **2～5 段**转写（每段最长 500 字、总长最长 800 字），
逐段复用上述后缀-前缀对齐完成拼接，返回最终文本与**逐字来源列表**。
- **`POST /api/collate`**：沿用 `/api/assemble` 的 `segments` 限制与续接门槛，复用其拼接文本和逐字来源，
逐位置回查各原始段原字、以**原始段为投票单位**汇总异文，供校勘人员复核（只给建议，不改写文本）。
- **`POST /api/order`**：提交 **2～4 段未排序**转写（每段不超过 100 字、总长不超过 240 字），
**穷举全部排列**，每一步把当前拼接文本与下一原段交给现有对齐逻辑、沿用同一续接门槛，**累计各步对齐得分**
选出累计分最高的完整顺序，返回**原输入下标顺序**、拼接文本与按原输入下标标记的逐字来源；最高分并列返回
**409**（含全部并列顺序），无完整顺序返回 **422**。
- **`POST /api/revise`**：提交与 `/api/assemble` 相同的有序 `segments` 及人工校订 `edits`
（每项含原始段序号 `segment`、原文下标 `pos`、替换字 `char`，`char` 为单个非 `?` 字符），
先复用拼接得到文本与逐字来源，再沿逐字来源把每项校订定位到拼接文本位置落实改字；
重叠段指向同一位置的相同改字**合并**，不同改字返回 **409**（列出冲突位置与校订项），
段序号/下标越界或坐标无法唯一定位返回 **422**；返回修订后文本、沿用的逐字来源与逐位置 `changes`。
- **`POST /api/locate-quote`**：提交与 `/api/assemble` 相同的有序 `segments` 及 1～80 字引文 `quote`，
在拼接文本中以逐字编辑代价（相同字或任一侧 `?` 代价 **0**，替换/插入/删除各代价 **1**）查找引文位置；
最小代价不超过 **2** 且区间唯一时返回**左闭右开区间**、原文片段、代价与该区间逐字 `sources`，
多个不同区间并列返回 **409**（列出全部并列区间），无合格区间返回 **422**；只定位、不改写拼接文本。
- **`POST /api/locate-quotes`**：提交与 `/api/assemble` 相同的有序 `segments` 及 **2～4 段按原文顺序
排列**的引文 `quotes`（各 1～80 字），为每段引文枚举编辑代价不超过 **2** 的全部非空区间，再选出区间
按序且**互不重叠**、总代价最低的**完整定位链**（即使某段单独最低代价的候选无法接入完整链，也会考虑
该段其余合格候选）；唯一最优链返回各引文区间、片段、代价与 `sources`，多个不同最优链并列返回 **409**
（给出两条不同最优链），无完整链返回 **422**。
- **`POST /api/find-repetition`**：提交与 `/api/assemble` 相同的有序 `segments`，先复用其拼接文本与
逐字来源，再在同一拼接文本中寻找两个**互不重叠的等长连续区间**：逐字相同或任一字为 `?` 即兼容，
区间长度至少 **6** 且至少 **4** 个位置两侧已知字相同；按长度最长、同长度已知相同位更多、再按两起点
升序取首对，返回两个左闭右开区间及各自原文与逐字 `sources`；无合格重复时 `repeat` 为 `null`。

## 快速开始

单条命令启动（依赖已纳入镜像构建）：

```bash
docker compose up --build
```

- **接口地址**：http://localhost:8000
- **端口**：8000
- **交互式接口文档（Swagger UI）**：http://localhost:8000/docs
- **健康检查**：http://localhost:8000/health

## 接口说明

### `POST /api/align`

请求体：

```json
{
  "left": "学而?习之",
  "right": "时习之不亦"
}
```

- `left`、`right`：必填，非空字符串（单段最长 500 字），未辨认字以 `?` 表示。

响应示例：

```json
{
  "score": 4,
  "aligned_pairs": 3,
  "left_interval": { "start": 2, "end": 5, "text": "?习之" },
  "right_interval": { "start": 0, "end": 3, "text": "时习之" },
  "left_free_prefix": "学而",
  "right_free_suffix": "不亦",
  "aligned_left": "?习之",
  "aligned_right": "时习之",
  "columns": [
    { "left_pos": 2, "left_char": "?", "right_pos": 0, "right_char": "时", "type": "wildcard", "score": 0 },
    { "left_pos": 3, "left_char": "习", "right_pos": 1, "right_char": "习", "type": "match", "score": 2 },
    { "left_pos": 4, "left_char": "之", "right_pos": 2, "right_char": "之", "type": "match", "score": 2 }
  ],
  "merged": "学而时习之不亦",
  "conflicts": [],
  "resolved_wildcards": [
    { "segment": "left", "pos": 2, "resolved_char": "时" }
  ]
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `score` | 最高对齐得分 |
| `aligned_pairs` | 对齐字符对数 |
| `left_interval` / `right_interval` | 左/右段参与对齐的原文区间（下标从 0 开始，左闭右开） |
| `left_free_prefix` / `right_free_suffix` | 未参与对齐、不计分的左段前缀 / 右段后缀 |
| `aligned_left` / `aligned_right` | 对齐串（空缺以 `-` 表示） |
| `columns` | 逐列对齐：`type` 为 `match`（相同字）/ `wildcard`（含 `?`）/ `mismatch`（异字）/ `gap_left`（左段空缺）/ `gap_right`（右段空缺），`score` 为本列得分 |
| `merged` | 拼接文本 |
| `conflicts` | 异字冲突列表：保留左段字，并列出双方原文位置及字形 |
| `resolved_wildcards` | `?` 补字列表：以对方已知字替换 |

调用示例：

```bash
curl -X POST http://localhost:8000/api/align \
  -H "Content-Type: application/json" \
  -d '{"left": "学而?习之", "right": "时习之不亦"}'
```

### `POST /api/assemble`

按阅读顺序逐段拼接 2～5 段转写。每一步把**当前拼接文本作为左段、下一段原始转写作为右段**，
复用 `/api/align` 的后缀-前缀对齐合并。

**续接门槛**：每一步仅在最高对齐得分 **大于 0**、且至少有 **2 对相同已知字**（`match` 列）时继续；
任一步不满足即返回 **422**，响应中给出失败段序号 `failed_segment`（从 0 开始）。整个请求为一次
纯内存计算，失败时不产生任何部分结果。

**逐字来源**：响应的 `sources` 与最终文本 `text` 等长，逐字对应；每个字保留贡献它的所有
原始段序号与原文下标（均从 0 开始）：

- 相同字：对齐双方来源都保留（多段重叠时可累积超过 2 个来源）；
- `?` 补字：`?` 一方与补字一方的来源都保留；双方皆为 `?` 时保留 `?`；
- 异字冲突：拼接保留左段字形，但冲突双方来源都保留；
- 空缺列：仅未空缺一方贡献来源。

请求体：

```json
{
  "segments": ["学而?习之", "时习之不", "之不亦乐乎"]
}
```

- `segments`：必填，2～5 个非空字符串；单段最长 500 字，各段总长最长 800 字。

响应示例：

```json
{
  "text": "学而时习之不亦乐乎",
  "sources": [
    [{ "segment": 0, "pos": 0 }],
    [{ "segment": 0, "pos": 1 }],
    [{ "segment": 0, "pos": 2 }, { "segment": 1, "pos": 0 }],
    [{ "segment": 0, "pos": 3 }, { "segment": 1, "pos": 1 }],
    [{ "segment": 0, "pos": 4 }, { "segment": 1, "pos": 2 }, { "segment": 2, "pos": 0 }],
    [{ "segment": 1, "pos": 3 }, { "segment": 2, "pos": 1 }],
    [{ "segment": 2, "pos": 2 }],
    [{ "segment": 2, "pos": 3 }],
    [{ "segment": 2, "pos": 4 }]
  ]
}
```

上例中：`时` 由第 1 段的 `?`（补字）与第 2 段的 `时` 共同贡献；`之` 由三段共同贡献。

续接失败示例（第 3 段无法与前文可靠拼接，`failed_segment` 为段序号，从 0 开始）：

```bash
curl -X POST http://localhost:8000/api/assemble \
  -H "Content-Type: application/json" \
  -d '{"segments": ["孔子曰未知", "未知生焉", "完全无关文本"]}'
```

```json
{
  "detail": {
    "message": "第 3 段（段序号 2）无法与前文可靠拼接：需要最高对齐得分 > 0 且至少 2 对相同已知字",
    "failed_segment": 2
  }
}
```

### `POST /api/collate`

供古籍校勘人员复核多份残页转写。请求体与 `/api/assemble` 完全相同（沿用其 `segments` 限制：
2～5 个非空字符串，单段最长 500 字、总长最长 800 字；续接门槛与 422 规则也一致），内部复用
`/api/assemble` 的拼接文本与逐字来源，再逐字回查所有来源原字。

**投票规则**（以**原始段为投票单位**，段序号均从 0 开始）：

- 对拼接文本的每个输出位置，经逐字来源回查各原始段在该位置的**原字**；
- 同一原始段在该位置有多个来源标记时（同段重复来源）**只计一次**；
- 原字为 `?`（未辨认字）的来源**不投票**；
- **仅保留至少有两种不同已知字的位置**（异文位置）。只有一种已知字的位置属于补字而非异文，
  不列入（例如某位置由一段的 `?` 与另一段的已知字补字而成，无候选分歧）。

**建议字**：各候选字按得票数排列，**唯一最高票**的候选作为 `suggestion`；**最高票并列**时
`suggestion` 为 `null`。接口**不自动改写**拼接文本，`text` 与 `/api/assemble` 的结果一致。

请求体：

```json
{
  "segments": ["甲乙丙丁戊己", "甲乙丙艮戊己", "甲乙丙丁戊己庚辛", "戊己康辛", "戊己康辛"]
}
```

响应示例：

```json
{
  "text": "甲乙丙丁戊己庚辛",
  "variants": [
    {
      "pos": 3,
      "current": "丁",
      "candidates": [
        { "char": "丁", "segments": [0, 2] },
        { "char": "艮", "segments": [1] }
      ],
      "suggestion": "丁"
    },
    {
      "pos": 6,
      "current": "庚",
      "candidates": [
        { "char": "康", "segments": [3, 4] },
        { "char": "庚", "segments": [2] }
      ],
      "suggestion": "康"
    }
  ]
}
```

上例中：

- 第 4 字（`pos` 3）拼接保留先出的 `丁`，段 0、2 作 `丁`（2 票）、段 1 作 `艮`（1 票），建议 `丁`；
- 第 7 字（`pos` 6）拼接文本仍是 `庚`，但后并入的段 3、4 作 `康`（2 票）压过段 2 的 `庚`（1 票），
  故**建议 `康` 而当前字为 `庚`**——是否采纳由校勘人员决定，文本不会被自动改写；
- 其余各字各段原字一致（或仅由 `?` 补字），不构成异文，不列入。

字段说明：

| 字段 | 含义 |
| --- | --- |
| `text` | 拼接文本（与 `/api/assemble` 一致，不被改写） |
| `variants[].pos` | 异文位置在拼接文本中的下标（从 0 开始） |
| `variants[].current` | 当前拼接文本在该位置的字 |
| `variants[].candidates[].char` | 候选原字（已知字） |
| `variants[].candidates[].segments` | 支持该候选字的原始段序号（升序、去重；同段重复来源只计一次，`?` 不投票） |
| `variants[].suggestion` | 建议字：唯一最高票候选；最高票并列时为 `null` |

候选按得票数降序排列；得票相同时按最小支持段序号升序排列。

并列最高票示例（`丁`、`艮` 各 1 票，建议为 `null`）：

```bash
curl -X POST http://localhost:8000/api/collate \
  -H "Content-Type: application/json" \
  -d '{"segments": ["甲乙丙丁戊己", "甲乙丙艮戊己"]}'
```

```json
{
  "text": "甲乙丙丁戊己",
  "variants": [
    {
      "pos": 3,
      "current": "丁",
      "candidates": [
        { "char": "丁", "segments": [0] },
        { "char": "艮", "segments": [1] }
      ],
      "suggestion": null
    }
  ]
}
```

补字无异文时（`?` 由已知字补入，候选不产生分歧）`variants` 为空数组：

```bash
curl -X POST http://localhost:8000/api/collate \
  -H "Content-Type: application/json" \
  -d '{"segments": ["学而?习之", "时习之"]}'
```

```json
{ "text": "学而时习之", "variants": [] }
```

续接失败时与 `/api/assemble` 一样返回 **422** 并给出 `failed_segment`（从 0 开始）。

### `POST /api/revise`

在拼接文本上落实**人工校订**。请求的 `segments` 与 `/api/assemble` 完全相同（沿用其限制与续接门槛，
失败同样返回 **422** 并给出 `failed_segment`），另附校订列表 `edits`。接口先复用 `/api/assemble`
得到拼接文本与逐字来源，再**沿逐字来源**把每项校订定位到最终文本位置落实改字：

- **定位**：每项校订给出原始段序号 `segment`、原文下标 `pos`（均从 0 开始）与替换字 `char`
  （**单个非 `?` 字符**）；接口在逐字来源中查找该坐标对应的输出位置；
- **合并**：重叠段指向**同一输出位置**且改字相同的多项校订合并为一处修改，关联校订项全部保留；
- **冲突（409）**：同一输出位置被指向**不同改字**时返回 **409**，`detail.conflicts` 列出全部
  冲突位置与校订项；
- **无法定位（422）**：段序号或原文下标越界、校订坐标未映射或映射到多个输出位置，均返回 **422**；
- **不产生部分修订**：任一环节失败即不返回任何结果；**不重新对齐**，未涉及位置保持原字，
  `sources` 沿用拼接结果不变。

请求体：

```json
{
  "segments": ["学而?习之", "时习之不", "之不亦乐乎"],
  "edits": [
    { "segment": 0, "pos": 4, "char": "知" },
    { "segment": 2, "pos": 0, "char": "知" }
  ]
}
```

- `segments`：必填，2～5 个非空字符串；单段最长 500 字，各段总长最长 800 字（同 `/api/assemble`）。
- `edits`：必填（可为空数组），每项含 `segment`、`pos`、`char` 三个字段。

调用示例：

```bash
curl -X POST http://localhost:8000/api/revise \
  -H "Content-Type: application/json" \
  -d '{"segments": ["学而?习之", "时习之不", "之不亦乐乎"], "edits": [{"segment": 0, "pos": 4, "char": "知"}, {"segment": 2, "pos": 0, "char": "知"}]}'
```

响应示例（拼接文本位置 4 的 `之` 由段 0、1、2 重叠贡献，两项校订改字相同，合并为一处修改）：

```json
{
  "text": "学而时习知不亦乐乎",
  "sources": [
    [{ "segment": 0, "pos": 0 }],
    [{ "segment": 0, "pos": 1 }],
    [{ "segment": 0, "pos": 2 }, { "segment": 1, "pos": 0 }],
    [{ "segment": 0, "pos": 3 }, { "segment": 1, "pos": 1 }],
    [{ "segment": 0, "pos": 4 }, { "segment": 1, "pos": 2 }, { "segment": 2, "pos": 0 }],
    [{ "segment": 1, "pos": 3 }, { "segment": 2, "pos": 1 }],
    [{ "segment": 2, "pos": 2 }],
    [{ "segment": 2, "pos": 3 }],
    [{ "segment": 2, "pos": 4 }]
  ],
  "changes": [
    {
      "pos": 4,
      "from_char": "之",
      "to_char": "知",
      "edits": [
        { "index": 0, "segment": 0, "pos": 4, "char": "知" },
        { "index": 1, "segment": 2, "pos": 0, "char": "知" }
      ]
    }
  ]
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `text` | 修订后的文本（未涉及位置保持原字） |
| `sources` | 逐字来源列表，沿用 `/api/assemble` 的拼接结果，不重新对齐 |
| `changes[].pos` | 修订位置在拼接文本中的下标（从 0 开始），按位置升序 |
| `changes[].from_char` | 原字（修订前拼接文本在该位置的字） |
| `changes[].to_char` | 新字（校订落实后的字） |
| `changes[].edits[]` | 关联校订项：`index` 为该校订在请求 `edits` 中的下标（从 0 开始），其余字段原样回显 |

**改字冲突（409）**示例——段 0 的 `之`（下标 4）与段 1 的 `之`（下标 2）经重叠对齐指向同一
输出位置，两项校订改字不同：

```bash
curl -X POST http://localhost:8000/api/revise \
  -H "Content-Type: application/json" \
  -d '{"segments": ["学而?习之", "时习之不", "之不亦乐乎"], "edits": [{"segment": 0, "pos": 4, "char": "甲"}, {"segment": 1, "pos": 2, "char": "乙"}]}'
```

```json
{
  "detail": {
    "message": "校订冲突：输出位置 4 被多项校订指向不同改字，无法落实修订",
    "conflicts": [
      {
        "pos": 4,
        "edits": [
          { "index": 0, "segment": 0, "pos": 4, "char": "甲" },
          { "index": 1, "segment": 1, "pos": 2, "char": "乙" }
        ]
      }
    ]
  }
}
```

**坐标越界（422）**示例——段序号或原文下标超出范围（坐标未映射或映射到多个输出位置同样返回 422）：

```json
{
  "detail": {
    "message": "第 1 项校订的段序号 5 越界：共 3 段（段序号 0～2）"
  }
}
```

替换字为 `?`、替换字不是单个字符、`segment`/`pos` 为负数或缺字段等参数不合法情况同样返回 **422**。
续接失败时与 `/api/assemble` 一样返回 **422** 并给出 `failed_segment`（从 0 开始）。

### `POST /api/order`

当残页转写的**先后顺序未知**时，提交 2～4 段未排序文本，由接口穷举可行阅读顺序：

- **穷举全部排列**（至多 4! = 24 种），对每个排列逐段拼接：每一步把**当前拼接文本作为左段、下一原段作为右段**
  交给 `/api/align` 的后缀-前缀对齐，沿用 `/api/assemble` 的**续接门槛**（最高对齐得分 **> 0** 且至少
  **2 对相同已知字**）；任一步不满足即废弃该排列（不报错，继续尝试其余排列）；
- 每个完整顺序的总分 = **各步对齐得分的累计**（链式拼接的整体质量），**不是**原段两两相似度的简单排序；
- 取累计得分最高的完整顺序，返回**原输入下标顺序** `order`、累计 `score`、拼接文本 `text` 及与文本等长、
  按**原输入下标**标记的逐字来源 `sources`（拼接与来源规则与 `/api/assemble` 完全一致）；
- **最高分并列**时返回 **409**，`detail.ties` 给出全部并列顺序（按下标顺序字典序排列），各带完整
  `order` / `score` / `text` / `sources`，由人工裁定；
- **没有任何完整顺序**（所有排列都在某一步断链）时返回 **422**。

请求体：

```json
{
  "segments": ["之不亦乐乎", "学而?习之", "时习之不"]
}
```

- `segments`：必填，**2～4** 个非空字符串；单段最长 **100** 字，各段总长最长 **240** 字。

调用示例：

```bash
curl -X POST http://localhost:8000/api/order \
  -H "Content-Type: application/json" \
  -d '{"segments": ["之不亦乐乎", "学而?习之", "时习之不"]}'
```

响应示例（原下标顺序 `[1, 2, 0]`，即第 2 段 → 第 3 段 → 第 1 段；累计得分 8 = 4 + 4）：

```json
{
  "order": [1, 2, 0],
  "score": 8,
  "text": "学而时习之不亦乐乎",
  "sources": [
    [{ "segment": 1, "pos": 0 }],
    [{ "segment": 1, "pos": 1 }],
    [{ "segment": 1, "pos": 2 }, { "segment": 2, "pos": 0 }],
    [{ "segment": 1, "pos": 3 }, { "segment": 2, "pos": 1 }],
    [{ "segment": 0, "pos": 0 }, { "segment": 1, "pos": 4 }, { "segment": 2, "pos": 2 }],
    [{ "segment": 0, "pos": 1 }, { "segment": 2, "pos": 3 }],
    [{ "segment": 0, "pos": 2 }],
    [{ "segment": 0, "pos": 3 }],
    [{ "segment": 0, "pos": 4 }]
  ]
}
```

注意 `sources` 中的 `segment` 始终是**原输入下标**（而非阅读次序中的位次）：上例拼接首段其实是
输入的第 2 段，故首字来源标记为 `{"segment": 1, ...}`。

**最高分并列（409）**示例——两段转写完全相同时，先并哪一段累计分相同，接口不擅自选择：

```bash
curl -X POST http://localhost:8000/api/order \
  -H "Content-Type: application/json" \
  -d '{"segments": ["甲乙丙丁", "丙丁戊", "丙丁戊"]}'
```

```json
{
  "detail": {
    "message": "最高累计得分 10 的完整顺序有 2 个并列，无法唯一确定阅读顺序",
    "score": 10,
    "ties": [
      { "order": [0, 1, 2], "score": 10, "text": "甲乙丙丁戊", "sources": [ "…" ] },
      { "order": [0, 2, 1], "score": 10, "text": "甲乙丙丁戊", "sources": [ "…" ] }
    ]
  }
}
```

**无完整顺序（422）**示例——任意排列都无法在每一步同时满足得分 > 0 与至少 2 对相同已知字：

```bash
curl -X POST http://localhost:8000/api/order \
  -H "Content-Type: application/json" \
  -d '{"segments": ["孔子曰未知", "完全无关文本甲", "另一无关内容乙"]}'
```

```json
{
  "detail": {
    "message": "没有任何排列能通过续接门槛（每步最高对齐得分 > 0 且至少 2 对相同已知字），无法确定完整阅读顺序"
  }
}
```

请求参数不合法（段数不在 2～4、单段超 100 字、总长超 240 字、含空段、缺字段）同样返回 **422**。

### `POST /api/locate-quote`

在拼接文本中**定位一段引文**。请求的 `segments` 与 `/api/assemble` 完全相同（沿用 2～5 段、单段最长
500 字、总长最长 800 字的限制与续接门槛，续接失败同样返回 **422** 并给出 `failed_segment`），另附
**1～80 字**的引文 `quote`（未辨认字也以 `?` 表示）。接口先复用 `/api/assemble` 得到拼接文本与逐字
来源，再把引文与拼接文本的**任意非空连续区间**比较，按逐字编辑代价寻找最接近的区间：

- 两字**相同**代价 **0**；**任一侧为 `?`**（未辨认字）的字符对代价也是 **0**；
- **替换**（双方均为已知字且不同）、**插入**（区间比引文多字）、**删除**（区间比引文少字）各代价 **1**；
- 区间起点、终点都自由（区间之前的拼接文本前缀、引文消耗完之后的区间后缀不产生删除/插入代价），
  但引文必须**完全消耗**、区间至少包含一个拼接字符；
- **仅接受最小代价不超过 2 的区间**。最小代价由多个**不同区间**并列取得时返回 **409**，
  `detail.ties` 按 `(start, end)` 升序列出全部并列区间（各带原文片段 `fragment`、`cost` 与该区间
  逐字 `sources`）；最小代价大于 2、无合格区间时返回 **422**。
- 接口**只做定位，不改写拼接文本**；唯一命中时返回左闭右开区间 `[start, end)`、原文片段 `fragment`、
  代价 `cost` 与该区间的逐字 `sources`（与 `fragment` 等长，规则同 `/api/assemble`），并回显
  完整拼接文本 `text` 与原文 `quote`。

请求体：

```json
{
  "segments": ["学而?习之", "时习之不", "之不亦乐乎"],
  "quote": "时习之"
}
```

- `segments`：必填，2～5 个非空字符串；单段最长 500 字，各段总长最长 800 字（同 `/api/assemble`）。
- `quote`：必填，**1～80** 字的非空字符串。

调用示例：

```bash
curl -X POST http://localhost:8000/api/locate-quote \
  -H "Content-Type: application/json" \
  -d '{"segments": ["学而?习之", "时习之不", "之不亦乐乎"], "quote": "时习之"}'
```

响应示例（拼接文本 `学而时习之不亦乐乎` 中，引文 `时习之` 代价 0 唯一命中区间 `[2, 5)`）：

```json
{
  "text": "学而时习之不亦乐乎",
  "quote": "时习之",
  "start": 2,
  "end": 5,
  "fragment": "时习之",
  "cost": 0,
  "sources": [
    [{ "segment": 0, "pos": 2 }, { "segment": 1, "pos": 0 }],
    [{ "segment": 0, "pos": 3 }, { "segment": 1, "pos": 1 }],
    [{ "segment": 0, "pos": 4 }, { "segment": 1, "pos": 2 }, { "segment": 2, "pos": 0 }]
  ]
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `text` | 拼接文本（与 `/api/assemble` 一致，不被改写） |
| `quote` | 原样回显的引文 |
| `start` / `end` | 命中区间在拼接文本中的下标（从 0 开始，**左闭右开** `[start, end)`） |
| `fragment` | 区间原文片段，即 `text[start:end]` |
| `cost` | 引文与该区间对齐的最小代价（相同字/任一侧 `?` 为 0；替换、插入、删除各 1） |
| `sources` | 该区间的逐字来源列表，与 `fragment` 等长，规则与 `/api/assemble` 一致 |

引文或拼接文本任一侧含 `?` 均免代价（下例引文 `时?之` 与片段 `时习之` 代价 0）：

```bash
curl -X POST http://localhost:8000/api/locate-quote \
  -H "Content-Type: application/json" \
  -d '{"segments": ["学而?习之", "时习之不", "之不亦乐乎"], "quote": "时?之"}'
```

允许最多 2 处差异——下例引文末字 `悦` 与拼接文本 `乎` 不同（替换 1 次），区间 `[0, 9)` 唯一命中：

```json
{
  "text": "学而时习之不亦乐乎",
  "quote": "学而时习之不亦悦乎",
  "start": 0,
  "end": 9,
  "fragment": "学而时习之不亦乐乎",
  "cost": 1,
  "sources": [ "…" ]
}
```

**多个不同区间并列（409）**示例——拼接文本 `甲子丙丁卯甲庚` 中有两个 `甲`，引文 `甲` 对两个区间
代价同为 0，接口不擅自选择：

```bash
curl -X POST http://localhost:8000/api/locate-quote \
  -H "Content-Type: application/json" \
  -d '{"segments": ["甲子丙丁卯", "丁卯甲庚"], "quote": "甲"}'
```

```json
{
  "detail": {
    "message": "引文在拼接文本中有 2 个不同区间以最小代价 0 并列，无法唯一定位",
    "cost": 0,
    "ties": [
      { "start": 0, "end": 1, "fragment": "甲", "cost": 0, "sources": [[{ "segment": 0, "pos": 0 }]] },
      { "start": 5, "end": 6, "fragment": "甲", "cost": 0, "sources": [[{ "segment": 1, "pos": 2 }]] }
    ]
  }
}
```

注意：即使区间长度不同也可能并列——例如引文 `时习知` 对片段 `时习之`（末字替换，代价 1）与对片段
`时习`（末尾多一个引文字删除，代价 1）并列时同样返回 **409**，两个区间都会列入 `ties`。

**无合格区间（422）**示例——引文与拼接文本任何非空区间的最小代价都大于 2：

```bash
curl -X POST http://localhost:8000/api/locate-quote \
  -H "Content-Type: application/json" \
  -d '{"segments": ["学而?习之", "时习之不", "之不亦乐乎"], "quote": "朋朋朋朋"}'
```

```json
{
  "detail": {
    "message": "引文（4 字）在拼接文本中最接近区间的代价为 4，超过 2，无合格区间"
  }
}
```

`quote` 为空、超过 80 字、缺字段，或 segments 不满足 `/api/assemble` 的段数/长度限制、续接失败，
同样返回 **422**（续接失败时给出 `failed_segment`，从 0 开始）。

### `POST /api/locate-quotes`

在拼接文本中**按原文顺序同时定位 2～4 段引文**。请求的 `segments` 与 `/api/assemble` 完全相同
（沿用 2～5 段、单段最长 500 字、总长最长 800 字的限制与续接门槛，续接失败同样返回 **422** 并给出
`failed_segment`），另附 **2～4 段按原文顺序排列**的引文 `quotes`（每段 **1～80** 字，未辨认字也以
`?` 表示）。接口先复用 `/api/assemble` 得到拼接文本与逐字来源，然后：

- **枚举候选**：对每段引文枚举与拼接文本的任意非空连续区间、逐字编辑代价不超过 **2** 的**全部**区间
  （代价规则同 `/api/locate-quote`：相同字或任一侧 `?` 代价 **0**，替换/插入/删除各代价 **1**，
  区间两端自由、引文完全消耗）；
- **选完整定位链**：从各段候选中选出区间按引文顺序排列、**两两不重叠**（前段 `end` ≤ 后段 `start`，
  相邻可贴合，不共享字即不算重叠）且**各段代价之和最低**的完整链；
- **不放弃次优候选**：即使某段引文单独最低代价的候选无法接入完整链（例如与前一段区间重叠），也会
  继续考虑该段其余代价不超过 2 的合格候选；
- **唯一最优链**时返回 `total_cost` 与 `hits`（与 `quotes` 等长、等序，每项含该段引文的区间、
  原文片段 `fragment`、本段代价 `cost` 与该区间逐字 `sources`）；
- **多个不同最优链并列**时返回 **409**，`detail.ties` 给出**两条不同的最优链**（按区间坐标字典序
  取最小的两条；同一组区间即使存在多种内部对齐方式也只算一条链）；
- **无完整链**（某段引文没有代价 ≤ 2 的区间，或所有合格区间都无法按序组成互不重叠的链）时返回
  **422**。接口**只做定位，不改写拼接文本**。

请求体：

```json
{
  "segments": ["学而?习之", "时习之不", "之不亦乐乎"],
  "quotes": ["学而", "时习之", "不亦乐乎"]
}
```

- `segments`：必填，2～5 个非空字符串；单段最长 500 字，各段总长最长 800 字（同 `/api/assemble`）。
- `quotes`：必填，**2～4** 个非空字符串；每段 **1～80** 字，按引文在原文中的先后顺序排列。

调用示例：

```bash
curl -X POST http://localhost:8000/api/locate-quotes \
  -H "Content-Type: application/json" \
  -d '{"segments": ["学而?习之", "时习之不", "之不亦乐乎"], "quotes": ["学而", "时习之", "不亦乐乎"]}'
```

响应示例（三段引文在拼接文本 `学而时习之不亦乐乎` 中代价均为 0，区间 `[0,2)`、`[2,5)`、`[5,9)`
按序贴合，总代价 0）：

```json
{
  "text": "学而时习之不亦乐乎",
  "quotes": ["学而", "时习之", "不亦乐乎"],
  "total_cost": 0,
  "hits": [
    {
      "start": 0,
      "end": 2,
      "fragment": "学而",
      "cost": 0,
      "sources": [
        [{ "segment": 0, "pos": 0 }],
        [{ "segment": 0, "pos": 1 }]
      ]
    },
    {
      "start": 2,
      "end": 5,
      "fragment": "时习之",
      "cost": 0,
      "sources": [
        [{ "segment": 0, "pos": 2 }, { "segment": 1, "pos": 0 }],
        [{ "segment": 0, "pos": 3 }, { "segment": 1, "pos": 1 }],
        [{ "segment": 0, "pos": 4 }, { "segment": 1, "pos": 2 }, { "segment": 2, "pos": 0 }]
      ]
    },
    {
      "start": 5,
      "end": 9,
      "fragment": "不亦乐乎",
      "cost": 0,
      "sources": [
        [{ "segment": 1, "pos": 3 }, { "segment": 2, "pos": 1 }],
        [{ "segment": 2, "pos": 2 }],
        [{ "segment": 2, "pos": 3 }],
        [{ "segment": 2, "pos": 4 }]
      ]
    }
  ]
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `text` | 拼接文本（与 `/api/assemble` 一致，不被改写） |
| `quotes` | 原样回显的引文列表（2～4 段，按原文顺序排列） |
| `total_cost` | 完整定位链上各段引文代价之和 |
| `hits[]` | 各引文的定位结果，与 `quotes` 等长、等序；字段同 `/api/locate-quote`（`start`/`end`/`fragment`/`cost`/`sources`），相邻区间满足前段 `end` ≤ 后段 `start` |

**次优候选成链**示例——两段引文都是单字 `甲` 时，第二段单独的代价 0 区间 `[0,1)` 与第一段重叠、
无法接入完整链；接口改取该段代价 1 的区间 `[1,2)`（片段 `乙`，替换 1 次），总代价 1：

```bash
curl -X POST http://localhost:8000/api/locate-quotes \
  -H "Content-Type: application/json" \
  -d '{"segments": ["甲乙", "甲乙"], "quotes": ["甲", "甲"]}'
```

```json
{
  "text": "甲乙",
  "quotes": ["甲", "甲"],
  "total_cost": 1,
  "hits": [
    { "start": 0, "end": 1, "fragment": "甲", "cost": 0, "sources": [[{ "segment": 0, "pos": 0 }]] },
    { "start": 1, "end": 2, "fragment": "乙", "cost": 1, "sources": [[{ "segment": 0, "pos": 1 }, { "segment": 1, "pos": 1 }]] }
  ]
}
```

**多个最优链并列（409）**示例——拼接文本 `甲丙甲丙` 中，引文 `甲`、`丙` 各有两个代价 0 位置，
`甲[0,1) → 丙[1,2)` 与 `甲[0,1) → 丙[3,4)` 总代价同为 0，接口不擅自选择，返回两条不同最优链：

```bash
curl -X POST http://localhost:8000/api/locate-quotes \
  -H "Content-Type: application/json" \
  -d '{"segments": ["甲丙甲丙", "甲丙甲丙"], "quotes": ["甲", "丙"]}'
```

```json
{
  "detail": {
    "message": "2 段引文在拼接文本中有多个不同定位链以最低总代价 0 并列，无法唯一确定",
    "cost": 0,
    "ties": [
      [
        { "start": 0, "end": 1, "fragment": "甲", "cost": 0, "sources": [[{ "segment": 0, "pos": 0 }]] },
        { "start": 1, "end": 2, "fragment": "丙", "cost": 0, "sources": [[{ "segment": 0, "pos": 1 }]] }
      ],
      [
        { "start": 0, "end": 1, "fragment": "甲", "cost": 0, "sources": [[{ "segment": 0, "pos": 0 }]] },
        { "start": 3, "end": 4, "fragment": "丙", "cost": 0, "sources": [[{ "segment": 0, "pos": 3 }]] }
      ]
    ]
  }
}
```

**无完整链（422）**示例——两段引文各自都有代价不超过 2 的区间，但可行区间的先后顺序与引文顺序
相反，无法选出互不重叠的完整链（某段引文本身无合格区间时同样返回 422，并指出是第几段引文）：

```bash
curl -X POST http://localhost:8000/api/locate-quotes \
  -H "Content-Type: application/json" \
  -d '{"segments": ["甲甲乙乙", "甲甲乙乙"], "quotes": ["乙乙XX", "甲甲XX"]}'
```

```json
{
  "detail": {
    "message": "各段引文虽有代价不超过 2 的区间，但无法按原文顺序选出互不重叠的完整定位链"
  }
}
```

`quotes` 段数不在 2～4、某段为空或超过 80 字、缺字段，或 segments 不满足 `/api/assemble` 的
段数/长度限制、续接失败，同样返回 **422**（续接失败时给出 `failed_segment`，从 0 开始）。

### `POST /api/find-repetition`

供校勘人员发现同一拼接稿中**可能的重复抄写**。请求的 `segments` 与 `/api/assemble` 完全相同（沿用
2～5 段、单段最长 500 字、总长最长 800 字的限制与续接门槛，续接失败同样返回 **422** 并给出
`failed_segment`）。接口先复用 `/api/assemble` 得到拼接文本与逐字来源，再在**同一份拼接文本**中寻找
两个**互不重叠的等长连续区间**：

- **逐字兼容**：对应位置的两个字**相同**，或**任一字为 `?`**（未辨认字）即视为兼容；
- **长度门槛**：区间长度至少 **6**；
- **已知相同位门槛**：区间内至少 **4** 个位置是两侧皆为**已知字且相同**（`?` 与他字的兼容配对
  不计入已知相同位，避免全 `?` 区间造成误报）；
- **互不重叠**：两区间不共享字，允许贴合（前段 `end` ≤ 后段 `start`）。

**择优规则**：先取**长度最长**的区间对；长度相同时取**已知相同位更多**者；再相同则按
**两起点升序** `(first.start, second.start)` 取首对，结果确定、不返回并列冲突。两个区间按起点升序记为
`repeat.first`、`repeat.second`，各自给出左闭右开区间 `[start, end)`、原文片段 `fragment` 与该区间
逐字 `sources`（与 `fragment` 等长，规则同 `/api/assemble`）。接口**只做发现，不改写拼接文本**；
不存在合格重复时 `repeat` 为 **`null`**。

请求体：

```json
{
  "segments": ["学而时习之不亦朱雀", "朱雀玄武白虎腾蛇青龙学而时习之不亦"]
}
```

- `segments`：必填，2～5 个非空字符串；单段最长 500 字，各段总长最长 800 字（同 `/api/assemble`）。

调用示例：

```bash
curl -X POST http://localhost:8000/api/find-repetition \
  -H "Content-Type: application/json" \
  -d '{"segments": ["学而时习之不亦朱雀", "朱雀玄武白虎腾蛇青龙学而时习之不亦"]}'
```

响应示例（拼接文本 `学而时习之不亦朱雀玄武白虎腾蛇青龙学而时习之不亦` 中，`学而时习之不亦` 出现
两次：区间 `[0,7)` 与 `[17,24)` 等长 7 字、7 个已知相同位、互不重叠）：

```json
{
  "text": "学而时习之不亦朱雀玄武白虎腾蛇青龙学而时习之不亦",
  "repeat": {
    "first": {
      "start": 0,
      "end": 7,
      "fragment": "学而时习之不亦",
      "sources": [
        [{ "segment": 0, "pos": 0 }],
        [{ "segment": 0, "pos": 1 }],
        [{ "segment": 0, "pos": 2 }],
        [{ "segment": 0, "pos": 3 }],
        [{ "segment": 0, "pos": 4 }],
        [{ "segment": 0, "pos": 5 }],
        [{ "segment": 0, "pos": 6 }]
      ]
    },
    "second": {
      "start": 17,
      "end": 24,
      "fragment": "学而时习之不亦",
      "sources": [
        [{ "segment": 1, "pos": 10 }],
        [{ "segment": 1, "pos": 11 }],
        [{ "segment": 1, "pos": 12 }],
        [{ "segment": 1, "pos": 13 }],
        [{ "segment": 1, "pos": 14 }],
        [{ "segment": 1, "pos": 15 }],
        [{ "segment": 1, "pos": 16 }]
      ]
    }
  }
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `text` | 拼接文本（与 `/api/assemble` 一致，不被改写） |
| `repeat` | 最优重复区间对；无合格重复时为 `null` |
| `repeat.first` / `repeat.second` | 起点较小 / 较大的区间，二者等长且互不重叠（`first.end ≤ second.start`） |
| `start` / `end` | 区间在拼接文本中的下标（从 0 开始，**左闭右开** `[start, end)`） |
| `fragment` | 区间原文片段，即 `text[start:end]` |
| `sources` | 该区间的逐字来源列表，与 `fragment` 等长，规则与 `/api/assemble` 一致 |

任一侧含 `?` 仍可配对——例如两处抄写为 `甲乙丙丁戊己` 与 `甲?丙丁戊?` 时，逐字兼容、长度 6、
已知相同位 4（≥4），同样会被发现；但若兼容位全部来自 `?`（已知相同位不足 4），或两区间只能以
重叠方式取得（如短周期文本 `甲乙丙甲乙丙…` 中互不重叠窗口不足 6 字），则不构成合格重复。

续接失败、段数/长度不合法、缺字段时同样返回 **422**（续接失败时给出 `failed_segment`，从 0 开始）。

## 计分与并列规则

- 相同字 **+2**；`?` 与任意字配对 **0**；异字 **-2**；
- 连续空缺：首字 **-3**，其余每字 **-1**；
- 只将左段后缀与右段前缀对齐；左段未参与对齐的前缀、右段未参与对齐的后缀**不计分**；
- 对齐区**至少包含一对字符**；
- 同分并列时，取**对齐字符对数最多**者；仍并列，取**左段起点最小**者。

## 拼接规则

- `?` 以对方已知字替换（双方均为 `?` 时保留 `?`）；
- 异字保留左段字，并在 `conflicts` 中列出双方原文位置及字形；
- `/api/assemble` 在此规则上额外保留**逐字来源**：相同字、`?` 补字双方、异字冲突双方的
  原始段序号与下标均不丢失；只有满足续接门槛（得分 > 0 且至少 2 对相同已知字）才会并入下一段。
- `/api/collate` 不修改以上拼接结果，只基于拼接文本与逐字来源做段级投票：同段重复来源只计一次、
  `?` 不投票，仅列出至少两种不同已知字的异文位置；唯一最高票给建议字，并列则建议为 `null`。
- `/api/order` 对 2～4 段未排序转写穷举全部排列，逐段复用上述续接门槛（不满足即废弃该排列），
  以**各步对齐得分的累计**比较完整顺序的优劣（非原段两两相似度）；最高分唯一返回该顺序（来源按
  **原输入下标**标记），最高分并列返回 **409** 并列出全部并列顺序，无完整顺序返回 **422**。
- `/api/revise` 复用 `/api/assemble` 的拼接文本与逐字来源，把每项人工校订（段序号、原文下标、
  替换字）沿逐字来源定位到输出位置落实改字：重叠段指向同一位置的相同改字合并、不同改字返回 **409**，
  坐标越界或无法唯一定位返回 **422**；不重新对齐，未涉及位置保持原字，逐字来源沿用不变。
- `/api/locate-quote` 复用 `/api/assemble` 的拼接文本与逐字来源（沿用段数/长度限制与续接失败规则），
  把 1～80 字引文与拼接文本的任意非空连续区间比较：相同字或任一侧 `?` 代价 0，替换、插入、删除各
  代价 1，区间两端自由、引文完全消耗；最小代价不超过 2 且区间唯一时返回左闭右开区间、原文片段、
  代价与该区间逐字 sources，多个不同区间并列返回 **409**，无合格区间返回 **422**；只定位、不改写
  拼接文本。
- `/api/locate-quotes` 对 2～4 段按原文顺序排列的引文（各 1～80 字），枚举每段代价不超过 2 的全部
  非空区间（代价规则同上），再选区间按序、两两不重叠（前段 `end` ≤ 后段 `start`）且总代价最低的
  完整定位链；某段单独最优候选无法成链时仍考虑该段其余候选。唯一最优链返回各引文区间、片段、代价与
  sources，多个不同最优链并列返回 **409**（两条不同最优链），无完整链返回 **422**。
- `/api/find-repetition` 复用 `/api/assemble` 的拼接文本与逐字来源（沿用段数/长度限制与续接失败
  规则），在同一份拼接文本中找两个互不重叠（允许贴合）的等长连续区间：对应字相同或任一字为 `?`
  即兼容，长度至少 6 且至少 4 个位置两侧已知字相同；取长度最长者，同长度取已知相同位更多者，再按
  两起点升序取首对，返回两个左闭右开区间及各自原文与逐字 sources；无合格重复时 `repeat` 为 `null`。

## 本地开发（不使用 Docker）

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## 运行测试

```bash
pip install -r requirements.txt requirements-dev.txt
pytest
```

## 项目结构

```
app/
  aligner.py    # 核心算法：后缀-前缀重叠对齐（仿射空缺罚分 DP + 回溯）
  assembler.py  # 多段顺序拼接：逐段复用对齐 + 续接门槛 + 逐字来源
  collator.py   # 异文校勘：复用拼接文本与逐字来源，段级投票回查原字
  orderer.py    # 未排序转写：穷举排列 + 累计对齐得分选序 + 并列/无完整顺序判定
  reviser.py    # 人工校订：沿逐字来源定位校订并落实改字 + 合并/冲突/定位判定
  locator.py    # 引文定位：半全局编辑代价 DP 查拼接文本区间；多引文按序不重叠最优链 + 并列/无完整链判定
  repetition.py # 重复抄写发现：对角扫描兼容 run + 滑动窗口取最长/已知相同位最多的非重叠等长区间对
  main.py       # FastAPI 接口与请求/响应模型（/api/align、/api/assemble、/api/collate、/api/order、/api/revise、/api/locate-quote、/api/locate-quotes、/api/find-repetition）
tests/          # 算法与接口测试
Dockerfile      # 镜像构建（含依赖安装）
docker-compose.yml
```
