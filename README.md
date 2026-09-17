# AstrBot 插件 - Squad 服务器状态查询

一个用于查询战术小队(Squad)游戏服务器状态的 AstrBot 插件。

## 功能特性

- 🎮 查询 Squad 服务器实时状态信息
- 🔍 支持服务器名称关键字模糊搜索
- 🇨🇳 按国别筛选国内服务器（支持境外机房的中文服）
- ⚡ 自动过滤满员服务器，只展示能进得去的活跃服
- 📊 按人数排序显示
- 🎨 支持自定义显示字段
- 🤖 **AI 自由调用**：注册为 LLM Tool，AI 可自主组合国别/语言/地图/人数/排序/条数等 14 个参数查询

## 命令说明

### 查询服务器状态

**命令格式:**
```
/squad_server [服务器名称关键字]
```

**中文别名:**
```
/战术小队服务器 [服务器名称关键字]
```

查询结果首行会给出命中统计与**本次生效的筛选口径**（如 `🔎 命中 23 台（筛选：国内服 · ≥60人 · 未满员 · 排除0人服），返回 5 台 | 国内服共 141 台`），便于判断是否还有更多结果，也避免把被默认门槛过滤后的数字误读成“国内服一共就这么多台”。只想问数量时（如“国服有多少台”），AI 会传 `count_only=true`，直接回报真实总数。

### 使用示例

```
# 查询所有符合条件的服务器（未满员且人数≥60）
/squad_server

# 搜索包含"CN"的服务器
/squad_server CN

# 搜索特定服务器名称
/squad_server 福星
```

## 显示字段

### 默认显示
| 字段 | 说明 |
|------|------|
| 服务器名称 | 服务器完整名称 |
| 玩家数 | 当前人数 / 人数上限 |
| Ping | 延迟；当前数据源不提供，统一显示"未知" |

### 扩展字段（可配置）
| 字段 | 说明 | 数据源支持 |
|------|------|-----------|
| `map` | 当前地图名称 | ✅ |
| `mode` | 游戏模式（数据源列表接口不提供，留空不显示） | ❌ |
| `version` | 游戏版本号 | ✅ |
| `ip` | 服务器IP地址和端口 | ✅ |
| `country` | 服务器所在地区（ISO 国别码，如 CN / RU） | ✅ |
| `language` | 服务器语言（如 zh / en / ru） | ✅ |
| `queue` | 排队人数（数据源不提供，恒为 0 故不显示） | ❌ |

## 配置说明

### 配置项列表

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `ping_threshold` | 200 | Ping 阈值（ms）。当前数据源不提供延迟数据，此选项暂不生效 |
| `min_players` | 60 | 无参数查询时的最低人数门槛 |
| `max_results` | 10 | 默认返回条数；AI 调用工具时可用 `limit` 参数按次覆盖（上限 100） |
| `show_extra_fields` | false | 是否显示额外字段 |
| `extra_fields` | ["map", "mode"] | 额外显示的字段列表（可选 map/mode/version/ip/country/language/queue） |
| `debug_mode` | false | 调试模式，启用后使用模拟数据 |
| `fallback_to_mock` | true | API 不可用时自动使用模拟数据（模拟数据非真实状态，生产环境建议关闭） |
| `cn_only` | true | 仅显示国内服务器：`country` 为 CN，或名称包含中文字符 |

### 配置示例

```json
{
    "ping_threshold": 200,
    "min_players": 60,
    "max_results": 10,
    "show_extra_fields": true,
    "extra_fields": ["map", "version"],
    "debug_mode": false,
    "fallback_to_mock": false,
    "cn_only": true
}
```

## AI 智能调用

插件已注册为 LLM Tool，AI 可以在对话中自动调用查询功能，无需用户输入命令前缀。

### 使用示例

```
# 用户自然语言查询
用户: "查一下Squad服务器"
AI: 自动调用工具，返回服务器列表

用户: "有没有人在玩战术小队"
AI: 自动调用工具，返回活跃服务器

用户: "福星服务器现在有多少人"
AI: 自动调用工具，返回包含"福星"的服务器
```

### Tool 配置

- **工具名称**: `query_squad_server`
- **描述**: 查询战术小队(Squad)服务器实时状态，可自由组合筛选条件并指定返回条数与排序

### Tool 参数

所有参数都是可选的；不传时按插件配置返回“未满员且人数达标”的国内服。

