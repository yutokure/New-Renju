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

## Clean候補ZIP受入
- source `9477f338fd92eadb33fd23e3d3f8a810a4168d46` clean build ZIPを日本語/空白pathへ新規展開。7行matrix全PASS、非管理者/noargs/exit0、全4難易度応手とsave/load/history。exe Windows ProductName=Gomoku 2.0、File/ProductVersion=2.0.0。
- 233payload filesのmanifest SHA256全一致、69notice/source filesがrepoとbyte一致。UiSans/DejaVu原文既知hash一致、FreeSans全path不在、pygame source archive/nested validator source直接アクセス同梱。sourceのみの文書リンクは正確commit URLへ変換、同梱user docs/images/licenseリンク存在。
- source `c54c9c1` ZIPでは長い棋譜名のbutton枠外描画#29を修正確認。7行一覧と通知/pageが重複しない所有HWND画像を確認、invalid JSON loadは可視拒否し既存設定を変更しない。フォルダ全体を移動後もnoargs起動・移動先exe隣保存・終了0を確認。92対象回帰合格。
- 追加の既存host ACLを持つLocalAppData内copyでは想定と異なりSaveが成功したため、read-only失敗native証拠にはしない。書込不能Saveの判定はソース故障注入として明示し、native file-obstructionのworker失敗と区別。権限・ACL変更なし。
- `.gitattributes`で第三者原文/font bytesのWindows改行変換を禁止し、将来checkoutのprovenance整合も維持。
- c54候補のnative追加probeで別cwd/TEMP、worker obstruction、異常AI子終了を再PASS。上級者明示worker rootを実exe引数で指定し、VeryHard思考中Menu→Quitで取消・終了0・指定dir/子process残留なしを確認。
- 最後のUI修正後の全回帰: **676 passed / 30.66s**、diff --check合格。
- Runtime内部レビューは指摘#28（再ビルド前保護）・文書linkを修正後ACCEPTABLE。ライセンスレビューの残条件（旧font除外／原文／対応source／最終payload）は上記展開照合で確認。範囲は実測環境に限定し法的な包括認証や全Windows環境保証とは主張しない。

状態: 配布候補の受入を確認。PR #27をmainへ反映後のclean最終build・展開ZIP再確認と公開後再取得は別段階で実施し、正式公開後の最終判定をRelease本文とPR記録へ追記する。旧CHANGES REQUESTEDは過去仕様の履歴であり、勝手に成功へ書換えない。
