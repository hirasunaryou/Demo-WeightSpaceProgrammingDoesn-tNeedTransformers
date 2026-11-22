#!/usr/bin/env python3
"""Start the offline, zero-install WSP teaching application.

The original paper experiment is NOT run by this launcher. It has different
PyTorch/Linux/bubblewrap requirements detailed in docs/REPRODUCE_ORIGINAL.md.
"""
import json
import sys
import threading
import traceback
from urllib.request import urlopen
import webbrowser
from lab.server import serve

def main():
    if sys.version_info<(3,8):
        print("Python 3.8以上が必要です。",file=sys.stderr)
        return 1
    url,server=serve()
    print("="*51)
    print(" WSP Live Lab / Weight-Space Programming")
    print("="*51)
    print("公開モデルの知識行を使った学習用サンドボックスです。")
    print("元論文のPyTorch forward()は実行しません。")
    print("追加pipパッケージ・GPU・仮想環境は不要。ブラウザはローカル接続のみ。")
    if "--self-check" in sys.argv:
        worker=threading.Thread(target=server.serve_forever,daemon=True)
        worker.start()
        try:
            with urlopen(url+"api/catalog",timeout=30) as response:
                data=json.load(response)
            assert data["statistics"]["bundled_fact_rows"]>100
            with urlopen(url,timeout=15) as response:
                assert b"WSP" in response.read()
            print("PASS: original published fact snapshots, local API, web UI")
            return 0
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=4)
    print("起動しました:",url)
    print("終了はターミナルを閉じるか Ctrl+C。")
    try:
        webbrowser.open(url)
        server.serve_forever()
        return 0
    except KeyboardInterrupt:
        print("\n終了しました。")
        return 0
    finally:
        server.server_close()

if __name__=="__main__":
    try:
        sys.exit(main())
    except Exception:
        print("起動に失敗しました。以下のログを確認してください。",file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
