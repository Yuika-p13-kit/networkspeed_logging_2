"""ダッシュボード最小骨組み
- Flask/FastAPI 等で実装予定
- まずは API のエントリと簡単な README を残す
"""

from typing import Dict


def health() -> Dict[str, str]:
    """簡易ヘルスチェック用関数（後で HTTP エンドポイントに接続）"""
    return {"status": "ok", "component": "dashboard"}


if __name__ == "__main__":
    print(health())
