# -*- coding: utf-8 -*-
import re

with open("src/components/ResearchRunsView.tsx", "r", encoding="utf-8") as f:
    rr = f.read()

# 1. 增加 runsPage 状态
target_state_point = '  const [diffLimit, setDiffLimit] = useState<number>(5);'
new_state_code = '''  const [diffLimit, setDiffLimit] = useState<number>(5);
  const [runsPage, setRunsPage] = useState<number>(1);
  const runsPageSize = 10;'''

rr = rr.replace(target_state_point, new_state_code)

# 2. 将 runs.map 改为分页切片
old_runs_map = '{runs.map((r) => {'
new_runs_map = '{runs.slice((runsPage - 1) * runsPageSize, runsPage * runsPageSize).map((r) => {'
rr = rr.replace(old_runs_map, new_runs_map)

# 3. 在表格底部插入分页控制器
old_table_close = '''            </tbody>
          </table>
        </div>
      </div>'''

new_table_close = '''            </tbody>
          </table>
        </div>

        {/* 归档实验列表分页控制器 */}
        {runs.length > runsPageSize && (
          <div className="px-4 py-3 border-t border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs bg-slate-50/50">
            <span className="text-slate-500">
              第 {runsPage} / {Math.ceil(runs.length / runsPageSize)} 页 · 共 {runs.length} 次归档实验记录 (每页 10 条)
            </span>
            <div className="flex items-center space-x-1">
              <button
                type="button"
                disabled={runsPage <= 1}
                onClick={() => setRunsPage(p => Math.max(1, p - 1))}
                className="px-2.5 py-1 rounded border border-slate-200 bg-white text-slate-600 disabled:opacity-40 hover:bg-slate-50 cursor-pointer"
              >
                上一页
              </button>
              {Array.from({ length: Math.ceil(runs.length / runsPageSize) }, (_, i) => i + 1).map(p => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setRunsPage(p)}
                  className={`px-2.5 py-1 rounded font-mono text-xs cursor-pointer ${
                    runsPage === p
                      ? "bg-indigo-600 text-white font-bold shadow-2xs"
                      : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {p}
                </button>
              ))}
              <button
                type="button"
                disabled={runsPage >= Math.ceil(runs.length / runsPageSize)}
                onClick={() => setRunsPage(p => p + 1)}
                className="px-2.5 py-1 rounded border border-slate-200 bg-white text-slate-600 disabled:opacity-40 hover:bg-slate-50 cursor-pointer"
              >
                下一页
              </button>
            </div>
          </div>
        )}
      </div>'''

rr = rr.replace(old_table_close, new_table_close)

with open("src/components/ResearchRunsView.tsx", "w", encoding="utf-8") as f:
    f.write(rr)
print("ResearchRunsView pagination added successfully!")
