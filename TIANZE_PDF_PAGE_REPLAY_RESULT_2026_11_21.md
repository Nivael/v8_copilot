# 天择已审页从PDF直接重提取与重渲染

补上前轮明确保留的页文本/图像来源重放限制。verify_tianze_pdf_page.py直接核保存官方PDF字节SHA/长度，使用PDFium打开核176页，从第19页重新提取原文本并按原1.4倍比例渲染。当前文字与已审文本完全一致，PNG字节与原已审图像完全一致，报告TIANZE_PDF_PAGE_REPLAY_2026_11_21.json。

只读命令：uv run --no-project --with pypdfium2 --with pillow python verify_tianze_pdf_page.py。不写源件或页面；渲染不同即拒绝并要求核版本，不能自动覆盖旧证据。

两项检查通过：实际PDF页重放一致；替换提取文本并重新计算摘要仍不能通过PDF原文核对。测试命令：uv run --no-project --with pypdfium2 --with pillow --with pytest python -m pytest tests/test_tianze_pdf_page_replay.py -q。无新网络来源、研究或独立验证，不改前端，未重复页面/构建。

检查范围仅第19页，不扩为176页全文审读，不认证5月30日撤销原公告已取得官方字节。已阅页来源链现更强，但后续报告日和原实施日的区别、8原公告缺口保持。后续资料改变时先运行原件→页→投影核验，不凭元数据一致就发布。
