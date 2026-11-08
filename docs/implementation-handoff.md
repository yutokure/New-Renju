# 自律実装ハンドオフ

## 現在のブランチとPR

- PR-A: https://github.com/yutokure/New-Renju/pull/1 — `improvement/hard-stability` → main、Draft
- PR-B: https://github.com/yutokure/New-Renju/pull/2 — `feature/very-hard-engine` → improvement/hard-stability、Draft
- main未マージ。CIなし（オーナー明示指示で撤去）。テスト/計測/ビルドはローカルのみ。

## 実装と検証

467ローカルテスト合格。HardはMinimax/αβ/反復深化/Zobrist/TT/元の行評価・depth2/1.5s維持。独立VHはAND/OR VCF/VCT証明 + 差分窓Negamax/αβ・default5s。共有正式着手ルールは黒exact5優先/白>=5/長連/同方向44/再帰偽三を扱う。3/4/6/7は対称freestyle。簡易序盤は保持し大会規定と区別。

初期80局: VH同一1.5s vs改善Hard20-4、旧Hard22-2、default16-0。Hard非退行は5-6-5censored、未確定。全記録3264着手再生合法・独立終局幾何一致。8開局の相関/再使用と初期VH記録のソースhash未記録は明示。最終戦術7/7VH vs6/7Hard、陽性証明3件、反撃陰性を誤勝利にしない。

WindowsPython実UI60frames最大19.56ms、Esc2.02ms。512MiB Job cap、BLAS1threadでRSS39MB/commit28MB。controlled64cap192allocMemoryError、親退出子kill、実adapter失敗回収を確認。凍結1024MiBは起動分の明示allowanceで、配布合格を意味しない。

## 未達 / 全体CHANGES REQUESTED

1. Hard非退行を統計的に確定できない。独立分析で終盤の見落とし単発バグはなく、浅い候補/同点/戦術の違い。正確性修正を戻す/負け局面だけに合わせて調整しない。
2. PyInstalleronedirbuild成功だが、凍結workerはこのhostのTEMP書込みでPermissionDenied。権限診断NOT_THIS_CLASS、修復0。権限/所有者未変更。このフォルダ権限の追加修復は停止。最終worker早期dispatchではエラーファイルすら書けない場合静かにexit1しmodalを避ける（最終exe再build未検証）。
3. UI最終黒着手再判定は12msでUNKNOWN不適用になり得る。一点の非同期再判定自動継続は未実装。
4. 深い実戦VCT/外部認証/独立開局多様性不足。

## 主文書

- validation-results.md / final-acceptance.md / strength-methodology.md
- hard-core-design.md / hard-async-design.md / hard-strength-followup.md
- very-hard-architecture.md / tactical-search-design.md / renju-rules-design.md
- hard-independent-review.md / renju-independent-review.md / very-hard-independent-review.md / worker-limits-independent-review.md / final-evidence-review.md

## 次の具体作業

- hash-pinned最終16局は回収済み、VH14勝2敗/614合法着手、参考Wilson64.0〜96.5%。群集計/再生監査も保存済み。
- DraftPRの最新説明とローカルテスト/CI不存在/未マージを確認。
- ハンドオフ時も全体PASSにしない。未達を隠してGoalcompleteにしない。改善作業を続けるならUI非同期一点判定と配布TEMP問題のアプリ側可搬対策（Windows権限変更ではない）を優先。
