import os

from flask import Blueprint, render_template

# pip インストール後もパスが解決されるよう絶対パスで指定
_HERE = os.path.dirname(os.path.abspath(__file__))

common_ui = Blueprint(
    "common_ui",
    __name__,
    template_folder=os.path.join(_HERE, "templates"),
    static_folder=os.path.join(_HERE, "static"),
    static_url_path="/static/common_ui",  # アプリ側の /static と衝突しないよう隔離
)


@common_ui.get("/ui/login")
def login_page():
    return render_template("common_ui/login.html")


@common_ui.get("/ui/register")
def register_page():
    return render_template("common_ui/register.html")


@common_ui.get("/ui/profile")
def profile_page():
    return render_template("common_ui/profile.html")
