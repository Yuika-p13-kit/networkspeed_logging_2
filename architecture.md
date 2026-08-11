# Phase 2 ダッシュボード UI 実装 - 詳細計画と修正提案

**作成日**: 2026-08-11  
**対象Issue**: #4  
**前提Phase**: Phase 1 (PR #7 マージ済み)

---

## 1. ユーザー提案の計画評価

### 1.1 提案の妥当性

ユーザー提案は **スコープ・受け入れ基準・推定工数ともに適切に定義** されており、以下の点で高い実装価値がある：

✅ **スコープ明確**: HTML/JS/CSS/Python 統合の 5 つの実装領域が区分されている  
✅ **受け入れ基準テスト可能**: API 呼び出し確認、ブラウザ DevTools での動作確認が可能  
✅ **工数見積もり妥当**: 7-11 時間の推定は Phase 2 スケールとしてリーズナブル  
✅ **架構制約尊重**: RaspberryPi3B+ メモリ制約、既存 DB スキーマ維持を明示  

### 1.2 **必要な修正点（Blocker/High）**

#### 【Blocker 1】Phase 1 に未解決の問題：v2_only 時の fetch が v1 テーブル固定

**現状**:
- `web.py` の API エンドポイント（`/api/dashboard/latest` 等）は実装済み
- しかし `repository.py` の `fetch_latest()`, `fetch_history()` は常に `network_speed_measurements` (v1) テーブル参照
- Phase 2 で `v2_only` 運用想定だが、ダッシュボード表示が空またはデータなし

**影響**: Phase 2 の受け入れ基準「ローカルブラウザで動作確認可能」が実質 **失敗** する。

**修正**: Phase 2 実装前に以下のいずれかを適用：
1. **【推奨】** `repository.py` の fetch メソッドを `schema_migration_mode` に対応させ、v2_only 時は `network_speed_logs_v2` から取得
2. **【代替】** Phase 1 の `v2_only` をサポートの対象外とし、`v1_only` と `dual_write` のみ確認

**責務**: Blocker のため、Implementer が Phase 2 着手前に修正する（または同一 PR で修正）。

---

#### 【Blocker 2】pyproject.toml に依存が未記載

**現状**:
- `web.py` で `fastapi`, `pydantic` を use しているが `pyproject.toml` に未列記
- 本来 `uvicorn`, `jinja2` も追加予定だが、未定義状態

**影響**: `uv sync` が依存を解決できず、実行時エラー発生。

**修正**: Phase 2 タスク【依存追加】で以下を `pyproject.toml` に追加：
```toml
[project]
dependencies = [
    "psycopg2-binary",
    "schedule",
    "speedtest-cli",
    "fastapi",      # ← 新規追加
    "pydantic",     # ← 既に web.py で use（上流で追加されたはず）
    "uvicorn",      # ← 新規追加
    "jinja2",       # ← 新規追加
]
```

**責務**: Implementer が Phase 2 タスク実行時に最初に実施。

---

### 1.3 必要な追加スコープ（High）

#### 【High 1】web.py に StaticFiles / Jinja2Templates 統合が未実装

**現状**:
- `web.py` は API エンドポイントのみ定義（`create_app()` 関数）
- StaticFiles マウント、テンプレートディレクトリ設定なし

**実装内容**（Phase 2 スコープに含める）:
1. `fastapi.staticfiles.StaticFiles` で `static/` ディレクトリをマウント
2. `fastapi.templating.Jinja2Templates` で `templates/` ディレクトリ設定
3. `GET /` でダッシュボード HTML テンプレート（Jinja2）を返すエンドポイント追加
4. `config.py` に `web_static_dir`, `web_template_dir` 設定を追加（オプション）

**修正コード案**（`web.py` の `create_app()` 内）:
```python
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

def create_app(repo: Any, template_dir: str = "templates", static_dir: str = "static"):
    app = FastAPI()
    
    # テンプレートディレクトリ設定
    templates = Jinja2Templates(directory=template_dir)
    
    # 既存 API エンドポイント（変わらず）
    @app.get("/api/dashboard/latest", ...)
    def dashboard_latest(): ...
    
    # ダッシュボード HTML をサーブ
    @app.get("/", response_class=HTMLResponse)
    def dashboard_page(request: Request):
        return templates.TemplateResponse("dashboard.html", {"request": request})
    
    # 静的ファイル（CSS/JS）マウント
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    return app
```

---

#### 【High 2】Web サーバー起動ロジックが未実装

**現状**:
- `main.py` はスケジューラーのみ実行（`bootstrap_and_run()`）
- Web サーバー (Uvicorn) は起動されていない

**スコープ判定**:
- **Phase 2 に含めるべき理由**: 「ローカルブラウザで動作確認可能」の受け入れ基準達成に必須
- **Phase 3 扱いではない理由**: ダッシュボード UI が実装されても、Web サーバーなしには動作確認不可

**実装内容**（Phase 2 スコープに含める）:
- `main.py` で `web.create_app()` を呼び出し、Uvicorn サーバーを起動
- スケジューラーと Web サーバーの共存は **後続 Phase** でスレッド/プロセス分離（現在は起動しない）

**修正コード案**（`main.py`）:
```python
def main_web_only() -> None:
    """Web サーバーのみ起動（ローカル動作確認用）."""
    import uvicorn
    from network_speed.web import create_app
    from network_speed.repository import PostgresRepository
    
    config = load_app_config()
    repo = PostgresRepository(config.db, schema_migration_mode=config.schema_migration_mode)
    repo.connect()
    
    app = create_app(repo)
    uvicorn.run(app, host=config.web_host, port=config.web_port)

if __name__ == "__main__":
    # 環境変数で選択: NETWORK_SPEED_MODE=scheduler or web
    mode = os.getenv("NETWORK_SPEED_MODE", "scheduler")
    if mode == "web":
        main_web_only()
    else:
        main()
```

---

## 2. 修正後の Phase 2 スコープ（最終版）

### 2.1 Must-Have（実装必須）

| # | 領域 | 実装内容 | 試験方法 |
|---|------|--------|--------|
| 1 | pyproject.toml | fastapi, uvicorn, jinja2 を依存に追加 | `uv sync` で解決確認 |
| 2 | web.py | StaticFiles/Jinja2Templates マウント実装 | pytest で app.get("/") 200 応答確認 |
| 3 | web.py | GET / でダッシュボード HTML を返す | ブラウザで http://localhost:8000 表示確認 |
| 4 | templates/dashboard.html | Jinja2 テンプレート（基本レイアウト） | HTML 構文チェック（VSCode） |
| 5 | templates/base.html | ナビゲーション・基本スタイル継承 | template extends 動作確認 |
| 6 | static/dashboard.js | `/api/dashboard/latest` 定期更新実装 | ブラウザ DevTools Network タブで API 呼び出し確認 |
| 7 | static/dashboard.js | `/api/dashboard/history` 呼び出し＋テーブル描画 | テーブル行表示確認 |
| 8 | static/dashboard.js | `/api/dashboard/stats` 呼び出し＋統計表示 | 統計値表示確認 |
| 9 | static/dashboard.js | 期間フィルタ（from/to）実装 | フィルタフォーム入力で API パラメータ確認 |
| 10 | static/dashboard.js | エラーハンドリング（API 502 等） | DevTools Console でエラーメッセージ確認 |
| 11 | static/style.css | Bootstrap CDN 統合 + カスタムスタイル | ブラウザでレスポンシブデザイン確認 |
| 12 | main.py | `NETWORK_SPEED_MODE=web` で Web サーバー起動ロジック追加 | `NETWORK_SPEED_MODE=web python main.py` で起動確認 |
| 13 | repository.py | **【重要】** v2_only 時 fetch の v2 テーブル対応 | v2_only 設定で fetch_latest() が v2 テーブルから取得確認 |

### 2.2 Should-Have（推奨するが Phase 3 へ延期可）

- ダークモード切り替え UI
- グラフ（Plotly.js）による時系列可視化
- 複数デバイスのフィルタリング
- キャッシング戦略（`Cache-Control` ヘッダ）

### 2.3 Non-Scope（対象外）

- Web サーバーとスケジューラーの共存実装（Phase 3）
- 認証・認可（運用環境は内部ネットワーク限定想定）
- ダッシュボード DB テーブル変更（読み取り専用）
- CI/CD パイプライン統合（Phase 3 以降）

---

## 3. 受け入れ基準（修正後）

### 3.1 API 層
- [ ] `web.py` が StaticFiles/Jinja2Templates 統合済み
- [ ] `GET /` で `templates/dashboard.html` を 200 応答
- [ ] `GET /api/dashboard/latest` で最新値を JSON 応答
- [ ] `GET /api/dashboard/history` で履歴を JSON 応答
- [ ] `GET /api/dashboard/stats` で統計を JSON 応答
- [ ] v2_only 設定時、fetch が `network_speed_logs_v2` テーブルから取得

### 3.2 フロントエンド層
- [ ] HTML テンプレート（base.html, dashboard.html）が Jinja2 文法で実装
- [ ] JavaScript（dashboard.js）が以下を実装：
  - `/api/dashboard/latest` を 10 秒間隔で定期更新、画面表示
  - `/api/dashboard/history` 呼び出し、ページネーション付き表示
  - `/api/dashboard/stats` 呼び出し、統計情報表示
  - 期間フィルタ（from/to）の入力受け取り・API パラメータ構成
  - エラーハンドリング（失敗時ユーザーメッセージ表示）
- [ ] CSS（style.css）が Bootstrap 5 CDN 統合 + レスポンシブデザイン実装

### 3.3 依存・設定
- [ ] `pyproject.toml` に fastapi, uvicorn, jinja2 記載
- [ ] `config.py` に web 関連設定（既存）
- [ ] `main.py` に `NETWORK_SPEED_MODE=web` で Web サーバー起動ロジック

### 3.4 動作確認
- [ ] `uv sync` で依存解決完了
- [ ] `NETWORK_SPEED_MODE=web python main.py` で Web サーバー起動
- [ ] `curl http://localhost:8000` で HTML 応答確認
- [ ] ブラウザ `http://localhost:8000` でダッシュボード表示確認
- [ ] ブラウザ DevTools Network タブで API 呼び出し確認
- [ ] ブラウザ DevTools Console でエラー・警告なし

---

## 4. 依存関係と前提条件

### 4.1 前提条件

| 条件 | 状態 | 対応 |
|-----|------|------|
| Phase 1 API 実装完了 | ✅ PR #7 マージ済み | 依存完了 |
| v2_only 時 fetch 対応 | ⚠️ 未実装 | **Phase 2 実装前に Blocker 修正必須** |
| DB テーブル存在 | ✅ `network_speed_logs_v2` 稼働中 | 依存完了 |
| Python 3.11+ | ✅ 環境確認済み | 依存完了 |
| PostgreSQL 接続 | ✅ 既存 DB 接続ロジック使用 | 依存完了 |

### 4.2 技術スタック

| コンポーネント | 選択肢 | 理由 |
|-------------|--------|------|
| Web Framework | FastAPI | Phase 1 既存選択、軽量、async 対応 |
| WSGI Server | Uvicorn | FastAPI デフォルト、Python Pure |
| Template Engine | Jinja2 | FastAPI 標準、学習曲線低 |
| Frontend | Vanilla JS + Bootstrap 5 CDN | 軽量、メモリ制約対応（RaspberryPi3B+） |
| グラフ | Plotly.js CDN（Phase 3） | インタラクティブ、CDN 軽量 |

### 4.3 スケーリング仮定

- **ユーザー**: 1-2 名（ローカルブラウザアクセス）
- **API レート**: 10 秒 1 回 latest 呼び出し × 数秒間隔の手動操作
- **データ量**: 100-1000 件/月の計測記録（取得時 1000 件制限）
- **メモリ**: RaspberryPi3B+ (1GB) で Web サーバー + スケジューラー共存時 OK 想定（Phase 3）

---

## 5. リスク評価と対応

### 5.1 重大度別リスク

| 重大度 | リスク | 発生確率 | 影響 | 対応 |
|--------|--------|--------|------|------|
| **Critical** | v2_only fetch 対応漏れで表示空データ | 高 | 受け入れ基準不達 | Blocker 修正を Phase 2 前提に明示 |
| **High** | pyproject.toml 依存漏れで実行時エラー | 中 | 動作確認不可 | チェックリストに依存追加を最初に配置 |
| **High** | Web サーバー起動ロジック未実装 | 中 | ブラウザ確認不可 | Phase 2 スコープに明示 |
| **Medium** | Jinja2 Template 構文エラー | 低 | 画面描画失敗 | pytest + ブラウザテストで早期検知 |
| **Medium** | JavaScript Promise/async エラー | 中 | API 呼び出し失敗表示 | DevTools Console 確認、エラーハンドリング実装 |
| **Low** | RaspberryPi3B+ メモリ不足 | 低 | Web サーバー起動失敗 | Phase 3 で共存テスト対応 |

### 5.2 対応計画

| リスク | 対応タイミング | 対応内容 |
|--------|-------------|--------|
| Critical | Phase 2 前 | `repository.py` fetch メソッド修正 |
| High | Phase 2 タスク開始 | `pyproject.toml` 依存追加チェックリスト化 |
| High | Phase 2 実装開始 | Web サーバー起動ロジック (main.py) を初期タスク化 |
| Medium | Phase 2 実装中 | ブラウザ DevTools で動作確認 |
| Low | Phase 3 テスト | RaspberryPi3B+ 共存動作確認 |

---

## 6. タスク分解（修正後）

### 6.1 順序付き実装タスク

```
Phase 2-1: 依存・基盤整備
  ├─ Task 2.1.1: pyproject.toml に fastapi, uvicorn, jinja2 追加
  ├─ Task 2.1.2: uv sync で依存解決確認
  └─ Task 2.1.3: repository.py の fetch メソッドを v2_only 対応 【Blocker 修正】

Phase 2-2: Web サーバー起動ロジック
  ├─ Task 2.2.1: main.py に NETWORK_SPEED_MODE 分岐ロジック追加
  ├─ Task 2.2.2: main_web_only() で Uvicorn 起動
  └─ Task 2.2.3: ローカル動作確認（8000 ポートで起動）

Phase 2-3: Web フレームワーク統合
  ├─ Task 2.3.1: web.py に StaticFiles マウント追加
  ├─ Task 2.3.2: web.py に Jinja2Templates 設定追加
  ├─ Task 2.3.3: GET / エンドポイント実装（dashboard.html 返す）
  └─ Task 2.3.4: pytest で GET / 200 応答テスト

Phase 2-4: HTML テンプレート実装
  ├─ Task 2.4.1: templates/base.html 実装（Bootstrap CDN, ナビゲーション）
  ├─ Task 2.4.2: templates/dashboard.html 実装（レイアウト, プレースホルダ）
  └─ Task 2.4.3: ブラウザで http://localhost:8000 表示確認

Phase 2-5: JavaScript API クライアント実装
  ├─ Task 2.5.1: static/dashboard.js 作成（基本構造）
  ├─ Task 2.5.2: fetchLatest() 実装（/api/dashboard/latest 呼び出し）
  ├─ Task 2.5.3: fetchHistory() 実装（/api/dashboard/history 呼び出し）
  ├─ Task 2.5.4: fetchStats() 実装（/api/dashboard/stats 呼び出し）
  ├─ Task 2.5.5: 期間フィルタ（from/to）入力処理
  ├─ Task 2.5.6: エラーハンドリング実装
  └─ Task 2.5.7: DevTools Network で API 呼び出し確認

Phase 2-6: CSS スタイリング
  ├─ Task 2.6.1: static/style.css 作成（Bootstrap カスタマイズ）
  ├─ Task 2.6.2: レスポンシブデザイン実装
  └─ Task 2.6.3: ブラウザで各デバイスサイズで表示確認

Phase 2-7: 統合テスト
  ├─ Task 2.7.1: エンドツーエンド動作確認（サーバー起動 → ブラウザアクセス）
  ├─ Task 2.7.2: API エラーケース確認（データ空時、タイムアウト等）
  └─ Task 2.7.3: PR ドキュメント作成（受け入れ基準検証結果記載）
```

### 6.2 推定工数（修正後）

| フェーズ | タスク数 | 推定工数 | 考慮 |
|---------|---------|--------|------|
| 2-1 | 3 | 1 時間 | Blocker 修正含む |
| 2-2 | 3 | 1 時間 | 環境変数分岐シンプル |
| 2-3 | 4 | 1.5 時間 | pytest 追加 |
| 2-4 | 3 | 2 時間 | 基本レイアウト, Jinja2 学習 |
| 2-5 | 7 | 4 時間 | API クライアント本体 |
| 2-6 | 3 | 1.5 時間 | CSS カスタマイズ |
| 2-7 | 3 | 1 時間 | 統合テスト |
| **合計** | **26** | **11.5 時間** | Phase 1 Blocker 修正含む |

**※ Phase 1 Blocker 修正（Task 2.1.3）が別途 1-2 時間必要な可能性あり**

---

## 7. 仮定と注記

### 7.1 明示的な仮定

| # | 仮定 | 根拠 | 影響 |
|---|------|------|------|
| 1 | v2_only 時の fetch 修正は implementer 側で実施 | review.md で Blocker 明示 | Phase 2 前提条件 |
| 2 | PostgreSQL DB は稼働中（新規ユーザーは database_info.txt セットアップ必須） | README 既述 | 接続テストで確認 |
| 3 | Bootstrap 5 CDN から取得（NPM 未使用） | RaspberryPi3B+ 軽量重視 | 通信環境必須 |
| 4 | 認証なし（内部ネットワーク限定運用） | 要件で明示 | HTTP 通信でセキュアスレッド無し |
| 5 | スケジューラーと Web サーバーの共存は Phase 3 | main.py で mode 分岐 | ローカル動作確認時は mode=web のみ |
| 6 | API は既に 30 日期間制限実装済み（Phase 1） | web.py 確認 | クエリパラメータ validation 済み |

### 7.2 ドキュメント参照

| 参照 | パス | 確認事項 |
|-----|------|--------|
| API 仕様 | `src/network_speed/web.py` | `/api/dashboard/*` エンドポイント確認 |
| DB スキーマ | Phase 1 PR #7 / docs/requirements.md | `network_speed_logs_v2` テーブル確認 |
| 運用環境 | README.md | database_info.txt セットアップ |
| v2_only 対応状況 | review.md | Blocker 一覧確認 |
| 設定読み込み | `src/network_speed/config.py` | web_host, web_port 確認 |

---

## 8. 受入確認チェックリスト（Phase 2 完了時）

### 依存・環境
- [ ] `uv sync` で依存解決（fastapi, uvicorn, jinja2 含む）
- [ ] `python -c "import fastapi; import uvicorn; import jinja2"` で import OK
- [ ] PostgreSQL DB 接続確認（`NETWORK_SPEED_SCHEMA_MIGRATION_MODE=v2_only` 設定時）

### Web サーバー・API
- [ ] `NETWORK_SPEED_MODE=web python main.py` で Uvicorn 起動
- [ ] `curl http://localhost:8000` で HTML 応答（200）
- [ ] `curl http://localhost:8000/api/dashboard/latest` で JSON 応答（200）
- [ ] `curl http://localhost:8000/static/dashboard.js` で JS ファイル応答（200）

### フロントエンド
- [ ] ブラウザ `http://localhost:8000` でダッシュボード表示
- [ ] 画面で最新値・履歴テーブル・統計情報が表示される
- [ ] 期間フィルタフォーム入力で API パラメータが変更される
- [ ] API 502 エラー時、画面にエラーメッセージ表示
- [ ] ブラウザ DevTools Console でエラー・警告なし

### テスト
- [ ] pytest で web サーバー API レスポンス確認（少なくとも GET / 200）
- [ ] v2_only 設定で fetch_latest() が v2 テーブルから取得

### ドキュメント
- [ ] PR 説明文に受け入れ基準チェック結果記載
- [ ] `NETWORK_SPEED_MODE=web` 起動方法を README に追記または docs/dashboard-setup.md 作成

---

## 9. 次フェーズへの引継ぎ事項

### Phase 3 への依存
- Web サーバーとスケジューラーの共存実装（スレッド/マルチプロセス分離）
- 本番環境での systemd ユニット設定（Web サーバー用）
- Plotly.js グラフ実装

### ドキュメント化必須
- ダッシュボード起動ガイド（docs/dashboard-setup.md）
- API リファレンス追記（レスポンス形式詳細）
- トラブルシューティング（ポート競合、DB 接続エラー等）

---

## 10. 結論と推奨

### ✅ 提案の採択可否

**採択可能（条件付き）**

提案されたスコープ・受け入れ基準・工数は適切である。ただし、以下の **必須前提条件** を満たす必要がある：

1. **Blocker 1 修正**: `repository.py` の fetch メソッドを v2_only 対応（Phase 2 実装前）
2. **Blocker 2 修正**: `pyproject.toml` に fastapi, uvicorn, jinja2 追加（Phase 2 実装開始時）
3. **スコープ追加**: Web サーバー起動ロジック (main.py) を Phase 2 に含める

### 🎯 進め方

1. **Task 実装開始前** に本 `architecture.md` の Blocker チェックリスト（5.1 表） を満たしたか確認
2. **Task 順序** を 6.1 に従い実施（依存・基盤 → Web サーバー → フレームワーク → テンプレート → クライアント → スタイル → テスト）
3. **受け入れ確認** は 8 番チェックリストで手動検証

### 💡 補足

- **RaspberryPi3B+ 動作確認**: Phase 2 はローカル Mac 開発環境を想定。実運用環境テストは Phase 3 で実施
- **認証・HTTPS**: 現在スコープ外（内部ネットワーク限定前提）。本番運用時に検討
- **グラフ可視化**: Phase 3 で Plotly.js 実装。Phase 2 は数値表示に専注

---

**作成**: Planner  
**次レビュー対象**: Project Manager (優先度決定)
