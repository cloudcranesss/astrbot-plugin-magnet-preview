import random
import re
import aiohttp
from functools import lru_cache
from astrbot.api import logger
from tenacity import retry, stop_after_attempt, wait_exponential

# 预编译正则表达式提高性能
_MAGNET_PATTERN = re.compile(r"^magnet:\?xt=urn:btih:[\w\d]{40}.*")
_REFERER_OPTIONS = [
    "https://beta.magnet.pics/",
    "https://tmp.nulla.top/",
    "https://pics.magnetq.com/"
]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def analysis(link: str, url: str, session: aiohttp.ClientSession = None) -> dict | None:
    """分析磁力链接，支持传入现有session"""
    if not _validate_magnet(link):
        logger.error("Invalid magnet link", extra={"link": link})
        return None

    api_url = f"{url.rstrip('/')}/api/v1/link"
    referer_url = random.choice(_REFERER_OPTIONS)
    logger.info("API request sent", extra={"link": link})
    logger.debug("API request headers", extra={"referer": referer_url})
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": referer_url
    }
    params = {"url": link}

    try:
        use_external_session = session is not None
        current_session = session if use_external_session else aiohttp.ClientSession()

        async with current_session.get(api_url, headers=headers, params=params, ssl=False) as response:
            if response.status == 200:
                data = await response.json()
                if not _validate_api_response(data):
                    logger.error("Invalid API response", extra={"response": data})
                    return None
                logger.info("API response received", extra={"link": link})
                return data
            logger.error("API request failed",
                         extra={"status": response.status, "link": link})
    except aiohttp.ClientError as e:
        logger.error("Network request failed",
                     extra={"error": str(e), "link": link})
    finally:
        if not use_external_session and 'current_session' in locals():
            await current_session.close()
    return None


@lru_cache(maxsize=1024)
def _validate_magnet(magnet: str) -> bool:
    """验证磁力链接格式有效性(带缓存)"""
    return bool(_MAGNET_PATTERN.match(magnet))


def _validate_api_response(data: dict) -> bool:
    """验证API返回的数据结构是否有效"""
    return all(key in data for key in {"type", "file_type", "name", "size", "count", "screenshots"})