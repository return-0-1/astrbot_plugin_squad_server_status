"""AstrBot 运行时依赖的测试替身

让测试脚本可以在没有安装 AstrBot 的环境下导入并实例化插件本体(main.py)。
仅用于测试，不会被打包进插件功能。
"""

import importlib
import sys
import types
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent

DEFAULT_CONFIG = {
    "ping_threshold": 200,
    "min_players": 60,
    "max_results": 10,
    "show_extra_fields": False,
    "extra_fields": ["map", "mode"],
    "debug_mode": False,
    "fallback_to_mock": True,
    "cn_only": True,
}


def _install_astrbot_stub():
    """注入最小可用的 astrbot 模块替身"""
    if "astrbot" in sys.modules:
        return

    astrbot = types.ModuleType("astrbot")
    api = types.ModuleType("astrbot.api")
    api.logger = types.SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )

    class AstrBotConfig(dict):
        """模拟 AstrBot 配置对象(dict + get)"""

    api.AstrBotConfig = AstrBotConfig

    star_mod = types.ModuleType("astrbot.api.star")

    class Star:
        def __init__(self, context):
            self.context = context

    star_mod.Star = Star
    star_mod.Context = object

    event_mod = types.ModuleType("astrbot.api.event")

    class AstrMessageEvent:
        pass

    class _Filter:
        def llm_tool(self, *args, **kwargs):
            return lambda fn: fn

        def command(self, *args, **kwargs):
            return lambda fn: fn

    event_mod.filter = _Filter()
    event_mod.AstrMessageEvent = AstrMessageEvent

    astrbot.api = api
    sys.modules["astrbot"] = astrbot
    sys.modules["astrbot.api"] = api
    sys.modules["astrbot.api.star"] = star_mod
    sys.modules["astrbot.api.event"] = event_mod


def load_plugin():
    """导入插件本体

    Returns:
        module: main.py 模块对象
    """
    _install_astrbot_stub()
    if str(PLUGIN_DIR) not in sys.path:
        sys.path.insert(0, str(PLUGIN_DIR))
    return importlib.import_module("main")


def make_plugin(**overrides):
    """实例化插件(走真实 __init__)

    Args:
        **overrides: 覆盖默认配置的配置项

    Returns:
        tuple: (插件实例, main.py 模块对象)
    """
    module = load_plugin()
    config = dict(DEFAULT_CONFIG)
    config.update(overrides)
    plugin = module.SquadServerStatusPlugin(
        context=None, config=module.AstrBotConfig(config)
    )
    return plugin, module
