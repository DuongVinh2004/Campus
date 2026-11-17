"""Alert channels: Telegram and e-mail. Both refuse any host that is not on the allow-list, never put a secret in a log line, and
use short timeouts so a dead channel cannot hold up the alert loop.

Configuration comes from the environment (a file with mode 0600 on the server), never from the command line:
  CAMPUS247_ALERT_TELEGRAM_TOKEN_FILE   file holding the bot token
  CAMPUS247_ALERT_TELEGRAM_CHAT_ID      chat or channel id that receives the messages
  CAMPUS247_ALERT_SMTP_HOST / _PORT     mail server (TLS is required; port 465 is implicit TLS, anything else uses STARTTLS)
  CAMPUS247_ALERT_SMTP_USER / _PASSWORD_FILE / _FROM / _TO    login, the file holding the password, sender, comma-separated recipients
  CAMPUS247_ALERT_ALLOWED_HOSTS         extra hosts allowed besides api.telegram.org and the SMTP host
"""
from __future__ import annotations

import smtplib
import ssl
from collections.abc import Mapping
from email.message import EmailMessage
from pathlib import Path

import httpx

from campus247.observability.alerts import AlertMessage, CompositeNotifier, LogNotifier, Notifier

TELEGRAM_HOST = "api.telegram.org"
TIMEOUT_S = 5.0


class ChannelRefused(Exception):
    pass


def _secret(path: str) -> str:
    value = Path(path).read_text(encoding="utf-8").strip()
    if not value:
        raise ChannelRefused("secret file is empty")
    return value


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, *, allowed_hosts: frozenset[str], client: httpx.Client | None = None) -> None:
        if TELEGRAM_HOST not in allowed_hosts:
            raise ChannelRefused("api.telegram.org is not on the allow-list")
        self._url, self._chat_id = f"https://{TELEGRAM_HOST}/bot{token}/sendMessage", chat_id
        self._client = client or httpx.Client(timeout=TIMEOUT_S, trust_env=False)

    def send(self, message: AlertMessage) -> None:
        for attempt in (1, 2):
            try:
                response = self._client.post(self._url, json={"chat_id": self._chat_id, "text": message.text(), "disable_web_page_preview": True})
            except httpx.HTTPError as error:
                if attempt == 2:
                    raise RuntimeError(f"telegram unreachable ({type(error).__name__})") from None  # the URL holds the token: not chained
                continue
            if response.status_code == 200:
                return
            if attempt == 2 or response.status_code < 500:
                raise RuntimeError(f"telegram answered {response.status_code}")


class SmtpNotifier:
    def __init__(self, host: str, port: int, sender: str, recipients: list[str], *, user: str | None, password: str | None,
                 allowed_hosts: frozenset[str], smtp_factory=None) -> None:
        if host not in allowed_hosts:
            raise ChannelRefused("the SMTP host is not on the allow-list")
        if not recipients:
            raise ChannelRefused("no recipients")
        self._host, self._port, self._sender, self._recipients = host, port, sender, recipients
        self._user, self._password = user, password
        self._factory = smtp_factory

    def send(self, message: AlertMessage) -> None:
        mail = EmailMessage()
        mail["Subject"] = message.text()[:200]
        mail["From"], mail["To"] = self._sender, ", ".join(self._recipients)
        mail.set_content(message.text())
        context = ssl.create_default_context()
        if self._factory is not None:
            connection = self._factory(self._host, self._port, context)
        elif self._port == 465:
            connection = smtplib.SMTP_SSL(self._host, self._port, timeout=TIMEOUT_S * 2, context=context)
        else:
            connection = smtplib.SMTP(self._host, self._port, timeout=TIMEOUT_S * 2)
            connection.starttls(context=context)  # never send a login or a message in clear text
        with connection:
            if self._user and self._password:
                connection.login(self._user, self._password)
            connection.send_message(mail)


def build_notifier(environ: Mapping[str, str]) -> Notifier:
    """The log channel always, plus every channel that is fully configured. A half-configured channel is skipped with a log line."""
    import logging
    log = logging.getLogger("campus247.alerts")
    extra = {host.strip() for host in environ.get("CAMPUS247_ALERT_ALLOWED_HOSTS", "").split(",") if host.strip()}
    channels: list[Notifier] = [LogNotifier()]
    token_file, chat_id = environ.get("CAMPUS247_ALERT_TELEGRAM_TOKEN_FILE"), environ.get("CAMPUS247_ALERT_TELEGRAM_CHAT_ID")
    if token_file and chat_id:
        try:
            channels.append(TelegramNotifier(_secret(token_file), chat_id, allowed_hosts=frozenset(extra | {TELEGRAM_HOST})))
        except (ChannelRefused, OSError) as error:
            log.warning("alert_channel_skipped channel=telegram kind=%s", type(error).__name__)
    host = environ.get("CAMPUS247_ALERT_SMTP_HOST")
    if host and environ.get("CAMPUS247_ALERT_SMTP_TO") and environ.get("CAMPUS247_ALERT_SMTP_FROM"):
        try:
            password_file = environ.get("CAMPUS247_ALERT_SMTP_PASSWORD_FILE")
            channels.append(SmtpNotifier(
                host, int(environ.get("CAMPUS247_ALERT_SMTP_PORT", "465")), environ["CAMPUS247_ALERT_SMTP_FROM"],
                [item.strip() for item in environ["CAMPUS247_ALERT_SMTP_TO"].split(",") if item.strip()],
                user=environ.get("CAMPUS247_ALERT_SMTP_USER"), password=_secret(password_file) if password_file else None,
                allowed_hosts=frozenset(extra | {host})))
        except (ChannelRefused, OSError, ValueError) as error:
            log.warning("alert_channel_skipped channel=smtp kind=%s", type(error).__name__)
    return channels[0] if len(channels) == 1 else CompositeNotifier(channels)
