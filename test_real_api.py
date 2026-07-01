import asyncio
import requests
import json

class MockConfig:
    def __init__(self, **kwargs):
        self._config = kwargs
    
    def get(self, key, default=None):
        return self._config.get(key, default)

class SquadServerStatusCore:
    def __init__(self, config):
        self.config = config
        self.api_sources = [
            "https://squadcalc.app/api/get/servers"
        ]
        self.cache = {}
        self.cache_time = 0

    def get_mock_servers(self):
        return []

    async def fetch_servers(self):
        for api_url in self.api_sources:
            try:
                headers = {"User-Agent": "AstrBot-Squad-Plugin/1.0"}
                response = await asyncio.to_thread(
                    requests.get, api_url, headers=headers, timeout=15
                )
                response.raise_for_status()
                data = response.json()

                if isinstance(data, dict):
                    servers = data.get("servers", data.get("data", []))
                elif isinstance(data, list):
                    servers = data
                else:
                    continue

                if servers and isinstance(servers, list) and len(servers) > 0:
                    normalized = []
                    for server in servers:
                        normalized_server = self.normalize_server_data(server)
                        if normalized_server:
                            normalized.append(normalized_server)
                    return normalized

            except Exception as e:
                print(f"API请求失败: {e}")
                continue

        return None

    def normalize_server_data(self, server):
        try:
            if isinstance(server, dict):
                data = server
            else:
                return None

            attributes = data.get("attributes", data)
            details = attributes.get("details", {})

            return {
                "name": str(attributes.get("name", data.get("name", ""))),
                "players": int(attributes.get("players", data.get("players", 0))),
                "max_players": int(attributes.get("maxPlayers", attributes.get("max_players", data.get("max_players", 0)))),
                "ping": int(attributes.get("ping", data.get("ping", 999))),
                "queue": int(details.get("squad_publicQueue", details.get("queue", attributes.get("queue", data.get("queue", 0))))),
                "status": str(attributes.get("status", data.get("status", "online"))).lower(),
                "map": str(details.get("map", attributes.get("map", data.get("map", "")))),
                "mode": str(details.get("gameMode", attributes.get("mode", data.get("mode", "")))),
                "version": str(details.get("version", attributes.get("version", data.get("version", "")))),
                "ip": str(attributes.get("ip", data.get("ip", ""))),
                "port": str(attributes.get("port", data.get("port", "")))
            }
        except Exception as e:
            print(f"标准化服务器数据失败: {e}")
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

                if ping >= ping_threshold and ping != 999:
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
        result += f"\n⏱️ Ping: {'未知' if ping >= 999 else f'{ping}ms'}"

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

        print(f"获取到 {len(servers)} 个服务器")

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

async def test_real_api():
    print("="*60)
    print("测试真实 API - 不带参数查询")
    print("="*60)
    
    config = MockConfig(
        ping_threshold=200,
        min_players=60,
        max_results=10,
        show_extra_fields=True,
        extra_fields=["map", "mode"]
    )
    
    plugin = SquadServerStatusCore(config)
    results = await plugin.handle_query(None)
    
    for result in results:
        print(result)
        print()

async def test_real_api_with_keyword():
    print("="*60)
    print("测试真实 API - 带关键字查询 'CN'")
    print("="*60)
    
    config = MockConfig(
        ping_threshold=200,
        min_players=0,
        max_results=10,
        show_extra_fields=True,
        extra_fields=["map", "mode"]
    )
    
    plugin = SquadServerStatusCore(config)
    results = await plugin.handle_query("CN")
    
    for result in results:
        print(result)
        print()

if __name__ == "__main__":
    print("\n" + "="*60)
    print("Squad服务器状态插件 - 真实API测试")
    print("="*60 + "\n")
    
    asyncio.run(test_real_api())
    asyncio.run(test_real_api_with_keyword())
    
    print("="*60)
    print("测试完成")
    print("="*60)