## 根本原因
ワーカー起動前のrequest書込がPopen例外時のcleanup保護外。AsyncAI.close/reapで個別のwait・Jobハンドルclose・一時ディレクトリcleanup例外が後続の回収を中断し、Game.closeも最初の例外で残るrunnerを飛ばす。main終了もfinallyでpygame終了を保証していない。

## 条件・再現
request書込PermissionError、子processのwaitエラー、Job CloseHandle／一時dir削除エラーを故障注入。先頭タスクのcleanup失敗時に次タスクが処理されない。

## 期待と実際
期待: すべての所有タスクへ有限時間の停止・回収を試み、失敗所有権を保持して後で再試行し、正常回収したと偽らない。実際: 初回例外で後続処理を中断し、GUIオブジェクト破棄後に回収所有権を失い得る。

## 根拠・影響
main d028f5f のai_async.py:start/close/reap、game.py:close、main.py末尾。G05内部レビューで発見。通常終了・異常終了・権限エラー時、全難易度と解析／判定workerに影響。

## 推奨対応・受入条件
個別タスクごとに例外分離して兄弟を回収。未回収の所有権とエラーを保持。Gameは全runnerを試み、失敗はapp所有の保留リストで明示再試行。mainはfinallyでpygame終了。request書込失敗で所有tempを明示cleanup。故障注入と実exe終了後に所有child／tempが残らないことを確認。分類A/B、P1、リリース阻害。関連PR: G05作成時追記。
