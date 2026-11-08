# G05 portable仕様 再開・受入記録

2026-11-08 オーナー追加入力により「ポータブル方式（exeと同じところにデータを保存）」を標準仕様として採用。G05 PR #27を再開。旧LocalAppData方式のCHANGES REQUESTEDはG05_VALIDATION.mdに履歴として保持し、成功と書き換えない。

## 契約
- 凍結版の棋譜は`sys.executable`所在フォルダ直下の`gomoku_save_*.json`。起動cwdではない。
- ワーカーは同じフォルダの`workers/renju-ai-<uuid>`。通常ダブルクリックで引数不要。
- 書込不可は可視エラー。TEMP/LocalAppData/cwdへの黙示fallbackなし。ACL/所有者/セキュリティ変更・管理者要求なし。
- ソース保存はcwd互換、Windowsソースworkerはプロジェクト/workers。明示`--worker-directory`は既存dirへの上級者指定として維持。
- 読込はportable保存先＋旧cwdを読み取り専用で列挙。自動移動・上書きなし。
- exe単体ではなく_internalを含む全体を展開・移動する。データもフォルダと共に移動する。

## 初期検証
- portable root / cwd非依存 / _MEIPASS非依存 / 権限失敗no-spawn / 明示override / 保存と旧回帰: 95 passed / 2.44s。
- #25: FreeSans歴史binaryとpreferred sourceの対応未確認につき、収集で推測するのでなくproduction UIを許諾原文の確認できるDejaVuへ切替え、FreeSansを成果物から除外して確認する方針。棋力・探索・ルール改修なし。

## 開発exe実測（標準引数なし）
- Windows11 x64 / build26300 / 非管理者 / noargs。4難易度H→AI・保存load履歴・Menu/Quit、H-H connect3終局→再戦、AI-H、AI-AIの7行matrix全PASS。各終了0、worker子dir残留なし。保存はexe直下。
- 別cwd・日本語/空白TEMPで起動し、棋譜がexe隣へ保存されることと旧LocalAppData未作成を確認。
- 所有worker rootをファイルで遮断するとAI unavailableを可視表示し、子プロセス起動なし・誤応手なし・別領域へのfallbackなし。棋譜保存と終了は継続可。
- 直接所有AI子processを特定して強制停止し、AI unavailable・誤応手なし・終了0・回収を確認。
- 専用PrintWindowで所有HWNDを撮影。元のdesktop cropに他window混入があった画像は証拠にせず、所有window画像で再確認。
- OS share-denyでSave失敗を作るprobeはdirectory handle取得自体がWinError32で不成立。保存権限エラーのnative実証として主張しない。ACL操作は行わず、Save PermissionError/旧データ不変は故障注入試験、native file-obstructionはworker側の別条件として区別。
- 全ソース回帰675 passed / 33.88s。builder preflight#28（portableデータの無断置換防止）＋nested source doc linkは故障注入で確認。内部runtimeレビューは限定指摘の修正後ACCEPTABLE。

状態: 最終clean ZIP展開・公開後再取得の全受入まで正式PASSとはしない。
