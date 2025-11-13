
---

# 🧲 Magnet Preview 磁力链接预览工具

一个基于 [whatslink](https://whatslink.info) API 实现的磁力链接预览工具，支持解析磁力链接内容并展示文件信息。

## ✨ 功能特性

- 自动解析磁力链接内容
- 显示文件类型、大小、数量等关键信息
- 支持预览截图展示
- 使用Redis缓存解析结果
- 响应式设计，适配多种平台

## 🚀 使用方法

直接发送磁力链接即可自动解析，例如：

```
magnet:?xt=urn:btih:A736FE3DE765B2601A52C6ACC166F75A5EE9B0A6&dn=SSNI730
```

## ⚙️ 配置说明

| 配置项                     | 类型   | 必填 | 默认值    | 说明                                                                 |
| -------------------------- | ------ | ---- | --------- | -------------------------------------------------------------------- |
| `IMAGE_DOMAIN_REPLACEMENT` | string | 否   | -         | **推荐** 图片域名替换地址，用于替换whatslink.info域名，优先使用此配置 |
| `WHATSLINK_URL`            | string | 否   | -         | **向后兼容** whatslink.info 代理地址（将被IMAGE_DOMAIN_REPLACEMENT替代） |
| `MAX_IMAGES`               | int    | 否   | 1         | 最大返回图片数（1-5）                                                |
| `REDIS_HOST`               | string | 是   | 127.0.0.1 | Redis数据库地址                                                      |
| `REDIS_PORT`               | int    | 是   | 6379      | Redis数据库端口                                                      |
| `REDIS_DB`                 | int    | 否   | 0         | Redis数据库索引                                                      |
| `REDIS_PASSWORD`           | string | 否   | -         | Redis数据库密码                                                      |

### 配置优先级说明

1. **优先使用** `IMAGE_DOMAIN_REPLACEMENT` 配置
2. **向后兼容** 如果未设置新配置，则使用 `WHATSLINK_URL`
3. **推荐迁移** 建议新部署使用 `IMAGE_DOMAIN_REPLACEMENT`，现有部署可逐步迁移

## 📸 效果展示

### 解析结果示例

![](https://netdisc.smartapi.com.cn/d/BQACAgUAAxkBAAM4aHHUNyfMQW_sS3BB37f_hbCmPLoAAoQWAAJbQJBXtvY577PmJUw2BA)

### 多图预览效果

![](https://netdisc.smartapi.com.cn/d/BQACAgUAAxkBAAM7aHHUn894WtSmA5PS7KI5J0HeQNYAAoUWAAJbQJBXetbR7lKQB5g2BA)

## 🔧 部署建议

1. 确保已安装并运行Redis服务
2. 为whatslink.info搭建反向代理
3. 根据需求调整`MAX_IMAGES`参数
4. 生产环境建议配置Redis密码

## 📝 注意事项

- 大陆用户需自行搭建whatslink反向代理
- 图片数量设置过多可能导致消息过长
- Redis密码建议在生产环境中配置