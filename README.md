# AstrBot 插件 - Squad 服务器状态查询

一个用于查询战术小队(Squad)游戏服务器状态的 AstrBot 插件。

## 功能特性

- 🎮 查询 Squad 服务器实时状态信息
- 🔍 支持服务器名称关键字模糊搜索
- 🇨🇳 按国别筛选国内服务器（支持境外机房的中文服）
- ⚡ 自动过滤满员服务器，只展示能进得去的活跃服
- 📊 按人数排序显示
- 🎨 支持自定义显示字段
- 🤖 **AI 自动调用**：注册为 LLM Tool，AI 可根据对话上下文自主调用

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
| `queue` | 排队人数（数据源不提供，恒为 0 故不显示） | ❌ |

## 配置说明

### 配置项列表

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `ping_threshold` | 200 | Ping 阈值（ms）。当前数据源不提供延迟数据，此选项暂不生效 |
| `min_players` | 60 | 无参数查询时的最低人数门槛 |
| `max_results` | 10 | 单次查询最大返回条数 |
| `show_extra_fields` | false | 是否显示额外字段 |
| `extra_fields` | ["map", "mode"] | 额外显示的字段列表 |
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
- **描述**: 查询战术小队(Squad)服务器状态，可按关键词搜索或返回所有活跃服务器
- **参数**: `keyword`（可选）- 服务器名称关键字

## 查询逻辑

### 带参数查询（关键词搜索）
- 根据关键字模糊匹配服务器名称（不区分大小写）
- **仍受 `cn_only` 国别筛选约束**
- 返回结果按人数从高到低排序
- 最多返回 `max_results` 条

### 不带参数查询
- 返回所有未满人的服务器（当前人数 < 人数上限）
- 仅返回人数 ≥ `min_players` 的服务器
- 仅返回 `cn_only` 筛中的服务器
- 返回结果按人数从高到低排序
- 最多返回 `max_results` 条

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

- Python 3.8+
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
├── test_plugin.py         # 离线单元测试（41 项断言）
└── test_real_api.py       # 联网集成测试（20 项断言）
```

## 测试

```bash
# 离线单元测试：字段适配、筛选、分页、缓存、容错、分段输出
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
