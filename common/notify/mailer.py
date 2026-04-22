import smtplib
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


@dataclass
class MailConfig:
    """メール送信設定を保持するデータクラス。"""
    host: str
    port: int
    user: str
    password: str
    from_address: str


class Mailer:
    """SMTP + STARTTLSでメールを送信するクライアント。

    送信のたびに接続を確立・切断するステートレスな設計。
    """

    def __init__(self, config: MailConfig) -> None:
        """
        Args:
            config: SMTP接続設定
        """
        self.config = config

    def send(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        html: bool = False,
    ) -> None:
        """メールを送信する。

        Args:
            to: 送信先アドレス（単一文字列またはリスト）
            subject: 件名
            body: 本文
            html: Trueの場合はHTMLメール、FalseはPROAINテキスト

        Raises:
            smtplib.SMTPException: SMTP通信エラー時
        """
        recipients = [to] if isinstance(to, str) else to

        msg = MIMEMultipart("alternative")
        msg["From"] = self.config.from_address
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject

        subtype = "html" if html else "plain"
        msg.attach(MIMEText(body, subtype, "utf-8"))

        # STARTTLSで暗号化してから認証・送信
        with smtplib.SMTP(self.config.host, self.config.port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(self.config.user, self.config.password)
            server.sendmail(self.config.from_address, recipients, msg.as_string())
