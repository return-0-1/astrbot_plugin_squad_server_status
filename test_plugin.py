import asyncio

class MockConfig:
    def __init__(self, **kwargs):
        self._config = kwargs
    
    def get(self, key, default=None):
        return self._config.get(key, default)

class SquadServerStatusCore:
    def __init__(self, config):
        self.config = config
        self.cache = {}
        self.cache_time = 0

    def get_mock_servers(self):
        return [
            {"name": "[CN] 福星2 通宵侵攻服", "players": 98, "max_players": 100, "ping": 35, "queue": 5, "status": "online", "map": "Narva_Invasion_v2", "mode": "Invasion", "version": "v10.5.1", "ip": "180.188.21.57", "port": 22007},
            {"name": "[CN] 利群 通宵猛攻服", "players": 95, "max_players": 100, "ping": 42, "queue": 3, "status": "online", "map": "AlBasrah_RAAS_v2", "mode": "RAAS", "version": "v10.5.1", "ip": "202.189.8.149", "port": 20101},
            {"name": "[CN] W.E萌新轻松娱乐服", "players": 68, "max_players": 99, "ping": 55, "queue": 0, "status": "online", "map": "Mutaha_RAAS_v1", "mode": "RAAS", "version": "v10.5.1", "ip": "180.188.21.57", "port": 22001},
            {"name": "[RU] PHEX 凤凰服务器", "players": 98, "max_players": 100, "ping": 180, "queue": 0, "status": "online", "map": "Mutaha_RAAS_v1", "mode": "RAAS", "version": "v10.5.1", "ip": "80.242.59.123", "port": 7807},
            {"name": "[GER] Steel Division", "players": 75, "max_players": 98, "ping": 210, "queue": 0, "status": "online", "map": "Harju_Seed_v1", "mode": "Seed", "version": "v10.5.1", "ip": "84.200.132.197", "port": 7787},
            {"name": "[CN] SDF叙利亚僵尸服", "players": 45, "max_players": 98, "ping": 48, "queue": 0, "status": "online", "map": "SQZR_AlBasrah_LastStand", "mode": "Zombies", "version": "v10.5.1", "ip": "202.189.10.78", "port": 7789},
            {"name": "[AU] BigD.com.au #1", "players": 97, "max_players": 98, "ping": 220, "queue": 0, "status": "online", "map": "AlBasrah_RAAS_v3", "mode": "RAAS", "version": "v10.5.1", "ip": "squad1.bigd.com.au", "port": 26040},
            {"name": "[US] Baja Boys Invasion", "players": 80, "max_players": 98, "ping": 195, "queue": 2, "status": "online", "map": "Sanxian_Invasion_v2", "mode": "Invasion", "version": "v10.5.1", "ip": "198.133.237.24", "port": 10250},
            {"name": "[CN] 五年老服 僵尸服", "players": 55, "max_players": 98, "ping": 38, "queue": 0, "status": "online", "map": "SQZR_AlBasrah_LastStand", "mode": "Zombies", "version": "v10.5.1", "ip": "202.189.10.78", "port": 7789},
            {"name": "[UA] Ukr.Games #1", "players": 99, "max_players": 100, "ping": 190, "queue": 0, "status": "online", "map": "Yehorivka_AAS_v2", "mode": "AAS", "version": "v10.5.1", "ip": "57.128.211.165", "port": 7787},
            {"name": "[CN] 军团要塞 战术服", "players": 72, "max_players": 100, "ping": 45, "queue": 1, "status": "online", "map": "Gorodok_RAAS_v2", "mode": "RAAS", "version": "v10.5.1", "ip": "180.188.21.57", "port": 22005}
        ]

    async def fetch_servers(self):
        if self.config.get("debug_mode", False):
            return self.get_mock_servers()
        return None

    def filter_servers(self, servers, keyword=None):
        ping_threshold = self.config.get("ping_threshold", 200)
        min_players = self.config.get("min_players", 60)
        max_results = self.config.get("max_results", 10)

        filtered = []
        for server in servers:
            try:
                if not isinstance(server, dict):
                    continue

                ping = int(server.get("ping", 999))
                players = int(server.get("players", 0))
                max_players = int(server.get("max_players", 0))
                status = str(server.get("status", "")).lower()

                if ping >= ping_threshold:
                    continue

                if status != "online":
                    continue

                name = server.get("name", "")
                if not name:
                    continue

                if keyword:
                    if keyword.lower() not in name.lower():
                        continue
                else:
                    if players < min_players:
                        continue
                    if players >= max_players:
                        continue

                filtered.append(server)
            except (ValueError, TypeError) as e:
                continue

        filtered.sort(key=lambda s: int(s.get("players", 0)), reverse=True)
        return filtered[:max_results]

    def format_server_info(self, server):
        name = server.get("name", "未知服务器")
        players = int(server.get("players", 0))
        max_players = int(server.get("max_players", 0))
        ping = int(server.get("ping", 0))
        queue = int(server.get("queue", 0))

        result = f"🎮 {name}\n"
        result += f"👥 {players}/{max_players}"
        if queue > 0:
            result += f" | 排队: {queue}"
        result += f"\n⏱️ Ping: {ping}ms"

        if self.config.get("show_extra_fields", False):
            extra_fields = self.config.get("extra_fields", [])

            if "map" in extra_fields:
                map_name = server.get("map", "")
                if map_name:
                    result += f"\n🗺️ 地图: {map_name}"

            if "mode" in extra_fields:
                mode = server.get("mode", "")
                if mode:
                    result += f"\n⚔️ 模式: {mode}"

            if "version" in extra_fields:
                version = server.get("version", "")
                if version:
                    result += f"\n📦 版本: {version}"

            if "ip" in extra_fields:
                ip = server.get("ip", "")
                port = server.get("port", "")
                if ip:
                    result += f"\n🌐 IP: {ip}:{port}"

        return result

    async def handle_query(self, keyword=None):
        servers = await self.fetch_servers()

        if not servers:
            return ["查询失败，请稍后重试"]

        filtered = self.filter_servers(servers, keyword)

        if not filtered:
            if keyword:
                return [f"未找到匹配 '{keyword}' 的服务器"]
            else:
                return ["未找到符合条件的服务器"]

        result_lines = []
        for i, server in enumerate(filtered, 1):
            info = self.format_server_info(server)
            result_lines.append(f"--- [{i}] ---")
            result_lines.append(info)

        result = "\n".join(result_lines)

        if len(result) > 2000:
            chunks = []
            current_chunk = ""
            for line in result_lines:
                if len(current_chunk) + len(line) > 1800:
                    chunks.append(current_chunk)
                    current_chunk = line
                else:
                    current_chunk += "\n" + line if current_chunk else line
            if current_chunk:
                chunks.append(current_chunk)
            return chunks
        else:
            return [result]

