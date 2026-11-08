# G05 製品化・Windows配布 検証記録（進行中）

開始main `d028f5f`。G01 #15、G02 #20、G03 #22、G04 #24はmainへ順次マージ済み。
判定: **CHANGES REQUESTED**。既定プロファイルの配布阻害#5が2修正サイクル後も未解消のため正式公開を停止。正式Releaseは未公開、タグ未作成。ビルド成功だけをPASSにしない。G05はdraft PRへ保存しmainへマージしない。

## 製品情報・方針
app_info.pyへ製品名Gomoku 2.0、表示2.0、内部2.0.0、v2.0.0、exe/ZIP名を集約。Aboutとタイトルバー・メニュー・Windows版情報を統一。onedirと全依存を同梱し、ユーザー向け説明／マニュアル／ノートを分離。
既定workerをユーザー別LocalAppData/Gomoku2/workers、凍結保存をLocalAppData/Gomoku2/Savesへ。source保存はcwd維持。権限不足で他領域に黙って切り替えず、ACL・所有者・セキュリティ設定の変更はしない。

## 発見・対応中
- #5: LocalAppDataへの変更だけでは実exeのStartが停止。診断専用runtime hookのfaulthandlerでPython3.12 tempfile.mkdtemp→os.mkdir(mode0700)での繰返しを特定（tempfile.py:379–398）。Windowsでは親がaccess(W_OK)ならPermissionErrorを多数回retryする。worker専用UUID子dirを通常mkdirで作り、既存ユーザー親のACLを継承する方式へ変更。衝突3回まで、権限エラー即失敗。システムACL等は一切変更しない。再ビルド後もGUI保存到達待ち失敗のため原因切分けを継続し、PASSとはしない。
- #25: 同梱権利文書不足。アプリMIT、Python/NumPy実環境原文、Pygame2.5.2のLGPLとnative依存notices、PyInstaller例外条件、Fontna公式配布のM+原文と出典を収集。フォントは既存V2バイナリを維持し埋込2019年copyrightも保存。取得したlegacy zipが同じV2バイナリとは主張しない。
- #26: request準備・close/reap・Game/mainの例外でcleanupが中断。各タスクを個別回収し、失敗所有権と元例外を保持、全runnerへ試行、app所有保留runnerを再回収、pygame.quitをfinallyへ。

## 実行済み
- G05対象109 passed / 4.50s（パス・identity・request書込失敗・二次cleanup失敗・全runner処理・main例外finally、adapter旧回帰）。
- PyInstaller6.13.0 / hooks2025.3 / Python3.12.3 / Pygame2.5.2 / NumPy1.26.3 / Windows11 build26300 x64で開発onedirビルド成功。
- 実exeのProductName=Gomoku 2.0、ProductVersion/FileVersion=2.0.0確認。
- 実exeのメニューとSettings表示、難易度変更を画像確認。初回画像取得はSetForegroundWindowの64bitHWND型未定義で別画面を撮影していたため、テストharness型を訂正。取得画像をアプリ証拠として誤用しない。
- GUI保存到達待ちで失敗した2回と、diagnostic traceback取得、bounded storage変更後の失敗を記録。未確認の対局／保存を成功扱いにしない。

## 最終検証と判断
- ソース全体668 passed / 30.38s。内部レビュー後の最後の限定修正（startup finally、readonly save list、Windows factory試験限定、GUI cleanupをnonblocking reap）後の対象113 passed / 4.43s、diff --check合格。
- controlled profileで4難易度すべての人間黒→実AI白応手、保存・履歴・現在復帰・ロード・Menu/Quit exit0とworker残留なしを確認。人間同士connect3終局→再戦空棋譜、別probeでAI先手→人間→AI、AI同士も確認。詳細 docs/g05-controlled-profile-evidence.json。日本語・空白pathと異なるTEMPを使用。ただしLocalAppDataを検証専用workspaceへ変更し親dirを事前作成した限定条件であり、通常ユーザー／既定プロファイル合格ではない。
- GUI試験のPostMessageキーがSDLへ届かずMenuへ遷移できなかった箇所はpointer操作へ訂正。ショートカットの実exe検証済みとはしない。初回matrixのAI-firstタイミングassert失敗は別probeで追加確認し、matrix全体が一度でPASSしたとは記載しない。
- #25はFreeSansの実配布原文とsource対応の最終確認が残りOPEN。追加SDL_ttf/OpenSSLの原文を収集しただけで完全な権利対応と判定しない。
- 内部レビュー: **CHANGES REQUESTED**。#5は未解消、#25はcoverage未完。#26の例外処理は改善したが正式配布の最終実証待ち。
- Release ZIPは生成せず、SHA-256配布チェックサム／v2.0.0タグ／Release URLは存在しない。開発onedirのBUILD_INFOはdirtyと明示され正式成果物ではない。展開後ZIP・公開ダウンロード後の実行確認は未実施。

## 再開に必要な条件
既定の通常Windowsユーザートークンでユーザー領域へ安全に書込める検証環境（ACL/セキュリティ変更を行わない）を確保し、#5を実exeの通常起動で再検証する。FreeSansを含む実成果物対noticesを完了し、G05 PRを受入後に最終mainからclean build/ZIPを作成。ZIP展開後の全必須確認、タグ重複確認、正式公開、公開ZIP再取得のSHA一致と実行まで完了して初めてPASSとする。
