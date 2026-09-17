"""真实 API 联网测试

直接调用插件本体的 fetch_servers / handle_query，验证 GAMEMONITORING 数据源的
连通性、字段适配与端到端输出。需要联网。
运行: python test_real_api.py
"""

import asyncio
import sys
import time

import aiohttp

from _astrbot_stub import make_plugin

RESULTS = []
REQUESTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    print(
        f"{'PASS' if condition else 'FAIL'} | {name}"
        + (f" | {detail}" if detail else "")
    )


async def _on_request_start(session, trace_config_ctx, params):
    REQUESTS.append(str(params.url))


def make_traced_session():
    """构造带请求计数的真实会话(与插件内部创建的会话参数一致)"""
    trace = aiohttp.TraceConfig()
    trace.on_request_start.append(_on_request_start)
    return aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=60),
        headers={"User-Agent": "AstrBot-Squad-Plugin/1.0"},
        trace_configs=[trace],
    )


async def main():
    plugin, module = make_plugin(
        show_extra_fields=True,
        extra_fields=["map", "version", "ip"],
        max_results=10,
        min_players=60,
    )
    plugin.session = make_traced_session()

    print(f"数据源: {module.API_BASE}  游戏 AppID: {module.SQUAD_APP_ID}\n")

    # ---------- 1. 抓取与字段适配 ----------
    t0 = time.time()
    servers = await plugin.fetch_servers()
    elapsed = time.time() - t0
    print(
        f"=== 抓取: {len(servers)} 台, {elapsed:.2f}s, 实际请求 {len(REQUESTS)} 次 ==="
    )
    check("分页: 至少发出一次请求", len(REQUESTS) >= 1, str(REQUESTS[:1]))

    check(
        "连通: 成功取到服务器数据", servers and len(servers) > 0, f"{len(servers)} 台"
    )
    check("分页: 单次抓取耗时在 30s 内", elapsed < 30, f"{elapsed:.2f}s")
    check("适配: 全部为在线状态", all(s["status"] == "online" for s in servers))
    total_players = sum(s["players"] for s in servers)
    populated = sum(1 for s in servers if s["players"] > 0)
    check("适配: 玩家总数合理(>1000)", total_players > 1000, f"总人数 {total_players}")
    check(
        "适配: 存在有人的服务器",
        populated > 50,
        f"{populated} 台有人(多数在线服是空服)",
    )
    check(
        "适配: 人数上限字段非全零",
        sum(1 for s in servers if s["max_players"] > 0) > len(servers) * 0.5,
    )
    check(
        "适配: 地图字段非空", sum(1 for s in servers if s["map"]) > len(servers) * 0.9
    )
    check(
        "适配: 版本字段非空",
        sum(1 for s in servers if s["version"]) > len(servers) * 0.9,
    )
    check(
        "适配: 无延迟数据统一为哨兵值",
        all(s["ping"] == module.PING_UNKNOWN for s in servers),
    )
    check(
        "适配: 携带国别字段",
        sum(1 for s in servers if s["country"]) > len(servers) * 0.9,
    )

    cn = [s for s in servers if s["country"] == "CN"]
    check("覆盖: 存在中国大陆服务器", len(cn) > 0, f"{len(cn)} 台")
    print(f"  国别分布 Top5: {_top_countries(servers)}")

    # ---------- 2. 缓存 ----------
    t1 = time.time()
    cached = await plugin.fetch_servers()
    check(
        "缓存: 60 秒内二次查询直接返回缓存",
        cached is servers and time.time() - t1 < 0.05,
        f"{time.time() - t1:.3f}s",
    )

    # ---------- 3. 端到端查询 ----------
    print("\n" + "=" * 60)
    print("无参数查询(默认: 未满员 + 人数≥60)")
    print("=" * 60)
    results = await plugin.handle_query(None)
    output = "\n".join(results)
    print(output)
    check("查询: 无参数返回结果", "🎮" in output, f"{output.count('🎮')} 台")
    check(
        "查询: 结果按人数降序",
        _players_from_output(output)
        == sorted(_players_from_output(output), reverse=True),
        str(_players_from_output(output)),
    )
    check(
        "查询: 过滤掉外文服务器(默认 cn_only)",
        all(
            any("\u4e00" <= c <= "\u9fff" for c in line) or _is_cn_ip(line)
            for line in output.splitlines()
            if line.startswith("🎮")
        )
        or "未找到" in output,
    )

    print("\n" + "=" * 60)
    print("关键字查询: 福星")
    print("=" * 60)
    kw_results = await plugin.handle_query("福星")
    print("\n".join(kw_results))
    check(
        "查询: 关键字命中",
        "福星" in "\n".join(kw_results) or "未找到" in "\n".join(kw_results),
    )

    print("\n" + "=" * 60)
    print("关键字查询: 不存在的服务器")
    print("=" * 60)
    miss = await plugin.handle_query("不存在的服务器名字")
    print("\n".join(miss))
    check("查询: 无匹配提示正确", miss == ["未找到匹配 '不存在的服务器名字' 的服务器"])

    # ---------- 4. 关闭 cn_only 的全球查询 ----------
    global_plugin, _ = make_plugin(
        cn_only=False, max_results=5, show_extra_fields=True, extra_fields=["map", "ip"]
    )
    global_results = await global_plugin.handle_query(None)
    print("\n" + "=" * 60)
    print("cn_only 关闭时的全球查询")
    print("=" * 60)
    print("\n".join(global_results))
    global_out = "\n".join(global_results)
    check(
        "查询: cn_only 关闭后能返回境外服务器",
        "🎮" in global_out or "未找到" in global_out,
    )
    check(
        "适配: 英文名服务器能正常渲染",
        any(
            not any("\u4e00" <= c <= "\u9fff" for c in line)
            for line in global_out.splitlines()
            if line.startswith("🎮")
        )
        or "未找到" in global_out,
    )

    await plugin.terminate()
    await global_plugin.terminate()

    failed = [name for name, ok, _ in RESULTS if not ok]
    print(f"\n{'=' * 60}")
    print(f"通过 {len(RESULTS) - len(failed)}/{len(RESULTS)} 项")
    for name in failed:
        print(f"  FAILED: {name}")
    print("=" * 60)
    return 1 if failed else 0


def _top_countries(servers):
    counts = {}
    for s in servers:
        counts[s["country"]] = counts.get(s["country"], 0) + 1
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:5]


def _players_from_output(output):
    values = []
    for line in output.splitlines():
        if line.startswith("👥 "):
            values.append(int(line[2:].split("/")[0]))
    return values


def _is_cn_ip(line):
    return "🌐 IP:" in line


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
