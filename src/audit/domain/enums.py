from enum import Enum


class RiskLevel(str, Enum):
    COMPLIANT = "合规"
    HINT = "提示"
    WARNING = "警告"
    VIOLATION = "违规"


class ViolationCategory(str, Enum):
    POLITICS = "涉政"
    TERROR = "暴恐"
    PORN = "色情"
    ABUSE = "辱骂"
    ILLEGAL_AD = "违法广告"
    FRAUD = "诈骗"
    TRAFFIC_DIVERSION = "引流"
    MINOR_SAFETY = "未成年人风险"
    VULGAR = "低俗"
    OTHER = "其他"


class PlatformAction(str, Enum):
    PASS = "pass"
    HINT = "hint"
    FOLD = "fold"
    DELETE = "delete"
    BLOCK = "block"
    MANUAL_REVIEW = "manual_review"
