# 制度前后摘帽：首日、后续和市场环境（2026-11-09）

首日上涨没有保证之后继续上涨。这轮比较已核的制度前37次、制度后12次撤销警示事件，不把它称全体ST的摘帽成功率，也不把两组当随机的新旧制度实验。

## 同一个“摘帽后”，先问从何日起算

前组37只复牌首日25涨12跌；后组12只5涨7跌。首日价格从停牌前最后实际收盘至复牌收盘，大盘和ST也按相同两端比较，包含其间停牌市场日。

本页默认从复牌收盘之后看20个市场日，排除复牌跳变：

|事件组|原组|完整可核|涨/跌|个股中位数|个股简单均值|同窗大盘均值|同窗ST均值|跑赢ST|
|---|---:|---:|---|---:|---:|---:|---:|---:|
|制度前事件|37|36|10/26|−11.93%|−2.65%|−5.35%|−8.59%|14/36|
|制度后事件|12|10|5/5|+1.14%|−0.03%|+1.22%|+5.44%|4/10|

前组少数大涨拉高均值，例如艾艾复牌后20市场日+132.81%，同窗大盘−13.27%、ST参考−4.46%；这段跨过7月6日。中位数与多数涨跌仍偏弱，不能用平均相对强推大多数上涨。前组可核的25家复牌先涨中18家随后20日下跌；这是同一事件的路径，不是额外独立验证次数。

原12只研究从停牌前收盘起算20市场日，6/10上涨；新默认从复牌收盘后再20日，5/10上涨。起点、终点都不同，不能把全部差额称首日贡献。宁科原口径+2.45%，新口径−6.74%；原结果及其价格构造均保留在折叠区，不覆盖旧判断。

## 不能漏掉的时期与样本差异

前组36个20日窗口，22个跨过7月6日。事件发生在制度前，不等于后窗全部处在旧制度。前组完全在7月6日前结束的子样本只剩14只，5涨9跌、中位数−11.33%；40日完全旧制度窗口为0，保留“不可算”，不填零。

前组36窗中30窗大盘跌，后组10窗中4窗大盘跌；两组市场均值分别−5.35%和+1.22%，ST参考分别−8.59%和+5.44%。这些是同一批个股各自日期的对照，不是共同日期组合。窗口重叠、公司构成和选择范围不同，同一市场冲击不算多次独立试验。相对大盘/ST的百分点差不是已扣除风险的独立收益或公告净贡献；没有把规则影响份额分摊出来。

前组来自5月6日在册、7月3日前移出的37家公司；后组来自7月3日固定150中后来撤销的12家公司，两组名单选择不同。前37撤销公告均明示后10%，28明确5%改10%、9只写后10%；后12仍10%，机制差异保留，但不能直接等于收益因果。

## 来源与不纳入项

剔除前组5份发行人PDF镜像、仅保留直接官方PDF后，20日31只中9涨22跌、中位数−10.81%；多数下跌的描述仍在，不能消除时期或公司选择偏差。前组镜像官方原字节仍待补，未升级为直接官方认证。

默认20日华微600360因6月8日公司行动/因子变化与直接前复权端点差异待核，不进入主统计；后组绝味603517、四通603838观察期未满，未缩窗或填零。5日从复牌收盘起算时，艾艾终点无实际成交，保留缺口。40日荣控000668（7月8日）、华微600360（6月8日）、艾艾603580（8月14日）的公司行动构造待原件解释。不能把公告目录、因子跳变或别家公司解释代替各自原件。

绝味已有三份公司行动原件与同因子重建支持，明确复用到本公司的5日窗口；未把直接前复权端点差异改成直接一致，也未推广到其他公司。

如要求同一公司同时有完整的前20市场日，前组只剩22家、后组10家；40日前组前史不足，配对为0。历史报价从5月6日开始，不能缩短前窗冒充等长比较。页面同时显示主样本、纯旧窗口、仅官方源、完整前后配对，分母不互换。

## 实现与核验

新增一个问题入口，保留11个原专题；窗口可选5/20/40日，起点可选停牌前或复牌收盘，范围可选全部/不跨规/仅官方来源。先给分布与市场解释，再展开均值、缺口、公司端点与公告。艾艾作为极端上涨反例默认显示，华微待核、绝味未满和已有重建、原尚镜像都可选；旧12只比较折叠保留。

仅复用98份既有腾讯原始/前复权响应12212报价点，无新行情提供方、报价或公告网络请求；同一渠道两口径不作底层完全独立认证。旧输入各键、每日价格/名单/路径/前后比较、全部旧主题和正文均精确不变，正文仍89公司199来源文档193记录192事项。没有新增或晋级经验方法，也不修改原问或生产库。

