from typing import Optional, Any, Generator
import astrbot.api.message_components as comp
from astrbot.core.platform import AstrMessageEvent
from astrbot.core import logger


class ForwardMessage:
    def __init__(self, event: AstrMessageEvent, messages: list[str],
                 screenshots: Optional[list] = None) -> None:
        self.event = event
        self.platform = event.get_platform_name()
        logger.info("Forward message initialized",
                    extra={
                        "platform": self.platform,
                        "message_count": len(messages),
                        "screenshot_count": len(screenshots) if screenshots else 0
                    })
        self.self_id = event.get_self_id()
        self.messages = messages
        self.screenshots = screenshots or []  # 确保总是列表

    def send(self) -> Generator[Any, Any, None]:
        """发送转发消息(优化版)"""
        uin = self.self_id
        bot_name = "CloudCrane Bot"

        if self.platform == "aiocqhttp":
            # 使用列表推导式优化节点生成
            nodes = [
                comp.Node(
                    uin=uin,
                    name=bot_name,
                    content=[comp.Plain(str(msg) if msg is not None else "")]
                )
                for msg in self.messages
            ]

            # 添加截图节点
            nodes.extend(
                comp.Node(
                    uin=uin,
                    name=bot_name,
                    content=[comp.Image.fromURL(screenshot)]
                )
                for screenshot in self.screenshots[:9]  # 限制最大数量
                if screenshot  # 过滤空值
            )

            yield self.event.chain_result([comp.Nodes(nodes)])
        else:
            # 非aiocqhttp平台处理
            if self.messages:
                yield self.event.plain_result("\n".join(msg for msg in self.messages if msg))

            for screenshot in self.screenshots[:9]:  # 限制最大数量
                if screenshot:  # 过滤空值
                    yield self.event.image_result(screenshot)

        # 结构化日志记录
        if self.screenshots:
            logger.info("Screenshots forwarded",
                        extra={"uin": uin, "count": len(self.screenshots)})