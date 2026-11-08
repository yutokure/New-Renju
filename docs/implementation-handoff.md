# 自律実装ハンドオフ

## 現在のブランチとPR

- PR-A: https://github.com/yutokure/New-Renju/pull/1 — `improvement/hard-stability` → main、Draft
- PR-B: https://github.com/yutokure/New-Renju/pull/2 — `feature/very-hard-engine` → improvement/hard-stability、Draft
- main未マージ。CIなし（オーナー明示指示で撤去）。テスト/計測/ビルドはローカルのみ。

## 実装と検証

539ローカルテスト合格（9.87秒）。HardはMinimax/αβ/反復深化/Zobrist/TT/元の行評価・depth2/1.5s維持。独立VHはAND/OR VCF/VCT証明 + 差分窓Negamax/αβ・default5s。共有正式着手ルールは黒exact5優先/白>=5/長連/同方向44/再帰偽三を扱う。3/4/6/7は対称freestyle。簡易序盤は保持し大会規定と区別。

初期80局: VH同一1.5s vs改善Hard20-4、旧Hard22-2、default16-0。Hard非退行は5-6-5censored、未確定。全記録3264着手再生合法・独立終局幾何一致。8開局の相関/再使用と初期VH記録のソースhash未記録は明示。最終戦術7/7VH vs6/7Hard、陽性証明3件、反撃陰性を誤勝利にしない。

WindowsPython実UI60frames最大19.56ms、Esc2.02ms。512MiB Job cap、BLAS1threadでRSS39MB/commit28MB。controlled64cap192allocMemoryError、親退出子kill、実adapter失敗回収を確認。凍結1024MiBは起動分の明示allowanceで、配布合格を意味しない。

## 未達 / 全体CHANGES REQUESTED

1. Hard非退行を統計的に確定できない。独立分析で終盤の見落とし単発バグはなく、浅い候補/同点/戦術の違い。正確性修正を戻す/負け局面だけに合わせて調整しない。
2. PyInstalleronedirbuild成功だが、凍結workerはこのhostのTEMP書込みでPermissionDenied。権限診断NOT_THIS_CLASS、修復0。権限/所有者未変更。このフォルダ権限の追加修復は停止。最終worker早期dispatchではエラーファイルすら書けない場合静かにexit1しmodalを避ける。最終exe再ビルド/明示root4難易度worker・adapter・単一判定・キャンセル・回収は成功。CLI--worker-directoryで実GUIのVery Hard選択・人間着手・AI応手・保存・Menu・終了/回収も成功。ただし既定TEMP経路は未認定。
3. UI12ms再判定超過は専用ワーカーで5秒まで自動継続する機構を実装済み・限定独立PASS。追加予算でも未判定ならUNKNOWN/未着手/R再試行。実Windows強制0秒予算で0.448秒後に合法手適用を確認。
4. 深い実戦VCT/外部認証/独立開局多様性不足。

## 主文書

- validation-results.md / final-acceptance.md / strength-methodology.md
- hard-core-design.md / hard-async-design.md / hard-strength-followup.md
- very-hard-architecture.md / tactical-search-design.md / renju-rules-design.md
- hard-independent-review.md / renju-independent-review.md / very-hard-independent-review.md / worker-limits-independent-review.md / final-evidence-review.md

## 次の具体作業

- hash-pinned最終16局は回収済み、VH14勝2敗/614合法着手、参考Wilson64.0〜96.5%。群集計/再生監査も保存済み。
- DraftPRの最新説明とローカルテスト/CI不存在/未マージを確認。
- 事前固定16開局32局は完了回収済み。Hard18勝9敗5打切り/エラー0、参考Wilson47.82〜81.36%、2510合法再生、全ゲーム開始hash一致。統計的非退行はなお未確定。全対局計128局6388着手（スモーク除外）。
- 独立Hard浅い探索oracle担当ac5f6284はtests/test_hard_search_oracle.pyとdocs/hard-search-oracle.mdのみ担当。20小盤のうち19は厳密2ply最適一致、1は既存強制応手絞込みの地平差でforkより単一脅威を好む制限を特徴づけ済み。対象42テスト0.53秒合格。追加後の全体回帰539件は32局完了後に直列実行し9.87秒で合格済み。アルファ/TTバグと誤認しない。
- ハンドオフ時も全体PASSにしない。未達を隠してGoalcompleteにしない。UI非同期一点判定と明示rootの可搬対策/実配布GUIは完了。次はHard非退行の開局多様化、既定TEMPの別通常環境での再現、実戦VCTコーパスの拡張を優先。