| 参数 | 类型 | 说明 |
|------|------|------|
| `keyword` | string | 服务器名称关键字（模糊匹配，不区分大小写） |
| `countries` | array[string] | 国别代码列表，如 `["CN","US"]`；**传入后按国家严格筛选，覆盖 `cn_only`** |
| `languages` | array[string] | 语言代码列表，如 `["zh"]` 查中文服、`["en"]` 查英文服 |
| `map_keyword` | string | 地图名关键字，如 `"Mutaha"` |
| `min_players` | number | 最低当前人数 |
| `max_players` | number | 最高当前人数 |
| `limit` | number | **返回条数上限（1-100）**，留空用配置的 `max_results` |
| `sort_by` | string | 排序字段：`players`(默认) / `name` / `map` / `fill`(满员度) |
| `order` | string | 排序方向：`desc`(默认) / `asc` |
| `only_joinable` | boolean | 只返回未满员（还能进）的服务器；留空时无关键字查询默认为 true |
| `include_empty` | boolean | 是否包含 0 人的服务器；留空时带关键字查询默认为 true |
| `cn_only` | boolean | 是否只看国内服；留空用插件配置 |
| `count_only` | boolean | **只统计数量**（如“国服有多少台”）：不受插件配置的人数门槛、未满员与排除空服默认值影响，返回按显式条件过滤后的真实总数 |
| `show_fields` | array[string] | 本次额外显示的字段：map/mode/version/ip/country/language |
| `compact` | boolean | true 时每台服务器压成一行（名称+人数），适合一次查询较多服务器 |

### AI 调用示例

| 用户说法 | AI 可能传入的参数 |
|----------|------------------|
| “有哪些国服还没满” | `countries=["CN"], only_joinable=true` |
| “美服有人吗” | `countries=["US"], min_players=1` |
| “给我 30 台服的名单” | `limit=30, compact=true` |
| “Mutaha 这图现在打的人多吗” | `map_keyword="Mutaha", sort_by="fill"` |
| “中文服前 3 名” | `languages=["zh"], limit=3` |
| “空服和满员服都列出来” | `include_empty=true, only_joinable=false, min_players=0` |
| “国服一共有多少台” | `count_only=true` |
| “CN 机房有多少台服” | `count_only=true, countries=["CN"]` |

## 查询逻辑

参数优先级统一为 **显式传参 > 插件配置**。

### 统计口径（`count_only=true`）
- 用于回答“有多少台 / 几台 / 总数”这类纯计数问题
- 只按显式传入的条件统计，**不套用**插件配置的 `min_players` 门槛、满员过滤与空服过滤
- 输出形如 `📊 命中 141 台（筛选：国内服 · 不限人数 · 含满员 · 含0人服）` + `📡 数据源在线服务器共 587 台`
- 不受 `limit` / `max_results` 影响（只回报数量，不列服务器）

### 不带参数查询（宽泛查询）
- 仅返回 `cn_only` 筛中的服务器（除非显式传 `countries` 或 `cn_only=false`）
- 仅返回人数 ≥ `min_players` 的服务器（除非显式传 `min_players`）
- 排除满员服务器（除非 `only_joinable=false`）
- 排除 0 人服务器（除非 `include_empty=true`）
- 按 `sort_by` / `order` 排序（默认人数降序），最多返回 `limit` 条（默认 `max_results`）
- 输出首行同时回报**国内服总数**，便于与命中数对比（如命中 23 台 / 国内服共 141 台）

### 带参数查询（关键词搜索）
- 根据关键字模糊匹配服务器名称（不区分大小写）
- **仍受 `cn_only` 国别筛选约束**
- 不额外施加人数门槛与满员过滤（保持旧行为），但显式传入的 `min_players` / `only_joinable` 等参数同样生效
- 最多返回 `limit` 条（默认 `max_results`）

### 参数兜底
- `limit` 硬上限 100，超出会被截断到 100
- 未知的 `sort_by` 回退 `players`，非数字的 `limit` 回退配置值，非法参数不会报错

## 数据来源

插件使用 **GAMEMONITORING 公开 API**（免费、无需认证、无需 API Key）：

| 项目 | 说明 |
|------|------|
| 接口地址 | `https://api.gamemonitoring.ro`（镜像：`https://api.gamemonitoring.net`） |
| 拉取方式 | `GET /servers?game=393380&status=1&sort=numplayers&order=desc&limit=500&offset=N` |
| game 参数 | Squad 的 Steam AppID `393380` |
| 拉取范围 | 仅在线服务器（`status=1`），按人数降序分页，每页 500 条，最多 4 页 |
| 实测覆盖 | 约 570+ 台在线服务器（其中大陆服务器约 130 台） |
| 数据新鲜度 | 服务端扫描周期约 1～2 分钟 |

