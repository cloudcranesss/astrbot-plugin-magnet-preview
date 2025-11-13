import random
import re
import aiohttp
import asyncio
from functools import lru_cache
from astrbot.api import logger
from tenacity import retry, stop_after_attempt, wait_exponential

# 预编译正则表达式提高性能
_MAGNET_PATTERN = re.compile(r"^magnet:\?xt=urn:btih:[a-zA-Z0-9]{40}.*")
_REFERER_OPTIONS = [
    "https://whatslink.smartapi.com.cn/",
    "https://whatslink.info/",
    "https://www.google.com/",
    "https://github.com/"
]

# API端点列表，按优先级排序
_API_ENDPOINTS = [
    "https://whatslink.smartapi.com.cn",
    "https://whatslink.info", 
    "https://api-whatslink-zone-3e6ueqpmjotd-1366542076.eo-edgefunctions1.com"
]

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def analysis(link: str, url: str, session: aiohttp.ClientSession = None) -> dict | None:
    """分析磁力链接，支持传入现有session"""
    if not _validate_magnet(link):
        logger.error("无效的磁力链接格式", extra={"link": link})
        return None

    # 检查URL配置是否有效
    if not url:
        logger.error("API URL未配置", extra={"link": link})
        return None

    api_url = f"{url.rstrip('/')}/api/v1/link"
    referer_url = random.choice(_REFERER_OPTIONS)
    
    logger.info(f"API请求发送: {link}")
    logger.info(f"API URL: {api_url}")
    logger.info(f"API请求头Referer: {referer_url}")
    
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": referer_url
    }
    params = {"url": link}

    try:
        use_external_session = session is not None
        current_session = session if use_external_session else aiohttp.ClientSession()

        async with current_session.get(api_url, headers=headers, params=params, ssl=False, timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status == 200:
                data = await response.json()
                if not _validate_api_response(data):
                    logger.error("API返回无效数据", extra={"response": data})
                    return None
                logger.info("API响应接收成功", extra={"link": link})
                return data
            else:
                logger.error("API请求失败",
                           extra={"status": response.status, "link": link, "api_url": api_url})
                return None
    except aiohttp.ClientError as e:
        logger.error("网络请求失败",
                   extra={"error": str(e), "link": link, "api_url": api_url})
    except asyncio.TimeoutError:
        logger.error("API请求超时",
                   extra={"link": link, "api_url": api_url})
    except Exception as e:
        logger.error("API请求发生未知错误",
                   extra={"error": str(e), "link": link, "api_url": api_url})
    finally:
        if not use_external_session and 'current_session' in locals():
            await current_session.close()
    return None

# 新增：多端点重试机制
async def analysis_with_fallback(link: str, session: aiohttp.ClientSession = None) -> dict | None:
    """使用多端点重试机制分析磁力链接"""
    if not _validate_magnet(link):
        logger.error("无效的磁力链接格式", extra={"link": link})
        return None

    logger.info(f"开始多端点重试解析: {link}")
    
    # 尝试所有可用的API端点
    for endpoint in _API_ENDPOINTS:
        logger.info(f"尝试端点: {endpoint}")
        result = await analysis(link, endpoint, session)
        if result is not None:
            logger.info(f"端点 {endpoint} 解析成功")
            return result
        else:
            logger.warning(f"端点 {endpoint} 解析失败，尝试下一个端点")
    
    logger.error("所有API端点都不可用")
    return None

@lru_cache(maxsize=1024)
def _validate_magnet(magnet: str) -> bool:
    """验证磁力链接格式有效性(带缓存)"""
    return bool(_MAGNET_PATTERN.match(magnet))

def _validate_api_response(data: dict) -> bool:
    """验证API返回的数据结构是否有效"""
    return all(key in data for key in {"type", "file_type", "name", "size", "count", "screenshots"})