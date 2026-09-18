import traceback
import sys
import server
from stock_model.features import build_features
from stock_model.research import run_latest_research

try:
    symbols = server._pool_symbols()
    panel = server._load_pool_panel(symbols)
    panel, meta_audit, univ_audit = server._governed_research_panel(panel)
    frame, features = build_features(panel, horizon=20)
    print("future_return in frame:", "future_return" in frame.columns)
    res = run_latest_research(frame=frame, features=features, top_k=10, horizon=20, output_dir=server.OUTPUT_DIR, weights=server.DEFAULT_WEIGHTS, fetch_sentiment=False)
    print("SUCCESS")
except Exception as e:
    traceback.print_exc()
