# AstrBot 插件 - Squad 服务器状态查询

一个用于查询战术小队(Squad)游戏服务器状态的 AstrBot 插件。

## 功能特性

- 🎮 查询 Squad 服务器状态信息
- 🔍 支持服务器名称关键字模糊搜索
- ⚡ 自动过滤高延迟服务器
- 📊 按人数排序显示
- 🎨 支持自定义显示字段

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
# 查询所有符合条件的服务器（未满人且人数≥60，Ping<200）
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
| 排队人数 | 等待进入服务器的玩家数 |
| Ping | 延迟（毫秒） |

### 扩展字段（可配置）
| 字段 | 说明 |
|------|------|
| `map` | 当前地图名称 |
| `mode` | 游戏模式（AAS/RAAS/Invasion等） |
| `version` | 游戏版本号 |
| `ip` | 服务器IP地址和端口 |

## 配置说明

### 配置项列表

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `ping_threshold` | 200 | Ping 阈值（ms），仅返回 Ping 小于此值的服务器 |
| `min_players` | 60 | 无参数查询时的最低人数门槛 |
| `max_results` | 10 | 单次查询最大返回条数 |
| `show_extra_fields` | false | 是否显示额外字段 |
| `extra_fields` | ["map", "mode"] | 额外显示的字段列表 |
| `debug_mode` | false | 调试模式，启用后使用模拟数据 |
| `fallback_to_mock` | true | API 失败时自动使用模拟数据 |
| `cn_only` | true | 仅显示中文服务器，开启后只返回服务器名称包含中文字符的服务器 |

### 配置示例

```json
{
    "ping_threshold": 200,
    "min_players": 60,
    "max_results": 10,
    "show_extra_fields": true,
    "extra_fields": ["map", "mode", "version"],
    "debug_mode": false,
    "fallback_to_mock": true,
    "cn_only": true
}
```

## 查询逻辑

### 带参数查询（关键词搜索）
- 根据关键字模糊匹配服务器名称（不区分大小写）
- **仅进行中文检测**（如果开启 `cn_only`）
- 返回结果按人数从高到低排序
- 最多返回 `max_results` 条

### 不带参数查询
- 返回所有未满人的服务器（当前人数 < 人数上限）
- 仅返回人数 ≥ `min_players` 的服务器
- 仅返回 Ping < `ping_threshold` 的服务器
- **仅返回排队人数为 0 的服务器**
- 返回结果按人数从高到低排序
- 最多返回 `max_results` 条

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
- requests 库（用于 API 请求）

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
├── test_plugin.py         # 模拟数据测试脚本
└── test_real_api.py       # 真实API测试脚本
```

## 数据来源

插件使用以下 API 源获取服务器数据：
1. **SquadCalc API** (`https://squadcalc.app/api/get/servers`) - 主要数据源，免费公开，无需认证
2. **BattleMetrics API** - 备用数据源（需要网络可访问）

### 数据说明

- **Ping 值**：SquadCalc API 不返回 Ping 值，显示为"未知"。如果需要真实 Ping，可能需要通过其他方式获取（如 Steam 服务器查询协议）。
- **排队人数**：通过 `squad_publicQueue` 字段获取。
- **地图和模式**：通过服务器详情的 `map` 和 `gameMode` 字段获取。

如果所有 API 源都不可用（如网络限制），插件会自动切换到模拟数据模式，确保功能正常运行。

## 测试

运行测试脚本验证插件逻辑：

```bash
python test_plugin.py
```

测试包含以下场景：
- 不带参数查询
- 带关键字查询
- 无匹配结果处理
- 扩展字段显示
- Ping 阈值过滤
- 最低人数门槛
- 最大返回条数限制

## 注意事项

1. **网络环境**：插件依赖外部 API，需要确保 AstrBot 服务器能够访问互联网
2. **数据缓存**：服务器数据会缓存 60 秒，避免频繁请求
3. **模拟数据**：调试模式或 API 不可用时使用模拟数据，不影响功能测试

## 许可证

MIT License

## 更新日志

### v1.0.0
- 初始版本
- 支持服务器状态查询
- 支持关键字搜索
- 支持配置项自定义
- 支持模拟数据模式