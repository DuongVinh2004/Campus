import json
import logging
from datetime import UTC, datetime

import httpx
import pytest
from campus247.observability.alert_notifiers import ChannelRefused, SmtpNotifier, TelegramNotifier, build_notifier
from campus247.observability.alerts import AlertMessage, CompositeNotifier, LogNotifier
from campus247.observability.alert_rules import Severity

MESSAGE = AlertMessage("model_down", "firing", Severity.CRITICAL, "Model ngừng", "reranker không trả lời", datetime(2026, 11, 17, 3, 42, tzinfo=UTC))
TOKEN = "123456:SECRET-TOKEN-VALUE"


def telegram(handler, **kwargs):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return TelegramNotifier(TOKEN, "-1001", allowed_hosts=frozenset({"api.telegram.org"}), client=client, **kwargs)


class TestTelegram:
    def test_posts_the_message_text_to_the_bot_api(self):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={"ok": True})

        telegram(handler).send(MESSAGE)
        (request,) = seen
        assert request.url.host == "api.telegram.org" and request.url.path == f"/bot{TOKEN}/sendMessage"
        body = json.loads(request.content)
        assert body["text"] == "[CRITICAL] Campus 24/7 · Model ngừng · reranker không trả lời · 10:42 17/11"
        assert body["chat_id"] == "-1001" and body["disable_web_page_preview"] is True

    def test_a_server_error_is_retried_once_then_reported_without_the_token(self):
        calls = []

        def handler(request):
            calls.append(1)
            return httpx.Response(502)

        with pytest.raises(RuntimeError) as failure:
            telegram(handler).send(MESSAGE)
        assert len(calls) == 2 and "502" in str(failure.value) and TOKEN not in str(failure.value)

    def test_a_client_error_is_not_retried(self):
        calls = []

        def handler(request):
            calls.append(1)
            return httpx.Response(401, json={"ok": False})

        with pytest.raises(RuntimeError, match="401"):
            telegram(handler).send(MESSAGE)
        assert len(calls) == 1

    def test_a_network_failure_never_carries_the_url_that_holds_the_token(self):
        def handler(request):
            raise httpx.ConnectError("refused", request=request)

        with pytest.raises(RuntimeError) as failure:
            telegram(handler).send(MESSAGE)
        assert TOKEN not in str(failure.value) and failure.value.__cause__ is None and "ConnectError" in str(failure.value)

    def test_succeeds_on_the_second_try(self):
        answers = iter([httpx.Response(503), httpx.Response(200, json={"ok": True})])
        telegram(lambda request: next(answers)).send(MESSAGE)

    def test_refuses_to_start_when_the_host_is_not_allowed(self):
        with pytest.raises(ChannelRefused):
            TelegramNotifier(TOKEN, "-1001", allowed_hosts=frozenset({"example.org"}))


class FakeSmtp:
    def __init__(self):
        self.log = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        self.log.append(("login", user, password))

    def send_message(self, mail):
        self.log.append(("send", mail["Subject"], mail["To"], mail.get_content()))


class TestSmtp:
    def make(self, fake, **over):
        args = dict(host="smtp.example.net", port=465, sender="alerts@example.net", recipients=["a@example.net", "b@example.net"], user="u", password="pw",
                    allowed_hosts=frozenset({"smtp.example.net"}), smtp_factory=lambda host, port, context: fake) | over
        return SmtpNotifier(args.pop("host"), args.pop("port"), args.pop("sender"), args.pop("recipients"), **args)

    def test_logs_in_and_sends_to_every_recipient(self):
        fake = FakeSmtp()
        self.make(fake).send(MESSAGE)
        assert fake.log[0] == ("login", "u", "pw")
        kind, subject, to, content = fake.log[1]
        assert subject.startswith("[CRITICAL] Campus 24/7") and to == "a@example.net, b@example.net" and "Model ngừng" in content

    def test_no_login_when_no_user_is_configured(self):
        fake = FakeSmtp()
        self.make(fake, user=None, password=None).send(MESSAGE)
        assert [entry[0] for entry in fake.log] == ["send"]

    def test_refuses_an_unlisted_host_and_an_empty_recipient_list(self):
        with pytest.raises(ChannelRefused):
            self.make(FakeSmtp(), allowed_hosts=frozenset({"other.example.net"}))
        with pytest.raises(ChannelRefused):
            self.make(FakeSmtp(), recipients=[])


class TestBuildNotifier:
    def test_only_the_log_channel_when_nothing_is_configured(self):
        assert isinstance(build_notifier({}), LogNotifier)

    def test_configured_channels_are_added(self, tmp_path):
        token, password = tmp_path / "token", tmp_path / "smtp-pw"
        token.write_text(TOKEN + "\n", encoding="utf-8")
        password.write_text("pw\n", encoding="utf-8")
        env = {"CAMPUS247_ALERT_TELEGRAM_TOKEN_FILE": str(token), "CAMPUS247_ALERT_TELEGRAM_CHAT_ID": "-1001",
               "CAMPUS247_ALERT_SMTP_HOST": "smtp.example.net", "CAMPUS247_ALERT_SMTP_TO": "a@example.net, b@example.net",
               "CAMPUS247_ALERT_SMTP_FROM": "alerts@example.net", "CAMPUS247_ALERT_SMTP_PASSWORD_FILE": str(password), "CAMPUS247_ALERT_SMTP_USER": "u"}
        notifier = build_notifier(env)
        assert isinstance(notifier, CompositeNotifier)
        assert [type(n).__name__ for n in notifier._notifiers] == ["LogNotifier", "TelegramNotifier", "SmtpNotifier"]

    def test_a_half_configured_or_unreadable_channel_is_skipped_with_a_log_line_and_no_secret(self, tmp_path, caplog):
        env = {"CAMPUS247_ALERT_TELEGRAM_TOKEN_FILE": str(tmp_path / "missing"), "CAMPUS247_ALERT_TELEGRAM_CHAT_ID": "-1001",
               "CAMPUS247_ALERT_SMTP_HOST": "smtp.example.net"}  # no recipients or sender
        with caplog.at_level(logging.WARNING, logger="campus247.alerts"):
            notifier = build_notifier(env)
        assert isinstance(notifier, LogNotifier)
        assert "alert_channel_skipped channel=telegram" in caplog.text and str(tmp_path) not in caplog.text

    def test_an_empty_secret_file_is_refused(self, tmp_path):
        token = tmp_path / "token"
        token.write_text("  \n", encoding="utf-8")
        assert isinstance(build_notifier({"CAMPUS247_ALERT_TELEGRAM_TOKEN_FILE": str(token), "CAMPUS247_ALERT_TELEGRAM_CHAT_ID": "1"}), LogNotifier)
