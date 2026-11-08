# 凍結ワーカーのホスト環境診断

## 結果: CHANGES REQUESTED（配布版未認定）

ローカルPyInstaller6.13.0 onedirビルドは成功した。ソース実行と作業ディレクトリ内requestに対する凍結workerの中央着手返却は成功。一方、このホストの `%TEMP%` 配下に作ったrequestを使う凍結workerは結果ファイルを書けず、起動例外ファイルもPermission deniedになった。

この失敗は単なる探索期限超過やVery Hard固有ロジックではなく、Easyのworker起動でも発生した。Pythonソースの同じファイルプロトコルは成功する。512MiB凍結起動失敗も観測し1024MiB allowanceを分離したが、それだけでTEMP書込みの問題は解消しなかった。

旧起動フローはGUIスタック読込後にworker dispatchし、起動例外がモーダルダイアログで残る可能性があった。最終ソースはworkerをGUI import前にdispatchし、起動エラーファイルを書けない場合も静かにexit1する。最終修正後の配布物を完全に再ビルド/再検証したという主張はしていない。

## Windows権限調査

権限診断skillを、当該disposable TEMPサブフォルダを境界として通常ユーザー・非昇格full-accessで実行。結果 **NOT_THIS_CLASS、変更0、復元不要、nextAction stop**。ユーザーのFullControl/所有者設定でこの診断対象の欠陥は認められず、foreign package grantもなかった。したがって追加の権限修復を停止し、手動権限変更・所有者変更・広範囲Temp修復は一切行っていない。

診断記録はホスト固有の識別情報を含むためGitの成果物から除外しローカルに保持。これはアプリのWindows一般環境で必ず失敗する証拠でも、製品実装が必ず正しい証拠でもない。別の通常ユーザー実行環境/許可された一時領域での再現性、起動トークン、セキュリティ製品・実行ポリシー等の切り分けが必要。検証未合格をパス扱いしない。

## 再現コマンド

```text
python -m PyInstaller --noconfirm New-Renju.spec
python -B -m benchmarks.frozen_smoke dist/New-Renju/New-Renju.exe
```

現在のテストはdisposable childだけを停止し、エラーが出た他のアプリ/プロセスを終了しない。mainへのマージやリリース配布は承認待ちのまま。
