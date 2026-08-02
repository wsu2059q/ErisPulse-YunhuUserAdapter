<div align="center">

<img src=".github/assets/ErisPulseLogo.png" width="180" alt="ErisPulse YunhuUserAdapter" />

# ErisPulse YunhuUserAdapter

**云湖用户账户驱动适配器 —— 用个人账户驱动 Bot。**

基于云湖用户账户协议实现的 ErisPulse 适配器，支持多账户、WebSocket 长连接与自动重连，提供文本 / 图片 / 视频 / 文件 / 语音 / Markdown / HTML / A2UI 等完整消息收发能力。

<p>
  <a href="https://pypi.org/project/ErisPulse-YunhuUserAdapter/"><img src="https://img.shields.io/pypi/v/ErisPulse-YunhuUserAdapter?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://pypi.org/project/ErisPulse-YunhuUserAdapter/"><img src="https://img.shields.io/badge/Python-3.10+-FFD43B?style=for-the-badge&logo=python&logoColor=blue" alt="Python"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License"></a>
  <a href="https://github.com/ErisPulse/ErisPulse-YunhuUserAdapter"><img src="https://img.shields.io/github/stars/ErisPulse/ErisPulse-YunhuUserAdapter?style=for-the-badge&logo=github&color=brightgreen" alt="Stars"></a>
  <a href="https://pepy.tech/project/ErisPulse-YunhuUserAdapter"><img src="https://img.shields.io/pepy/dt/ErisPulse-YunhuUserAdapter?style=for-the-badge&color=blue" alt="Downloads"></a>
  <a href="https://github.com/ErisPulse/ErisPulse"><img src="https://img.shields.io/badge/Powered_by-ErisPulse-FF6B9D?style=for-the-badge&logo=bookstack&logoColor=white" alt="ErisPulse"></a>
</p>

</div>

---

## 安装

```bash
pip install ErisPulse-YunhuUserAdapter
```

## 使用方法

### 基础使用

```python
from ErisPulse.Core import adapter

# 获取适配器实例
yunhu = adapter.get("yunhu_user")

# 发送文本消息
await yunhu.Send.To("user", "user_id").Text("Hello World!")

# 发送到群聊
await yunhu.Send.To("group", "group_id").Text("群消息")

# 发送图片
await yunhu.Send.To("group", "group_id").Image("https://example.com/image.jpg")
```

### 多账户使用

```python
from ErisPulse.Core import adapter

yunhu = adapter.get("yunhu_user")

# 使用指定账户发送消息
await yunhu.Send.Using("default").To("group", "group_id").Text("来自默认账户的消息")

# 使用第二个账户发送消息
await yunhu.Send.Using("account2").To("user", "user_id").Text("来自账户2的消息")

# 或者使用 Account 方法（与 Using 等效）
await yunhu.Send.Account("account2").To("group", "group_id").Text("消息内容")
```

### 链式修饰

```python
# 回复消息
await yunhu.Send.To("group", "group_id").Reply("message_id").Text("回复内容")

await yunhu.Send.To("group", "group_id").Reply("message_id").At("user_id").Text("@用户并回复")

# 因为用户账户较为特殊，即便你不是管理员，也可以@全体 故这里只会发送一个艾特全体的文本
# 这是一个伪@全体
await yunhu.Send.To("group", "group_id").Reply("message_id").AtAll().Text("@全体并回复")

# 添加按钮
buttons = [
    [
        {"text": "确认", "actionType": 3, "value": "confirm"},
        {"text": "取消", "actionType": 3, "value": "cancel"}
    ]
]
await yunhu.Send.To("group", "group_id").Buttons(buttons).Text("请选择")

# 组合使用
await yunhu.Send.Using("default").To("group", "group_id").Reply("msg_id").Buttons(buttons).Text("回复消息")
```

### 消息类型

```python
# 文本消息
await yunhu.Send.To("user", "user_id").Text("纯文本消息")

# Markdown 消息
await yunhu.Send.To("group", "group_id").Markdown("**粗体** 和 *斜体*")

# HTML 消息
await yunhu.Send.To("group", "group_id").Html("<b>加粗</b> 和 <i>斜体</i>")

# A2UI 消息
await yunhu.Send.To("group", "group_id").A2ui({"type": "card", "content": "..."})

# 编辑消息
await yunhu.Send.To("group", "group_id").Edit("message_id", "新内容")

# 编辑消息（指定内容类型）
await yunhu.Send.To("group", "group_id").Edit("message_id", "新内容", content_type="markdown")

# 撤回消息
await yunhu.Send.To("group", "group_id").Recall("message_id")

# 以下媒体消息均支持URL和二进制传入

# 图片消息（URL）
await yunhu.Send.To("group", "group_id").Image("https://example.com/image.jpg")

# 视频消息
await yunhu.Send.To("group", "group_id").Video("https://example.com/video.mp4")

# 文件消息
await yunhu.Send.To("group", "group_id").File("https://example.com/document.pdf")

# 语音消息
await yunhu.Send.To("group", "group_id").Audio("https://example.com/audio.mp3")

# 表情消息（URL 或 表情ID 或 二进制数据）
await yunhu.Send.To("group", "group_id").Face("https://example.com/sticker.png")
```

