# Gomoku 2.0 ゲート別Issue台帳

初期main: `edc95cc`。G01→G05の直列受入。棋力・探索・評価関数は今回変更しない。

| Issue | 分類 | ゲート | 内容 | リリースへの影響 |
|---|---|---|---|---|
| [#11](https://github.com/yutokure/New-Renju/issues/11) | A/B | G01 | 棋譜の意味検証・一括適用 | PR #15で解決・CLOSED |
| [#14](https://github.com/yutokure/New-Renju/issues/14) | A/B | G01 | 保存の直接上書き・衝突・通知 | PR #15で解決・CLOSED |
| [#16](https://github.com/yutokure/New-Renju/issues/16) | A | G02 | hover依存・イベント座標・遷移と連続入力 | PR #20で解決・CLOSED |
| [#17](https://github.com/yutokure/New-Renju/issues/17) | A | G03 | 最終フレーム再描画と履歴へのライブ表示混入 | PR #22で解決・CLOSED |
| [#18](https://github.com/yutokure/New-Renju/issues/18) | A | G02 | 再戦候補の資源例外と部分reset | PR #20で解決・CLOSED |
| [#19](https://github.com/yutokure/New-Renju/issues/19) | A | G02 | 取消・期限切れワーカーの強制停止fallback | PR #20で解決・CLOSED |
| [#21](https://github.com/yutokure/New-Renju/issues/21) | A | G04 | 補助脅威・Popup・部分overlayの表示意味 | PR #24で解決・CLOSED |
| [#5](https://github.com/yutokure/New-Renju/issues/5) | B | G05 | Windows凍結ワーカーの既定通信領域 | オーナー採用PORTABLEでexe隣既定・noargs非管理者7行matrix/展開ZIP PASS。PR #27で解決 |
| [#25](https://github.com/yutokure/New-Renju/issues/25) | A/B | G05 | 実配布物の第三者ライセンス／フォント原文 | FreeSans除外＋DejaVu原文hash確認、69notices/source同梱の展開ZIP照合。PR #27で解決 |
| [#26](https://github.com/yutokure/New-Renju/issues/26) | A/B | G05 | 回収例外で後続タスク処理／所有権が中断 | 故障注入とnative異常子終了/終了回収PASS。PR #27で解決 |
| [#28](https://github.com/yutokure/New-Renju/issues/28) | A/B | G05 | 再ビルド前のportableデータ保護 | builder/spec事前guard・後段guard、既存bytes不変を検証。PR #27で解決 |
| [#29](https://github.com/yutokure/New-Renju/issues/29) | A | G05 | 長い棋譜名とロード通知の画面重複 | 文字surfaceをhit枠内へ・7行page、実exe画像とinvalid load拒否を確認。PR #27で解決 |
| [#23](https://github.com/yutokure/New-Renju/issues/23) | A | G04 | 状態・ルール説明・初回操作・視認性 | PR #24で解決・CLOSED |
| [#13](https://github.com/yutokure/New-Renju/issues/13) | A | G04 | 研究値の意味・表示 | 既存表示を確認・補完、PR #24で解決・CLOSED |
| [#9](https://github.com/yutokure/New-Renju/issues/9) | C | G04 | 深い禁手再帰のUNKNOWNと手動再試行 | UNKNOWNを誤判定へ変換せず、制限と操作を説明 |
| [#10](https://github.com/yutokure/New-Renju/issues/10) | C | G05 | 非WindowsのOSメモリ強制上限 | 正式配布対象はWindows。非Windows保証なしを明示 |
| [#3](https://github.com/yutokure/New-Renju/issues/3) | C | 対象外 | Hard棋力非退行の独立証拠不足 | 既知制限。普遍的な棋力改善を主張しない |
| [#4](https://github.com/yutokure/New-Renju/issues/4) | C | 対象外 | Hard候補絞り込みの探索地平 | 既知制限。探索改修しない |
| [#6](https://github.com/yutokure/New-Renju/issues/6) | C | 対象外 | Very Hard独立コーパス不足 | 既知制限。普遍的な棋力改善を主張しない |
| [#7](https://github.com/yutokure/New-Renju/issues/7) | C | 対象外 | VCF/VCTの固定予算 | 既知制限。探索改修しない |
| [#8](https://github.com/yutokure/New-Renju/issues/8) | C | 対象外 | Very Hard長連窓評価 | 既知制限。評価関数改修しない |
| [#12](https://github.com/yutokure/New-Renju/issues/12) | C | 対象外 | 定石名データとAI選択の非統合 | 表示専用であることを説明。棋力改修しない |

未再現事項を確定バグとして扱わない。ゲート終了時にPR、検証結果、残件を対応記録へ記載する。