async def test_no_keyword():
    print("="*60)
    print("测试1: 不带参数查询（返回未满人且人数≥60，Ping<200）")
    print("="*60)
    
    config = MockConfig(
        ping_threshold=200,
        min_players=60,
        max_results=10,
        show_extra_fields=False,
        debug_mode=True
    )
    
    plugin = SquadServerStatusCore(config)
    results = await plugin.handle_query(None)
    
    for result in results:
        print(result)
        print()

async def test_with_keyword():
    print("="*60)
    print("测试2: 带关键字查询 'CN'（模糊匹配中文服务器）")
    print("="*60)
    
    config = MockConfig(
        ping_threshold=200,
        min_players=60,
        max_results=10,
        show_extra_fields=False,
        debug_mode=True
    )
    
    plugin = SquadServerStatusCore(config)
    results = await plugin.handle_query("CN")
    
    for result in results:
        print(result)
        print()

async def test_with_keyword_not_found():
    print("="*60)
    print("测试3: 带关键字查询 '不存在的服务器'（无匹配）")
    print("="*60)
    
    config = MockConfig(
        ping_threshold=200,
        min_players=60,
        max_results=10,
        show_extra_fields=False,
        debug_mode=True
    )
    
    plugin = SquadServerStatusCore(config)
    results = await plugin.handle_query("不存在的服务器")
    
    for result in results:
        print(result)
        print()

async def test_with_extra_fields():
    print("="*60)
    print("测试4: 不带参数查询（开启额外字段：地图、模式、版本）")
    print("="*60)
    
    config = MockConfig(
        ping_threshold=200,
        min_players=60,
        max_results=5,
        show_extra_fields=True,
        extra_fields=["map", "mode", "version"],
        debug_mode=True
    )
    
    plugin = SquadServerStatusCore(config)
    results = await plugin.handle_query(None)
    
    for result in results:
        print(result)
        print()

async def test_ping_threshold():
    print("="*60)
    print("测试5: Ping阈值设置为100（过滤高延迟服务器）")
    print("="*60)
    
    config = MockConfig(
        ping_threshold=100,
        min_players=60,
        max_results=10,
        show_extra_fields=False,
        debug_mode=True
    )
    
    plugin = SquadServerStatusCore(config)
    results = await plugin.handle_query(None)
    
    for result in results:
        print(result)
        print()

async def test_min_players():
    print("="*60)
    print("测试6: 最低人数门槛设置为80（只显示人数≥80的服务器）")
    print("="*60)
    
    config = MockConfig(
        ping_threshold=200,
        min_players=80,
        max_results=10,
        show_extra_fields=False,
        debug_mode=True
    )
    
    plugin = SquadServerStatusCore(config)
    results = await plugin.handle_query(None)
    
    for result in results:
        print(result)
        print()

async def test_max_results():
    print("="*60)
    print("测试7: 最大返回条数设置为3")
    print("="*60)
    
    config = MockConfig(
        ping_threshold=200,
        min_players=60,
        max_results=3,
        show_extra_fields=False,
        debug_mode=True
    )
    
    plugin = SquadServerStatusCore(config)
    results = await plugin.handle_query(None)
    
    for result in results:
        print(result)
        print()

if __name__ == "__main__":
    print("\n" + "="*60)
    print("Squad服务器状态插件 - 测试验证")
    print("="*60 + "\n")
    
    asyncio.run(test_no_keyword())
    asyncio.run(test_with_keyword())
    asyncio.run(test_with_keyword_not_found())
    asyncio.run(test_with_extra_fields())
    asyncio.run(test_ping_threshold())
    asyncio.run(test_min_players())
    asyncio.run(test_max_results())
    
    print("="*60)
    print("所有测试完成")
    print("="*60)