接口返回的原始字段（`numplayers` / `maxplayers` / `status` 布尔值等）由插件内的适配层
（`normalize_server_data`）转换为统一格式后使用。

### 数据说明

- **Ping 值**：GAMEMONITORING 不返回延迟数据，统一显示为"未知"；`ping_threshold` 选项因此暂不生效。
- **排队人数**：接口不提供，恒为 0，因此不显示排队信息。
- **地图 / 版本 / 国别**：分别取自 `map`、`version`、`country` 字段。
- **模式（AAS/RAAS/Invasion 等）**：列表接口不返回，插件不额外为每台服务器发起详情请求，故留空。

如果 API 不可用且 `fallback_to_mock` 为 true，插件会切换到内置模拟数据以免报错；
生产环境建议将其设为 false，脚本会直接提示"查询失败"而不是展示模拟数据。

## 安装指南

### 方法一：插件市场安装

1. 打开 AstrBot WebUI
2. 进入插件市场
3. 搜索 "squad_server_status"
4. 点击安装

### 方法二：手动安装

1. 下载插件文件
2. 将插件目录复制到 AstrBot 的 `data/plugins/` 目录下
3. 重启 AstrBot 或在 WebUI 中启用插件
4. 在插件配置页面调整各项参数

## 依赖说明

- Python 3.10+（插件运行于 AstrBot v4.16+，AstrBot 自身要求 Python 3.12）
- aiohttp 库（用于异步 API 请求）

## 文件结构

```
astrbot_plugin_squad_server_status/
├── metadata.yaml          # 插件元数据
├── _conf_schema.json      # 配置文件定义
├── requirements.txt       # Python 依赖
├── main.py                # 插件主代码
├── README.md              # 说明文档
├── CHANGELOG.md           # 更新日志
├── LICENSE                # MIT 许可证
├── _astrbot_stub.py       # 测试用的 AstrBot 依赖替身
├── test_plugin.py         # 离线单元测试（78 项断言）
└── test_real_api.py       # 联网集成测试（20 项断言）
```

## 测试

```bash
# 离线单元测试：字段适配、筛选、分页、缓存、容错、分段输出、统计口径、LLM 工具参数与 docstring 契约
python test_plugin.py

# 联网集成测试：真实调用 API 并驱动插件抓取/查询链路
python test_real_api.py
```

两个脚本都以非零退出码表示存在失败项，可直接接入 CI。

联网测试覆盖：
- API 连通性与抓取耗时
- 分页拉取与字段适配（人数、地图、版本、国别、无 Ping 哨兵值）
- 60 秒缓存命中
- 无参数查询、关键字查询、无匹配提示
- `cn_only` 开关下的国内外服务器表现
- 统计口径 `count_only`（国内服总数 / 全部在线服总数）与结果首行口径说明

## 注意事项

1. **网络环境**：插件依赖外部 API，需确保 AstrBot 服务器可访问 `api.gamemonitoring.ro`
   （Cloudflare 托管，国内直连可用，实测单次请求 1～2 秒）。
2. **数据缓存**：服务器数据缓存 60 秒，避免频繁请求；单次抓取通常为 1～2 次 HTTP 请求。
3. **模拟数据**：`debug_mode` 或 API 不可用且开启 `fallback_to_mock` 时使用内置模拟数据，
   模拟数据不是真实服务器状态，仅用于调试。
4. **已移除的旧数据源**：SquadCalc API（Squad 覆盖不足）与 BattleMetrics API（国内网络不可达），
   本版本不再使用，也不保留备用源。

## 许可证

MIT License

## 更新日志

### v1.2.0
- LLM Tool 参数全面开放：`query_squad_server` 由单一 `keyword` 扩展为 14 个参数
  （国别/语言/地图/人数区间/条数/排序/是否排除满员/是否含空服/显示字段/紧凑模式）
- 查询结果新增“命中 N 台，返回 M 台”统计行
- 显示字段新增 `country` / `language`
- 离线测试扩充至 64 项，新增 docstring 参数契约测试

### v1.1.0
- 数据源替换为 GAMEMONITORING 公开 API，移除 SquadCalc 与 BattleMetrics
- 新增字段适配层，支持 `numplayers` / `maxplayers` / `status` 布尔值等原始字段
- `cn_only` 改为按 `country` 字段判定，兼容境外机房的中文服
- 新增离线单元测试与联网集成测试（详见 CHANGELOG.md）

### v1.0.0
- 初始版本
- 支持服务器状态查询
- 支持关键字搜索
- 支持配置项自定义
- 支持模拟数据模式
