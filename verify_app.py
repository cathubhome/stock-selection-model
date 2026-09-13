from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from streamlit.testing.v1 import AppTest

VIEWS = ["研究看板", "股票池与数据", "综合评分", "历史回测", "研究记录"]

at = AppTest.from_file("app.py", default_timeout=300)
at.run()
print("初始运行异常:", [str(e.value) for e in at.exception] or "无")

for view in VIEWS[1:]:
    at2 = AppTest.from_file("app.py", default_timeout=300)
    at2.run()
    if at2.sidebar.radio:
        at2.sidebar.radio[0].set_value(view).run()
        errors = [str(e.value) for e in at2.exception]
        print(f"{view} 异常:", errors or "无")
    else:
        print(f"{view}: 未找到侧边栏 radio")

score_page = AppTest.from_file("app.py", default_timeout=300)
score_page.run()
score_page.sidebar.radio[0].set_value("综合评分").run()
assert not any(widget.label == "选择要加入股票池的候选" for widget in score_page.multiselect)

backtest_page = AppTest.from_file("app.py", default_timeout=300)
backtest_page.run()
backtest_page.sidebar.radio[0].set_value("历史回测").run()
assert not any("未通过原因" in item.label or "限制与风险" in item.label for item in backtest_page.expander)
print("关键交互回归检查: 通过")