独立读取冻结响应并校验身份与SHA，逐窗核市场日边界、实际成交、因子变化及收益，复算379个具有成交端点的前后/后续窗口（371支持、8待因子解释），另核49个复牌首日；缺前史、后窗不足与停牌端点保留。全量前后统计、纯旧窗口、仅官方源、市场条件分组与路径计数均核；441后台相关测试、542前端测试、构建和静态检查通过。实际页面核5/20/40切换、40日旧组为空、镜像排除、华微/绝味与原12结果，不只核静态截图。

研究 `RUN-CD17AC3DC2004FFB8287B5E8`；快照 `d7bbf361ad9489937fe01a8dadc0e7055f04e7170f5e8dac418ec8af53435338`。账本172→173，旧运行与经验登记摘要精确保持。草稿PR叠在 #52，未合并。

## 49个事件的来源与可核20日

|事件组|当时公司|代码|撤销生效|复牌后20日|本轮层级|公告|
|---|---|---|---|---|---|---|
|前|ST张家界|000430|2026-05-18|+1.66%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-05-15/6f402615-fa1b-4745-94e2-b1fabbe5fe99.PDF)|
|前|*ST生物|000504|2026-06-12|-8.37%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-06-11/f15b063c-f7d3-428b-b1d9-6fd3e7f7d7b7.PDF)|
|前|*ST四环|000518|2026-05-20|-7.92%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-05-19/0a94edec-c6d1-4502-97ee-74b71a21ff16.PDF)|
|前|*ST宝实|000595|2026-07-02|-13.05%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-07-01/af60f941-607b-446d-a2c5-2035a309444b.PDF)|
|前|*ST阳光|000608|2026-05-21|+91.67%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-05-20/494593f7-f4de-41e9-a27e-4d8205a7b3ce.PDF)|
|前|*ST金科|000656|2026-07-02|+0.85%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-07-01/7d2b1820-3995-4358-80f0-143b49523f8f.PDF)|
|前|*ST荣控|000668|2026-06-03|+10.58%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-06-02/f0fb2ad4-bd83-452e-8d6e-9cf4af80bd03.PDF)|
|前|*ST亚太|000691|2026-06-01|+24.03%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-05-29/973b027f-b690-42c1-bb3e-1c9c5dfe5e8a.PDF)|
|前|*ST中地|000736|2026-06-03|-27.51%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-06-02/3aee3bf1-ddca-4d9f-8a83-6e3a02b0a605.PDF)|
|前|ST景峰|000908|2026-06-12|+3.82%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-06-11/afa5801d-da96-42b2-a6a7-4defa6eb5cbb.PDF)|
|前|*ST兰黄|000929|2026-06-16|-14.84%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-06-13/2ee403da-7393-4d54-859d-0a73c712f27d.PDF)|
|前|*ST中基|000972|2026-06-29|+0.91%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-06-26/a5a6e55a-09db-4068-b784-f2e621a6f332.PDF)|
|前|*ST铖昌|001270|2026-05-20|-7.25%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-05-19/7dcd926a-5a98-4b8b-b5cb-185bc679a713.PDF)|
|前|*ST宝鹰|002047|2026-05-21|-16.57%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-05-20/12450d89-55c4-48a3-a21a-07aaab9f2290.PDF)|
|前|*ST威尔|002058|2026-06-15|-19.69%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-06-12/f1cc9a47-bae9-468b-81f3-773aaf9b0481.PDF)|
|前|*ST星光|002076|2026-06-22|-27.95%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-06-18/0cab5cc3-cb42-4879-bc17-2ca8afc67645.PDF)|
|前|*ST交投|002200|2026-06-03|-15.80%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-06-02/5d954840-b0be-4dc9-8b52-0ff7f104936f.PDF)|
|前|*ST智胜|002253|2026-06-26|-22.54%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-06-25/b39db85c-196b-48e0-8bc7-04ec1070cfcf.PDF)|
|前|*ST宇顺|002289|2026-06-26|-28.92%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-06-25/af9423d8-f7fe-42f0-a0a5-34683d069519.PDF)|
|前|*ST辉丰|002496|2026-06-18|-10.81%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-06-17/7ffd83e6-05d9-4295-b671-f0997a558873.PDF)|
|前|*ST海源|002529|2026-06-15|-14.58%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-06-12/03482648-0613-4da6-a5f7-8ee83ee8ef2c.PDF)|
|前|*ST双成|002693|2026-05-25|-23.00%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-05-22/78ec81ea-8021-413d-8756-64127cd390b9.PDF)|
|前|*ST金比|002762|2026-06-22|-17.67%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-06-18/98bbbf8e-dd6d-4d6f-8c24-1752de46dbfb.PDF)|
|前|*ST高斯|002848|2026-06-02|-14.75%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-05-30/1d87a7b8-3586-49db-b322-ad57b7527815.PDF)|
|前|*ST绿康|002868|2026-05-13|-37.13%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-05-12/1fcb70d5-aa94-4444-b727-e4029dec1f91.PDF)|
|前|*ST声迅|003004|2026-05-20|+46.84%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-05-19/baf80594-70c5-49d7-bae9-60d15ff4b2d9.PDF)|
|前|*ST传智|003032|2026-06-11|-21.92%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-06-10/f9b610ea-5a04-468b-9a53-35b67a9c5d8e.PDF)|
|前|*ST返利|600228|2026-06-09|-1.08%|官方PDF|[所引公告](https://static.cninfo.com.cn/finalpage/2026-06-06/1225354167.PDF)|
|前|*ST华微|600360|2026-05-20|公司行动构造待核|官方PDF|[所引公告](https://static.cninfo.com.cn/finalpage/2026-05-19/1225312619.PDF)|
|前|*ST新潮|600777|2026-06-23|-25.93%|发行人PDF镜像，原字节待补|[所引公告](http://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESH_STOCK/2026/2026-6/2026-06-19/12401725.PDF)|
|前|*ST大晟|600892|2026-07-01|-8.86%|官方PDF|[所引公告](https://static.cninfo.com.cn/finalpage/2026-06-30/1225397243.PDF)|
|前|*ST立航|603261|2026-06-16|+42.51%|发行人PDF镜像，原字节待补|[所引公告](http://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESH_STOCK/2026/2026-6/2026-06-13/12391668.PDF)|
|前|*ST亚振|603389|2026-07-01|-24.37%|发行人PDF镜像，原字节待补|[所引公告](http://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESH_STOCK/2026/2026-6/2026-06-30/12419797.PDF)|
|前|ST通脉|603559|2026-07-02|-3.22%|官方PDF|[所引公告](https://static.cninfo.com.cn/finalpage/2026-07-01/1225400711.PDF)|
|前|*ST艾艾|603580|2026-07-01|+132.81%|官方PDF|[所引公告](https://static.cninfo.com.cn/finalpage/2026-06-30/1225397222.PDF)|
|前|*ST天择|603721|2026-06-02|-26.61%|发行人PDF镜像，原字节待补|[所引公告](http://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESH_STOCK/2026/2026-5/2026-05-30/12361633.PDF)|
|前|*ST原尚|603813|2026-06-16|-10.73%|发行人PDF镜像，原字节待补|[所引公告](http://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESH_STOCK/2026/2026-6/2026-06-13/12390955.PDF)|
|后|京蓝科技|000711|2026-08-31|-20.54%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-08-28/c338c029-b409-4145-83f9-09dccda9d09e.PDF#page=1)|
|后|神雾节能|000820|2026-07-30|+13.12%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-07-29/30a864d9-fc5e-4adc-951e-665360e3af62.PDF#page=1)|
|后|德豪润达|002005|2026-07-14|-8.80%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-07-11/b33de5b6-7427-4e7c-ab40-29d7bff78195.PDF#page=1)|
|后|东晶电子|002199|2026-07-23|+13.14%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-07-22/fc9df353-bb5a-49ac-82ea-820381a724cf.PDF#page=1)|
|后|大立科技|002214|2026-08-05|+9.02%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-08-04/d7bb9c52-ce95-4147-bc1d-12c57efcf3d4.PDF#page=1)|
|后|围海股份|002586|2026-08-31|-13.37%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-08-28/e595f7d5-abad-4b0c-8e64-73fc1d1e1ad0.PDF#page=1)|
|后|摩登大道|002656|2026-07-20|+11.11%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-07-17/d2dba6de-2b16-42c8-b0ea-741712cf5377.PDF#page=1)|
|后|东易日盛|002713|2026-07-20|+13.51%|官方PDF|[所引公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-07-17/ab1edd1b-d361-4416-8ea5-a2cd4162090d.PDF#page=1)|
|后|宁科生物|600165|2026-08-26|-6.74%|官方PDF|[所引公告](https://static.cninfo.com.cn/finalpage/2026-08-25/1225497764.PDF#page=1)|
|后|长园集团|600525|2026-08-26|-10.73%|官方PDF|[所引公告](https://static.cninfo.com.cn/finalpage/2026-08-25/1225499508.PDF#page=1)|
|后|绝味食品|603517|2026-10-20|后窗未满|官方PDF|[所引公告](https://static.cninfo.com.cn/finalpage/2026-10-19/1225609996.PDF#page=1)|
|后|四通股份|603838|2026-10-20|后窗未满|官方PDF|[所引公告](https://static.cninfo.com.cn/finalpage/2026-10-17/1225608268.PDF#page=1)|

## 下一步与推翻条件

先补华微6月8日、荣控7月8日、艾艾8月14日前后的公司行动原件和参考价构造，逐公司核数字与报价；不借绝味的原件、分红或重建规则给其他公司认证。新交易日到来再补未满窗。初始完整官方名单、5镜像对应官方PDF原字节和沪科日期差异仍留档；没有新证据时不重复采集。正式更正、成交日期/状态变化、公司行动不符或镜像与原件冲突会推翻对应支持，重算受影响窗口。持续goal保持active。
