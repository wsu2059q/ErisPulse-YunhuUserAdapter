class MessageTypes:
    TEXT = 1
    IMAGE = 2
    MARKDOWN = 3
    FILE = 4
    FORM = 5
    ARTICLE = 6
    STICKER = 7
    HTML = 8
    VIDEO = 10
    AUDIO = 11
    A2UI = 14


class ChatType:
    USER = 1
    PRIVATE = 1
    GROUP = 2
    BOT = 3


# 会话类型映射（OneBot12 detail_type -> 云湖 chat_type）
CHAT_TYPE_MAP = {
    "user": ChatType.USER,
    "private": ChatType.PRIVATE,
    "group": ChatType.GROUP,
    "bot": ChatType.BOT
}

# 内容类型映射（content_type -> 云湖 msg_type）
CONTENT_TYPE_MAP = {
    "text": MessageTypes.TEXT,
    "markdown": MessageTypes.MARKDOWN,
    "html": MessageTypes.HTML
}