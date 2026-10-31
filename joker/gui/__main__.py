"""Start the local GUI:  python -m joker.gui  [--port 8765] [--no-browser]"""

import argparse
import webbrowser

from .server import serve


def main() -> None:
    parser = argparse.ArgumentParser(description="JOKER local table")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    server = serve(args.port)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"JOKER table running at {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
