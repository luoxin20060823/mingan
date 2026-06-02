from __future__ import annotations

from ..domain.enums import ViolationCategory


CATEGORY_KEYWORDS: list[tuple[ViolationCategory, tuple[str, ...]]] = [
    (
        ViolationCategory.MINOR_SAFETY,
        ("未成年", "未滿", "未满", "幼女", "幼齿", "萝莉", "学生妹", "童模", "儿童色情", "恋童"),
    ),
    (
        ViolationCategory.FRAUD,
        ("诈骗", "刷单", "杀猪盘", "资金盘", "跑分", "套现", "洗钱", "博彩", "稳赚", "包赔", "返利"),
    ),
    (
        ViolationCategory.TRAFFIC_DIVERSION,
        ("加微信", "加薇", "加v", "加V", "私聊", "进群", "QQ群", "qq群", "联系方式", "VX", "vx"),
    ),
    (
        ViolationCategory.VULGAR,
        ("低俗", "裸聊", "约炮", "擦边", "福利视频", "成人直播"),
    ),
]


def normalize_category(word: str, category: str) -> str:
    text = word.casefold()
    for target, keywords in CATEGORY_KEYWORDS:
        if any(keyword.casefold() in text for keyword in keywords):
            return target.value
    return category
