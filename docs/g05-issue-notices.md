## 根本原因
既存PyInstaller設定はフォント・依存バイナリを配布する一方、アプリMIT LICENSEとフォント／Pygame/SDL等の第三者条件を明示同梱していない。fonts配下はOTFのみで出典・権利表示が不足。

## 再現・根拠
開始main d028f5f のNew-Renju.spec:datasはjosekiとfontsのみ、fontsにはYasashisaGothicBold-V2.otfのみ。アプリLICENSEは再配布時の文書保持を要求。Fontna公式 https://www.fontna.com/blog/yasashisagothic_b.html はM+条件・Fontna著作権・組込利用を説明し同梱LICENSE_E/J参照を求める。Pygameのwheelも別途LGPL等のnoticesを要する。

## 期待・実際・影響
期待: 配布ZIPにMITと全同梱資産の権利条件／出典が含まれる。実際: 明示的収集がない。Windows正式配布の全利用者。G05で発見。

## 対応・受入条件
実際のビルド依存版に対応するPython/Pygame/SDL/NumPy等とフォントの原文条件を取得し出典を記録して同梱。フォントバイナリを無関係な条件でMIT扱いしない。ZIP内の権利文書を確認。分類A/B、P1、リリース阻害（解消するまで公開しない）。関連PR: G05作成時追記。
