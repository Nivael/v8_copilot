# v8 QuestionCard Contract v0

W1 单写的 QuestionCard 产品对象契约。它承接用户问题、答案缺口和人审问题，
但不写入 evidence library。

`status=needs_data` 时必须同时提供 `needs_data[]` 和正式 `debt_ref`；
`answerable`、`needs_data`、`needs_review` 分别进入答案引擎、数据债和人审生命周期。
