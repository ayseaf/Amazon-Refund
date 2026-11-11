from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Challenge:
    kind: str
    message: str


def detect_challenge(html: str, url: str, status_code: int | None = None) -> Challenge | None:
    """Name a page that automation must not try to get around.

    MFA during sign-in is still reported. The sign-in wait leaves the window
    open so the person can type the code. A scan stops instead of continuing.
    """
    lowered_url = url.lower()
    text = " ".join(html.split()).lower()
    if status_code == 429 or "request was throttled" in text or "automated access to amazon" in text:
        return Challenge(
            "rate_limited",
            "Amazon showed a rate-limit page. The run stopped. Nothing was bypassed.",
        )
    if (
        "validatecaptcha" in lowered_url
        or "enter the characters you see" in text
        or "type the characters you see" in text
    ):
        return Challenge(
            "captcha",
            "Amazon showed a CAPTCHA. The run stopped and left it on screen. This app will not try to get around it.",
        )
    if "unusual activity" in text or "unusual sign-in" in text:
        return Challenge(
            "unusual_activity",
            "Amazon showed an unusual-activity page. The run stopped. Nothing was bypassed.",
        )
    if (
        "/ap/mfa" in lowered_url
        or "two-step verification" in text
        or "one-time password" in text
        or "enter otp" in text
    ):
        return Challenge(
            "mfa",
            "Amazon is asking for a verification code. This app does not read or enter it.",
        )
    if "/ap/signin" in lowered_url:
        return Challenge(
            "sign_in_required",
            "Amazon is showing the sign-in page. This app does not type a password.",
        )
    return None
