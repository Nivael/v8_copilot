# 两个停牌案例：成交日期与收盘交叉核对

本轮新增龙元、岭南的腾讯与东方财富报价核对；每个渠道各核原始及前复权，共8份有效响应、908个渠道收盘点，对应227个实际成交证券日。报价响应冻结在本地，链接可能变化，不能把渠道数量当独立案例数或底层供数独立证明。行情覆盖2026-05-06至2026-11-06。

## 结论与阅读变化

- 龙元120个实际成交日、6个无成交日期；岭南107个实际成交日、19个无成交日期。四组报价的实际日期集合及收盘分币数值与原缓存一致，停牌日未补为成交。
- 共同2026-07-03至2026-11-06为84个市场交易日。龙元起点停牌，岭南期末停牌，个股实际成交收益都留空；旧参考价比值另存。
- 龙元实际成交另窗2026-07-02至11-06：85日，+30.39%；同窗大盘−19.78%、ST参考−8.76%。岭南实际另窗2026-07-03至10-12：65日，−57.94%；同窗大盘−14.26%、ST参考−3.54%。不同日期窗口不能替换84日共同比较，也不能拿共同大盘数计算另窗超额。
- 停牌案例阅读区先显示核验结论，原始报价、无成交日期、同窗行情及1/5/20日选择按需展开。龙元7月10日后5日+20.54%及8月28日后5日−4.76%等原公告窗口精确保留。
- 价格一致未改变公司程序判断：龙元结果已确认、清算仅见办理安排，完成回执未纳入；岭南已核事先告知，最终决定和摘牌文件未纳入。不从报价推公告净因果。

## 来源、复算与保留

复用378份原提供商缓存响应，逐份验SHA并重建两公司126日原始收盘、成交量、复权因子及停牌记录；没有新提供商查询。两公司在所核区间复权因子未变化，当前前复权回看不当作当时可成交报价。独立脚本重算20个可用窗口（含共同/另窗和公告窗口），背景或不足交易日的窗口留空。

首次8请求中龙元东方财富两请求断开，各一次补试成功；首次失败记录、成功原响应及SHA均保留，无未解决请求。原比较、日路径、名单、全部旧主题、原始行情逐值不变。正文仍33公司101文件、101条原事实、100阅读事项；固定成交端点覆盖146/150，不因新增核价改变。无经验晋级。

| 对象/报价口径 | 收盘点 | 冻结响应SHA256及来源 |
|---|---:|---|
| 岭南 tencent_raw | 107 | [eca63c4413228ff0de47ab9bd5a61d3b0a6edb16fe3ece0b0ed85115697240cc](https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz002717%2Cday%2C2026-05-06%2C2026-11-06%2C640%2C) |
| 岭南 tencent_qfq | 107 | [60ae43989d246c0b113a2a98a4158d45d9e7906aa215bd1da87071e08c7d57a0](https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz002717%2Cday%2C2026-05-06%2C2026-11-06%2C640%2Cqfq) |
| 岭南 eastmoney_raw | 107 | [b6f19628422028a3162b8f31524438ca6a9dc7aeb6f7581110bcda7f8533e0ce](https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.002717&klt=101&fqt=0&beg=20260506&end=20261106&fields1=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6&fields2=f51%2Cf52%2Cf53%2Cf54%2Cf55%2Cf56%2Cf57%2Cf58%2Cf59%2Cf60%2Cf61) |
| 岭南 eastmoney_qfq | 107 | [a819e3d82e1408b586428b1b51af1d3ba6f7725f0119f320d45cc97d28b37fd9](https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.002717&klt=101&fqt=1&beg=20260506&end=20261106&fields1=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6&fields2=f51%2Cf52%2Cf53%2Cf54%2Cf55%2Cf56%2Cf57%2Cf58%2Cf59%2Cf60%2Cf61) |
| 龙元 tencent_raw | 120 | [f1425d960b986518cef98cc9ff31d7ffa67a23da1ca705c5649af28661e23de8](https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600491%2Cday%2C2026-05-06%2C2026-11-06%2C640%2C) |
| 龙元 tencent_qfq | 120 | [b4dc75340bd9acce885fc407c152fdd1c99b33532ed402c40715d4d990098e49](https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600491%2Cday%2C2026-05-06%2C2026-11-06%2C640%2Cqfq) |
| 龙元 eastmoney_raw | 120 | [634eead40e85f6fca524380cfa6604c2c266bb69f1f0df4d5640572fc3693dfd](https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.600491&klt=101&fqt=0&beg=20260506&end=20261106&fields1=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6&fields2=f51%2Cf52%2Cf53%2Cf54%2Cf55%2Cf56%2Cf57%2Cf58%2Cf59%2Cf60%2Cf61) |
| 龙元 eastmoney_qfq | 120 | [abbb8e6bd4986d7ac4817360da36ce9a48b0e080ed89757e82c061ef83b4bd97](https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.600491&klt=101&fqt=1&beg=20260506&end=20261106&fields1=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6&fields2=f51%2Cf52%2Cf53%2Cf54%2Cf55%2Cf56%2Cf57%2Cf58%2Cf59%2Cf60%2Cf61) |

## 验收与续接

后端112项、前端454项通过，构建及静态检查通过。浏览器已核两公司证据展开、1/5/20日切换、共同/另窗分离、截止日及报价来源。研究运行账本151→152，旧记录及经验登记精确保留，accepted10/candidate3。

下一轮优先沿官方目录补龙元明确清算付款/过户完成证据与岭南最终决定/摘牌文件；随后补期初及沪市历史名单缺口。已一致的报价不无目的重复抓取。仍未认证全体ST行情、开高低收全部字段、底层供数独立性及净因果，多个独立案例检验才可形成条件性经验。

本地留档：`out/st-halt-price-crosscheck-20261109/`，包含plan、原响应/重试、study-input、independent-verification、validation、record、ledger-proof、activation、live-check、goal-audit、进度与续接。敏感原提供商配置不入库。

快照：`0ea541c45aca0058d92f5855543ac24cceb4b9bde79506872bcdec934793aa1f`。
输入：`734920cd281ef8ff28bcd6051b8312b7640db736d74a8da7a64197d400db24ec`。
研究记录：`RUN-9D1716DA65604DE781A95769`。父轮草稿PR32，本轮独立分支提交草稿，不合并。
