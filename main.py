from typing import Any, AsyncGenerator
from astrbot.core import logger, AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Star, register
from astrbot.core.star import Context
from .analysis import analysis
from .froward_message import ForwardMessage

FILE_TYPE_MAP = {
    'folder': '📁 文件夹',
    'video': '🎥 视频',
    'image': '🖼️ 图片',
    'text': '📄 文本',
    'audio': '🎵 音频',
    'archive': '📦 压缩包',
    'document': '📑 文档',
    'unknown': '❓ 其他'
}

@register("Magnet Previewer", "cloudcranesss", "预览磁力链接", "1.0.0")
class MagnetPreviewer(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        logger.info("Magnet Previewer init")
        logger.info(f"AstrBot Version: {config.version}")
        self.config = config
        self.whatslink_url = self.config.get("WHATSLINK_URL", "")
        logger.info(f"WHATSLINK_URL: {self.whatslink_url}")



    @filter.regex(r"magnet:\?xt=urn:btih:[a-zA-Z0-9]{40}.*")
    async def handle_magnet(self, event: AstrMessageEvent) -> AsyncGenerator[Any, Any]:
        messages = event.get_messages()
        command = str(messages[0])
        link = command.split("&")[0]
        result = await analysis(link, self.whatslink_url)
        infos, screenshots = self._sort_infos(result)
        for msg in ForwardMessage(event, infos, screenshots).send_by_qq():
            yield msg


    def _sort_infos(self, info: dict) -> tuple[list[str], list[Any]]:
        base_info = [
            f"🔍 解析结果：\r"
            f"📝 名称：{info.get('name', '未知')}\r"
            f"📦 类型：{FILE_TYPE_MAP.get(info.get('type', 'unknown').lower(), '❓ 其他')}\r"
            f"📏 大小：{self._format_file_size(info.get('size', 0))}\r"
            f"📚 包含文件：{info.get('count', 0)}个"
        ]
        screenshots_data = info.get('screenshots', [])
        screenshots = [s["screenshot"] for s in screenshots_data[:5] if s]
        return base_info, screenshots

    def _format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if not size_bytes:
            return "0B"

        units = ["B", "KB", "MB", "GB", "TB"]
        unit_index = 0
        size = float(size_bytes)

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        return f"{size:.2f} {units[unit_index]}"