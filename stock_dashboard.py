import requests
# 語言選擇開關
import streamlit as st
# 確保 df 已定義（若尚未載入股價資料）
if "df" not in locals():
    import pandas as pd
    import numpy as np

    import yfinance as yf

    ticker = "AAPL"
    df = yf.download(ticker, start="2022-01-01", end="2025-01-01")
    df["SMA20"] = df["Close"].rolling(window=20).mean()
    df["RSI"] = 100 - (100 / (1 + df["Close"].pct_change().rolling(14).apply(lambda x: (x[x > 0].mean() / abs(x[x < 0].mean())) if abs(x[x < 0].mean()) > 0 else 0)))
    df = df.dropna()
    # 展平成單層欄位（解決 MultiIndex 造成 Close_AAPL 問題）
    df.columns = ["_".join(col).strip() if isinstance(col, tuple) else col for col in df.columns]
    df.columns = [col.replace(" ", "_").replace("(", "").replace(")", "").replace("%", "").replace("-", "_") for col in df.columns]

    # 建立對應：原始欄位名 → 真正欄位名
    column_alias_map = {
        "Close": [col for col in df.columns if "Close" in col][0],
        "Open": [col for col in df.columns if "Open" in col][0],
        "High": [col for col in df.columns if "High" in col][0],
        "Low": [col for col in df.columns if "Low" in col][0],
        "Volume": [col for col in df.columns if "Volume" in col][0],
        "SMA20": [col for col in df.columns if "SMA20" in col][0],
        "RSI": [col for col in df.columns if "RSI" in col][0],
    }
    original_columns = df.columns
    original_to_cleaned = {col: col for col in df.columns}  # 一一對應，不需轉換

language = st.sidebar.selectbox("Language", ["English", "繁體中文"])
is_en = language == "English"
# === 混合式 LLM 指令入口 ===
st.markdown("## 🧠 Intelligent Command Panel" if is_en else "## 🧠 智能指令入口")
query = st.text_input("🔎 Ask: e.g., show me stocks with RSI < 30" if is_en else "🔎 請輸入指令，例如：找出 RSI 小於 30 的股票")

if query:
    with st.spinner("LLM parsing your intent..."):
        try:
            column_list = ", ".join(df.columns)
            llm_prompt = f"""
You are an AI that receives a natural language question and returns a JSON filter condition.

Current data columns: {column_list}
Question: {query}

Expected output format:
{{"filter": "<expression>"}}
Only return JSON. Do not explain.
"""
            llm_res = requests.post("http://localhost:11434/api/generate", json={
                "model": "llama4:latest",
                "prompt": llm_prompt,
                "stream": False
            })
            llm_res.raise_for_status()
            parsed = llm_res.json().get("response", "").strip()

            if not parsed:
                raise ValueError("Empty response from LLM")

            if "```" in parsed:
                parsed = parsed.split("```")[-1].strip()

            import json
            filter_json = json.loads(parsed)
            filter_expr = filter_json.get("filter")

            if filter_expr:
                import re
                # 將 filter_expr 中的別名換成實際欄位名稱
                for alias, real_col in column_alias_map.items():
                    filter_expr = re.sub(rf"\b{alias}\b", f"`{real_col}`", filter_expr)
                filtered = df.query(filter_expr, engine="python")
                st.markdown("### 🎯 Filtered Results" if is_en else "### 🎯 篩選結果")
                st.dataframe(filtered.tail())
                st.line_chart(filtered[[column_alias_map["Close"]]])
            else:
                st.warning("⚠️ No valid filter key found in LLM response." if is_en else "⚠️ LLM 回傳格式錯誤，找不到篩選條件。")
        except Exception as e:
            st.error(f"❌ Failed to apply filter: {e}" if is_en else f"❌ 篩選失敗：{e}")
