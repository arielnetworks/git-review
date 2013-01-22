=====================
 git-review について
=====================

`Review Board <http://www.reviewboard.org/>`_ にレビューを投稿するときに定型として入れる情報を取得するのがめんどうだったので適当にラップするためのもの。

やっていることは git log して取ってきた最新のコミットの diff から情報を拾ってきて Review Board に登録するだけ。

設定するもの
============

() 内は post-review のオプション

- trac のチケット番号 (--bugs-closed)
- trac のチケット概要を取得して Review のタイトルに (--summary)
- チケットに対応する Review が存在していたら上書き (--review-request-id)
- コミットメッセージから概要を設定 (--description)
- デフォルトのレビュー依頼対象を設定 (--target-people/--target-group)


必要なもの
==========

- RBTools(http://pypi.python.org/pypi/RBTools/)
- git


セットアップ
============

RBTools と git は予め入れておく

.git/config に以下のような設定を追記。
trac の設定は、書かなければ反映されない。

::

  [reviewboard]
          # reviewboard の URL (必須)
          url = http://path/to/reviewboard

          # review を依頼するグループ
          group = framework

  [trac]
          # trac の URL (オプション)
          url = http://path/to/trac
          # trac の realm
          realm = Trac login
          # ユーザ名とパスワード
          user = tracuser
          password = *********


使い方
======

git review コマンドを対象の git リポジトリで実行すると Review Board に Review が作られる。








