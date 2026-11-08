# G03 描画・性能・視覚情報 受入記録

開始main `0715b02`（G02 PR #20マージ後）。関連[#17](https://github.com/yutokure/New-Renju/issues/17)。判定: **PASS**（対象範囲）。全体623 passed / 32.10s、diff --check合格。

## 変更範囲
- TextPopup更新を1ループへ統合。最後のPopup削除、Telop・着手・点滅アニメーション終了時もdirtyを立てて最終画面を再描画。
- Telopはdirty再描画内で一度だけ合成し、同じ背景へ半透明要素を重ね続けない。終局ボタンの重複描画を除去。
- 履歴移動でライブの着手／脅威アニメーション・Popup・Telop・無効クリック・旧研究値を破棄。描画側も履歴へライブ石を出さない。last_moveをtuple化してマーカー比較を統一。
- 研究が未完overlayを中断したらその予約キーを破棄し、研究終了後に再queue可能にする。完成したoverlayは保持。研究中に共有runnerでoverlayを奪わない。
- idleでhoverが変わった場合も再描画。固定無効点Surface／終局overlay Surface、評価値・状態文字Surfaceを上限512項目で再利用。脅威線の交点と画面座標は局面キャッシュで構築。
- 再帰的合法性・正式勝敗は描画内で判定しない。AI・ルールコア変更なし。大規模renderer刷新なし。

## 検証
- 対象のピクセル／キャッシュ＋非AI入力: 21 passed / 3.43s。最終追加（30個PopupでもMenu可能、Telop不変フレームの非重複合成）を含む描画対象12 passed / 2.10s。追加テスト初回はSTATE_MENUを文字列と誤比較して1件失敗し、定数比較へ訂正して再実行した（アプリの障害ではない）。
- 着手・点滅・Telop・Popupの最終フレームと画像を比較し、古い表示が消えることを確認。
- Popup.updateが1フレーム1回、historyの偽石なし、旧研究値破棄、last_move型、cache再利用と盤面変更時再構築、hover、研究がoverlayを中断した後の再queueを検証。
- 15路・19路を直列で各200強制描画（少数の石・全空点研究値・Popup、SDL dummy）。15路: 0.760→0.688 ms/frame、19路: 1.021→0.969 ms/frame。軽量スモークで明確な悪化なし。単回測定であり一般的なFPS向上や実GPU保証とは主張しない。生結果: benchmarks/results/g03-render-before.json、g03-render-after.json。再現: `python -B -m benchmarks.render_smoke --output <path>`。

## 内部レビュー・引継ぎ
描画と正式判定の分離、dirty終了、cache文脈、例外・退行を対象限定でレビュー。脅威Popupの所有者／カスタム目数の意味、overlay部分完了時の意味を新規Issueに記録しG04へ引継ぎ。表示補助の課題であり未確認を合法・禁手・必勝に変換しない。配布・実Windows exeの最終検証はG05。
