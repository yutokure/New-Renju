# Gomoku 2.0 ゲート別Issue台帳

初期main: `edc95cc`。G01→G05の直列受入。棋力・探索・評価関数は今回変更しない。

| Issue | 分類 | ゲート | 内容 | リリースへの影響 |
|---|---|---|---|---|
| [#11](https://github.com/yutokure/New-Renju/issues/11) | A/B | G01 | 棋譜の意味検証・一括適用 | 解決必須 |
| [#14](https://github.com/yutokure/New-Renju/issues/14) | A/B | G01 | 保存の直接上書き・衝突・通知 | 解決必須 |
| [#5](https://github.com/yutokure/New-Renju/issues/5) | B | G05 | Windows凍結ワーカーの既定通信領域 | 実exeと展開ZIPで実証的に解消必須 |
| [#13](https://github.com/yutokure/New-Renju/issues/13) | A | G04 | 研究値の意味・表示 | 最新mainはHard staticを明示済み。追加確認後判断 |
| [#9](https://github.com/yutokure/New-Renju/issues/9) | C | G04 | 深い禁手再帰のUNKNOWNと手動再試行 | UNKNOWNを誤判定へ変換せず、制限と操作を説明 |
| [#10](https://github.com/yutokure/New-Renju/issues/10) | C | G05 | 非WindowsのOSメモリ強制上限 | 正式配布対象はWindows。非Windows保証なしを明示 |
| [#3](https://github.com/yutokure/New-Renju/issues/3) | C | 対象外 | Hard棋力非退行の独立証拠不足 | 既知制限。普遍的な棋力改善を主張しない |
| [#4](https://github.com/yutokure/New-Renju/issues/4) | C | 対象外 | Hard候補絞り込みの探索地平 | 既知制限。探索改修しない |
| [#6](https://github.com/yutokure/New-Renju/issues/6) | C | 対象外 | Very Hard独立コーパス不足 | 既知制限。普遍的な棋力改善を主張しない |
| [#7](https://github.com/yutokure/New-Renju/issues/7) | C | 対象外 | VCF/VCTの固定予算 | 既知制限。探索改修しない |
| [#8](https://github.com/yutokure/New-Renju/issues/8) | C | 対象外 | Very Hard長連窓評価 | 既知制限。評価関数改修しない |
| [#12](https://github.com/yutokure/New-Renju/issues/12) | C | 対象外 | 定石名データとAI選択の非統合 | 表示専用であることを説明。棋力改修しない |

未再現事項を確定バグとして扱わない。ゲート終了時にPR、検証結果、残件を対応記録へ記載する。
