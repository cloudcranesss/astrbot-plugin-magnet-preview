import re
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
        self.max_screenshots = self.config.get("MAX_IMAGES", 1)
        logger.info(f"WHATSLINK_URL: {self.whatslink_url}")

    async def terminate(self):
        """可选择实现 terminate 函数，当插件被卸载/停用时会调用。"""
        logger.info("Magnet Previewer terminate")
        await super().terminate()

    @filter.event_message_type(filter.EventMessageType.ALL)
    @filter.regex(r"magnet:\?xt=urn:btih:[a-zA-Z0-9]{40}.*")
    async def handle_magnet(self, event: AstrMessageEvent) -> AsyncGenerator[Any, Any]:
        messages = event.get_messages()
        plain = str(messages[0])
        command = re.findall(r"text='(.*?)'", plain)[0]
        link = command.split("&")[0]

        result = await analysis(link, self.whatslink_url)

        if not result or result.get('error'):
            error_msg = result.get('name', '解析磁力链接失败') if result else 'API无响应'
            logger.error(f"API错误: {error_msg}")
            yield event.plain_result(f"⚠️ 解析失败: {error_msg.split('contact')[0]}")
            return

        if not result:  # 关键修复：处理空响应
            yield event.plain_result("解析磁力链接失败，请检查链接格式或重试")
            return

        infos, screenshots = self._sort_infos(result)
        for msg in ForwardMessage(event, infos, screenshots).send():
            yield msg



    def _sort_infos(self, info: dict) -> tuple[list[str], list[Any]]:
        # 使用更安全的字段获取方式
        base_info = [
            f"🔍 解析结果：\r"
            f"📝 名称：{info.get('name', '未知')}\r"
            f"📦 类型：{FILE_TYPE_MAP.get(info.get('file_type', 'unknown').lower(), FILE_TYPE_MAP['unknown'])}\r"
            f"📏 大小：{self._format_file_size(info.get('size', 0))}\r"
            f"📚 包含文件：{info.get('count', 0)}个"
        ]
        # Handle screenshots
        screenshots_data = info.get('screenshots')
        if screenshots_data is None:
            screenshots_data = []
        elif not isinstance(screenshots_data, list):
            screenshots_data = []

        # Now take up to self.max_screenshots
        screenshots = []
        for s in screenshots_data[:self.max_screenshots]:
            # Only process if s is a non-null dictionary
            if isinstance(s, dict):
                url = s.get('screenshot')
                if url:  # if url is not empty string and not None
                    screenshots.append(url)

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

    # 替换图片中的域名
    def replace_image_url(self, image_url: str) -> str:
        return image_url.replace("https://whatslink.info", self.whatslink_url)