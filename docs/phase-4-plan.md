# Phase 4: ダッシュボード拡張・運用統合 - 計画書

## 背景
Issue #4 の受け入れ基準（Phase 0-3）は 2026-08-11 に完全達成・CLOSED となった。
同時にユーザーコメント「要素イメージ」として以下のユースケース 5-7 が提示されており、これらを Phase 4 で実装する計画。

---

## 目的

1. **ダッシュボード拡張**: requirements.md 12.3 のユースケース 5-7 を実装
   - ユースケース 5: 過去1時間・直近ウィンドウの移動平均表示
   - ユースケース 6: 曜日別／時間帯別の傾向表示
   - ユースケース 7: シーズン別統計・比較

2. **運用統合**: 本番環境への完全統合
   - systemd サービス化（RPi 自動起動）
   - ロギング・監視設定
   - セキュリティ設定（TLS、認証オプション）

3. **品質向上**: 性能・信頼性・保守性の向上
   - 大規模データ対応（キャッシュ・インデックス）
   - エラーハンドリング強化
   - ドキュメント整備

---

## スコープ

### 4.1 API 拡張（repository + web.py）

#### 移動平均・1時間平均 API
```
GET /api/dashboard/aggregates?type=moving_avg&window=6&from=...&to=...
```
- 6 点移動平均（1時間ごと、または 10 分刻み）
- 1 時間平均（1h毎の履歴）
- Response: `[{timestamp, download_avg, upload_avg}, ...]`

#### 曜日別・時間帯別集計 API
```
GET /api/dashboard/aggregates?type=weekday_hourly&from=...&to=...
```
- 曜日（月〜日）× 時間帯（0-23 時）の 2D 集計
- Response: `{weekday: {hourly: {hour: {avg_download, avg_upload, count}, ...}, ...}, ...}`

#### シーズン別統計 API
```
GET /api/dashboard/aggregates?type=season&season=2026Q3&from=...&to=...
```
- シーズン（年度/四半期/月単位など）ごとの統計
- Response: `{season: {count, avg_download, max_download, min_download, ...}, ...}`

### 4.2 UI 拡張（dashboard.html + dashboard.js）

#### グラフ表示
- Plotly.js による折れ線グラフ（download/upload の時系列）
- 移動平均オーバーレイ
- 曜日別・時間帯別ヒートマップ
- シーズン別比較チャート

#### フィルタ・インタラクション
- グラフズーム・パン
- 曜日フィルタ（平日/休日切り替え）
- 時間帯フィルタ
- シーズン選択ドロップダウン

### 4.3 運用統合

#### systemd サービス化
- `network-speed-dashboard.service` ファイル作成
- 自動起動・再起動設定
- ロギング設定（journal へのリダイレクト）

#### セキュリティ設定
- TLS オプション（自己署証明書 or Let's Encrypt）
- 認証オプション（Basic Auth or OAuth2 OAuth との連携）
- CORS 設定

#### 監視・アラート
- Prometheus メトリクス公開（オプション）
- ヘルスチェックエンドポイント
- ロギング・ログローテーション

---

## 実装計画

### Step 1: API 拡張実装（1-2 週間）
1. `repository.py` に以下のメソッドを追加
   - `fetch_moving_average(window, from_, to_)`
   - `fetch_weekday_hourly_stats(from_, to_)`
   - `fetch_season_stats(season, from_, to_)`

2. `web.py` に aggregates エンドポイント拡張
   - `GET /api/dashboard/aggregates?type=...` の複数タイプ対応

3. テスト実装
   - 各メソッドの単体テスト
   - エンドポイント統合テスト
   - データ妥当性テスト

### Step 2: UI 拡張実装（1-2 週間）
1. `dashboard.html` にグラフコンテナ追加
2. `dashboard.js` に API クライアント関数追加
   - `fetchMovingAverage()`, `fetchWeekdayHourly()`, `fetchSeasonStats()`
3. グラフ描画関数実装（Plotly.js）
4. インタラクション実装（フィルタ、ズーム etc）
5. スタイル調整（レスポンシブ, ダークモード)

### Step 3: 運用統合（1 週間）
1. systemd サービスファイル作成・テスト
2. 本番環境での起動検証
3. ロギング・監視設定
4. ドキュメント更新（運用ガイド）

### Step 4: テスト・デプロイ（1 週間）
1. 統合テスト（全機能同時動作確認）
2. 性能測定（キャッシュ無し vs 有り）
3. 本番環境への段階的デプロイ
4. ロールバック手順確認

---

## 受け入れ基準（Phase 4）

### 機能面
- [ ] 移動平均 API が正常に動作すること（テスト合格）
- [ ] 曜日別・時間帯別集計 API が正常に動作すること（テスト合格）
- [ ] シーズン別統計 API が正常に動作すること（テスト合格）
- [ ] UI でグラフが描画されること（手動確認）
- [ ] フィルタ・インタラクション が動作すること（手動確認）

### 運用面
- [ ] systemd サービスが RPi で自動起動・停止できること
- [ ] ロギングが journal に記録されること
- [ ] ヘルスチェックエンドポイントが動作すること
- [ ] 本番環境でのトラブルシュート手順がドキュメント化されていること

### 品質面
- [ ] 大規模データ（10k+ レコード）でも レスポンス時間が要件内（95p 2s）
- [ ] エラーハンドリング が統一されていること
- [ ] 既存テストがすべて合格すること

---

## 非スコープ（Phase 4 では対象外）

- 高度な認証（OAuth2, SAML）
- BI ツール連携（Grafana, Tableau など）
- データアーカイブ・大規模保存対応
- モバイルアプリ化

---

## リスク・制約

### リスク
- 大規模データでの集計パフォーマンス（対策: キャッシュ・定期集計テーブル導入）
- RPi のリソース制約（対策: スワップ増量、連続 API 呼び出し制限）

### 制約
- DB スキーマ変更は引き続き非対象（新テーブルの作成は許可、既存テーブルの列追加は最小限）
- 既存 API との互換性を維持（v1/v2 互換レイヤー保持）

---

## 優先度・タイムライン

| タスク | 優先度 | 見積 | 開始 | 完了 |
|--------|--------|------|------|------|
| API 拡張 | P0 | 1-2w | TBD | TBD |
| UI 拡張 | P0 | 1-2w | TBD | TBD |
| systemd 化 | P1 | 1w | TBD | TBD |
| テスト・デプロイ | P0 | 1w | TBD | TBD |
| ドキュメント | P1 | 1w | TBD | TBD |

---

## 参考資料

- **Issue #4**: ダッシュボード作成: 要件定義と実装準備 (CLOSED)
- **PR #7**: Issue #4: dashboard read API - basic implementation (MERGED)
- **requirements.md**: 第 12 章（ダッシュボード要件定義）
- **User Comment**: 「要素イメージ」(2026-08-11)

---

## 次のアクション

1. ユーザーから Phase 4 スケジュール・優先度を確認
2. 各ステップの詳細要件をユーザーとすり合わせ
3. 開発チームで工数見積を確定
4. 実装開始日を決定
