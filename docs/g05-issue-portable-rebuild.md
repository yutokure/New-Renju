## 根本原因
ポータブル標準化により開発dist内exeが保存した棋譜もexe隣へ存在する。build_release.pyはruntime data混入検査より先にPyInstaller --noconfirmを起動し、COLLECTが既存distフォルダを置換するため、その棋譜を削除し得る。後段guardだけでは保護できない。

## 再現・期待と実際
開発dist/Gomoku-2.0 exeでSaveし、同じ場所へ再ビルドする。期待: ユーザーデータがある既存出力はビルド前に拒否して保護。実際: PyInstallerが先に出力を置換しguardでは検知不能。

## 根拠・影響
G05 portable再開の内部レビューで発見。tools/build_release.pyのPyInstaller呼出と後段runtime guardの順序。ローカル開発／再ビルド時、通常ゲームプレイには影響しない。P1・分類A/B、受入前に解消。

## 方針・受入条件
PyInstallerより前に既存出力のgomoku_save_*.jsonまたはworkersを検知してfail closed。後段payload検査も維持。出力を無断移動／削除せずバックアップ指示。故障注入テストでPyInstaller未起動・棋譜bytes不変を検証。関連PR #27。
