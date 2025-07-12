from typing import Optional, Any, Generator
import astrbot.api.message_components as comp
from astrbot.core.platform import AstrMessageEvent
from astrbot.core import logger


class ForwardMessage:
    def __init__(self, event: AstrMessageEvent, messages: list[str], screenshots: Optional[list] = None) -> None:
        self.event = event
        self.platform = self.event.get_platform_name()
        logger.info(f"{self.platform} forward message: {messages}")
        self.self_id = int(self.event.get_self_id())
        self.messages = messages
        self.screenshots = screenshots

    def send(self) -> Generator[Any, Any, None]:
        uin = self.self_id  # 预计算重复值
        bot_name = "CloudCrane Bot"
        nodes = []

        if self.platform == "aiocqhttp":
            for message in self.messages:
                # 处理消息
                text_content = str(message) if message is not None else ""
                nodes.append(
                    comp.Node(
                        uin=uin,
                        name=bot_name,
                        content=[comp.Plain(text_content)]
                    )
                )
            for screenshot in self.screenshots:
                nodes.append(
                    comp.Node(
                        uin=uin,
                        name=bot_name,
                        content=[comp.Image.fromURL(screenshot)]
                    )
                )
        else:
            message = "\r".join(self.messages)
            yield self.event.plain_result(f"{message}")
            for image in self.screenshots:
                yield self.event.image_result(image)
        # 记录日志（复用预存变量）
        if self.screenshots:
            logger.info(f"{uin} forward screenshots: {self.screenshots}")

        yield self.event.chain_result([comp.Nodes(nodes)])