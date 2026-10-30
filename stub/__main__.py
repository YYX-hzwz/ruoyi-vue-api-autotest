"""独立启动契约桩：`python -m stub`。

用于手工联调：先起桩，再用 `curl` 或浏览器验证接口形状。
"""

from __future__ import annotations

import argparse

from werkzeug.serving import make_server

from .app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="启动 RuoYi 契约桩")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--fixed",
        action="store_true",
        help="关闭缺陷复现（模拟后端已修复）",
    )
    parser.add_argument("--captcha", action="store_true", help="开启验证码")
    args = parser.parse_args()

    app = create_app(reproduce_bugs=not args.fixed, captcha_enabled=args.captcha)
    server = make_server(args.host, args.port, app, threaded=True)
    print(f"契约桩已启动: http://{args.host}:{server.server_port}")
    print(f"缺陷复现: {'关闭（模拟已修复）' if args.fixed else '开启'}")
    print("健康检查: GET /__stub/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
