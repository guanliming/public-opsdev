import io
import secrets
import string
from typing import Optional

from captcha.image import ImageCaptcha


_CAPTCHA_LENGTH = 4
_CAPTCHA_CHARS = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


class CaptchaService:
    def __init__(self, length: int = _CAPTCHA_LENGTH, chars: str = _CAPTCHA_CHARS):
        self.length = length
        self.chars = chars
        self._image = ImageCaptcha(
            width=160,
            height=56,
            font_sizes=(38, 42, 46),
        )

    def generate(self) -> tuple[str, str, bytes]:
        text = "".join(secrets.choice(self.chars) for _ in range(self.length))
        token = secrets.token_urlsafe(24)
        image_bytes = self._image.generate(text)
        if hasattr(image_bytes, "getvalue"):
            data = image_bytes.getvalue()
        else:
            buf = io.BytesIO()
            buf.write(image_bytes)
            data = buf.getvalue()
        return token, text, data

    @staticmethod
    def normalize(code: str) -> str:
        return (code or "").strip().upper()


captcha_service = CaptchaService()
