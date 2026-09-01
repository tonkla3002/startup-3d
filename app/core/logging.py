"""Logging config พร้อม filter ปิดบังค่า sensitive ตาม STANDARDS section 8.3."""

import logging
import re

SENSITIVE_KEYS: tuple[str, ...] = (
    "app_secret",
    "partner_key",
    "access_token",
    "refresh_token",
    "sign",
    "code",
)

_REDACTED = "***REDACTED***"

_KEY_GROUP = r"(?P<key>" + "|".join(SENSITIVE_KEYS) + r")"
_SEP_GROUP = r"(?P<sep>\"?\s*[=:]\s*\"?)"
_VALUE_GROUP = r"(?P<value>[^\s,&\"'}]+)"

_PATTERN = re.compile(_KEY_GROUP + _SEP_GROUP + _VALUE_GROUP, re.IGNORECASE)


def redact(text: str) -> str:
    """แทนที่ค่า sensitive ใน string ด้วย placeholder.

    Args:
        text: ข้อความที่อาจมี secret ปนอยู่

    Returns:
        ข้อความที่ค่า sensitive ถูกแทนที่แล้ว
    """
    return _PATTERN.sub(lambda m: f"{m['key']}{m['sep']}{_REDACTED}", text)


class RedactSecretsFilter(logging.Filter):
    """Safety net กัน secret หลุดลง log แม้จะเผลอ log มาโดยตรง."""

    def filter(self, record: logging.LogRecord) -> bool:
        """ปิดบังค่า sensitive ใน log record เสมอ แล้วปล่อยผ่าน."""
        record.msg = redact(str(record.getMessage()))
        record.args = ()
        return True


def configure_logging(level: str = "INFO") -> None:
    """ตั้งค่า root logger พร้อมติด RedactSecretsFilter.

    Args:
        level: ระดับ log เช่น "INFO" หรือ "DEBUG"
    """
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s :: %(message)s")
    )
    handler.addFilter(RedactSecretsFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
