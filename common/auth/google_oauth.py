import os
from dataclasses import dataclass

from authlib.integrations.requests_client import OAuth2Session


_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"
_DEFAULT_SCOPES = ["openid", "email", "profile"]


@dataclass
class GoogleUserInfo:
    """Googleから取得したユーザー情報。"""
    google_id: str
    email: str
    name: str
    picture: str | None


class GoogleOAuth:
    """Google OAuth2 認証フロー（Authorization Code Flow）を扱うクライアント。

    環境変数 GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET を設定して使用する。

    フロー::

        1. get_auth_url(redirect_uri) でGoogleの認証URLを取得しリダイレクト
        2. Googleがコールバックにcode + stateを付けてリダイレクト
        3. exchange_code(code, redirect_uri) でユーザー情報を取得
        4. 取得した google_id / email でDBのユーザーを検索・作成
        5. create_token(user.id) でJWTを発行して返す
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        self.client_id = client_id or os.environ["GOOGLE_CLIENT_ID"]
        self.client_secret = client_secret or os.environ["GOOGLE_CLIENT_SECRET"]

    def get_auth_url(self, redirect_uri: str, state: str | None = None) -> str:
        """GoogleのOAuth2認証ページURLを返す。

        Args:
            redirect_uri: 認証後のコールバックURL
            state: CSRF対策用のランダム文字列（省略時は自動生成）

        Returns:
            リダイレクト先URL
        """
        session = OAuth2Session(
            client_id=self.client_id,
            redirect_uri=redirect_uri,
            scope=_DEFAULT_SCOPES,
            state=state,
        )
        url, _ = session.create_authorization_url(
            _AUTHORIZATION_ENDPOINT,
            access_type="offline",
            prompt="select_account",
        )
        return url

    def exchange_code(self, code: str, redirect_uri: str) -> GoogleUserInfo:
        """認可コードをアクセストークンに交換してユーザー情報を取得する。

        Args:
            code: Googleから受け取った認可コード
            redirect_uri: get_auth_url に渡したものと同一のURL

        Returns:
            GoogleUserInfo

        Raises:
            ValueError: ユーザー情報の取得に失敗した場合
        """
        session = OAuth2Session(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=redirect_uri,
        )
        session.fetch_token(_TOKEN_ENDPOINT, code=code)

        resp = session.get(_USERINFO_ENDPOINT)
        if not resp.ok:
            raise ValueError(f"Failed to fetch user info: {resp.status_code}")

        data = resp.json()
        return GoogleUserInfo(
            google_id=data["sub"],
            email=data["email"],
            name=data.get("name", ""),
            picture=data.get("picture"),
        )
