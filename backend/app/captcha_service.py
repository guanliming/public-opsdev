import io
import secrets
import string
from typing import Optional

from captcha.image import ImageCaptcha


_CAPTCHA_LENGTH = 4
_CAPTCHA_CHARS = string.digits + string.ascii_uppercase


class CaptchaService:
    def __init__(self, length: int = _CAPTCHA_LENGTH, chars: str = _CAPTCHA_CHARS):
        self.length = length
        self.chars = chars
        self._image = ImageCaptcha(width=140, height=48, font_sizes=(32, 36, 38))

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