### OneBot12 原始消息

```python
# 发送 OneBot12 格式消息段
ob12_message = [
    {"type": "text", "data": {"text": "Hello"}},
    {"type": "image", "data": {"file_id": "image_id"}}
]
await yunhu.Send.To("group", "group_id").Raw_ob12(ob12_message)
```

## 配置

在 `config.toml` 中配置：

```toml
[YunhuUserAdapter]
ws_reconnect_interval = 30
ws_timeout = 70

[YunhuUserAdapter.accounts.default]
email = "your_email@example.com"
password = "your_password"
platform = "windows"
device_id = ""
enabled = true
```

### 配置说明

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `ws_reconnect_interval` | int | 30 | WebSocket 重连间隔（秒） |
| `ws_timeout` | int | 70 | WebSocket 超时时间（秒） |
| `accounts.<name>.email` | str | - | 登录邮箱 |
| `accounts.<name>.password` | str | - | 登录密码 |
| `accounts.<name>.platform` | str | "windows" | 登录平台 |
| `accounts.<name>.device_id` | str | "" | 设备ID（留空自动生成） |
| `accounts.<name>.enabled` | bool | true | 是否启用 |

## 事件监听

```python
from ErisPulse.Core.Event import message, command, notice

# 消息事件
@message.on_message()
async def message_handler(event):
    if event["platform"] == "yunhu_user":
        await event.reply("Echo: " + event.get_alt_message())

# 命令处理
@command("hello", help="发送问候")
async def hello_command(event):
    await event.reply("你好！我是云湖用户机器人。")
```

## 事件格式

### 消息事件

```python
{
    "id": "event_id",
    "time": 1234567890,
    "type": "message",
    "detail_type": "group",  # 或 "private"
    "platform": "yunhu_user",
    "self": {
        "platform": "yunhu_user",
        "user_id": "your_user_id"
    },
    "message": [
        {"type": "text", "data": {"text": "消息内容"}}
    ],
    "alt_message": "消息内容",
    "user_id": "sender_user_id",
    "user_nickname": "发送者昵称",
    "group_id": "group_id",   # 群消息时包含
    "yunhu_user_raw": {...},  # 原始事件数据
    "yunhu_user_raw_type": "push_message"  # 原始事件类型
}
```

### 平台特有字段

所有云湖用户特有字段都以 `yunhu_user_` 前缀标识：

- `yunhu_user_raw`: 原始事件数据（包含完整的云湖协议数据）
- `yunhu_user_raw_type`: 原始事件类型（如 `push_message`、`edit_message` 等）

## API 响应格式

适配器的 `call_api` 方法返回符合 OneBot12 的响应格式：

```python
{
    "status": "ok",  # 或 "failed"
    "retcode": 0,  # 0 表示成功，其他为错误码
    "data": {...},  # 响应数据
    "message_id": "message_id",  # 消息ID
    "message": "",  # 错误信息（成功时为空）
    "yunhu_user_raw": {...}  # 原始响应数据
}
```

## 事件处理范围

适配器支持了以下云湖 WebSocket 事件：

| 原始事件类型 | OneBot12 类型 | 说明 |
|-------------|--------------|------|
| `push_message` | `message` | 推送消息（包括私聊、群聊）|
| `edit_message` | `notice` | 消息编辑事件 |
| `file_send_message` | `notice` | 超级文件分享事件 |
| `bot_board_message` | `notice` | 机器人公告设置事件 |

其他事件类型（如 `heartbeat_ack`、`draft_input` 等）会被忽略。

## OneBot12 支持的 detail_type

适配器将云湖消息转换为以下 OneBot12 类型：

| OneBot12 detail_type | 云湖 chat_type | 说明 |
|-------------------|---------------|------|
| `private` | 1 | 私聊消息 |
| `group` | 2 | 群聊消息 |
| `bot` | 3 | 机器人消息 |

## 开发状态

- [x] 基础适配器结构
- [x] 多账户支持（AccountConfigClass 声明式配置）
- [x] WebSocket 连接和消息接收（使用 sdk.client.ws_connect）
- [x] 自动重连机制
- [x] 事件转换（OneBot12 格式）
- [x] 消息发送（文本、图片、视频、文件、语音、Markdown、HTML、A2UI、表情）
- [x] 链式修饰（Reply、Buttons、At、AtAll）
- [x] 消息管理（Edit、Recall）
- [x] 用户邮箱登录
- [x] Raw_ob12 原始消息发送
- [x] sdk.client 统一 HTTP 客户端（移除直接 aiohttp 依赖）
- [x] sdk.client.ws_connect 统一 WebSocket 客户端（移除直接 websockets 依赖）

## 致谢

- [yhchatAPI](https://github.com/yh-Tpdev/yhchatAPI)
- [yh_user_sdk](https://github.com/yyyytawa-org/yh_user_sdk)

## 相关链接

- [ErisPulse](https://github.com/ErisPulse/ErisPulse)
- [ErisPulse-YunhuAdapter](https://github.com/ErisPulse/ErisPulse-YunhuAdapter)
