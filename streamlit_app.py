from __future__ import annotations

import asyncio
import json
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from marketminer.pipeline import MarketMinerPipeline
from processors.entity_resolver import records_to_jsonable

st.set_page_config(page_title="MarketMiner GUI", page_icon="⛏️", layout="wide")

CUSTOM_CSS = """
<style>
:root { --mm-blue:#2563eb; --mm-cyan:#06b6d4; --mm-green:#16a34a; --mm-orange:#f97316; }
.block-container { padding-top: 1.4rem; }
.mm-hero {
  padding: 1.4rem 1.6rem; border-radius: 24px;
  background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 48%, #0891b2 100%);
  color: white; box-shadow: 0 18px 50px rgba(15,23,42,.22); margin-bottom: 1.1rem;
}
.mm-hero h1 { margin: 0; font-size: 2.2rem; letter-spacing: -0.04em; }
.mm-hero p { margin: .35rem 0 0 0; color: #dbeafe; font-size: 1.03rem; }
.mm-card {
  padding: 1rem; border-radius: 18px; border: 1px solid rgba(148,163,184,.25);
  background: white; box-shadow: 0 8px 30px rgba(15,23,42,.07); min-height: 126px;
}
.mm-card h3 { margin: 0 0 .35rem 0; font-size: 1rem; color:#0f172a; }
.mm-card p { color:#475569; font-size:.88rem; margin:0; }    /* already dark */
.mm-pill { display:inline-block; padding:.2rem .55rem; border-radius:999px; background:#e0f2fe; color:#075985; font-size:.75rem; font-weight:700; }
.mm-log {
  border-left: 4px solid #2563eb; background:#f8fafc; padding:.7rem .9rem; border-radius:12px;
  margin:.35rem 0; font-size:.9rem;
  color: #0f172a;   /* <--- ADD THIS: dark text for logs */
}
.mm-stage {
  text-align:center; padding:.8rem .35rem; border-radius:18px; background:#f1f5f9; border:1px solid #e2e8f0;
  color: #000000;   /* <--- ADD THIS: black text for stages */
}
.mm-stage-active { background:#dbeafe; border-color:#60a5fa; color:#1d4ed8; font-weight:800; }
.mm-stage-done { background:#dcfce7; border-color:#86efac; color:#166534; font-weight:800; }
[data-testid="stMetricValue"] { font-size: 1.7rem; }
</style>
"""


st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
st.markdown(
    """
    <div class="mm-hero">
      <span class="mm-pill">Enterprise B2B intelligence demo</span>
      <h1>⛏️ MarketMiner Graphical Console</h1>
      <p>Discover manufacturers, filter noise, validate contacts, and export tiered Level 1 / 2 / 3 prospect intelligence.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("🎛️ Controls")
    keywords = st.text_input("Market keywords", value="Switches")
    geography = st.text_input("Target geography", value="Germany")
    demo_mode = st.toggle(
        "Safe demo mode",
        value=True,
        help="Uses curated sample candidates. Disable only for compliant live scraping.",
    )
    smtp_probe = st.toggle(
        "SMTP handshake probe",
        value=False,
        help="Optional non-sending RCPT TO probe. Off by default.",
    )
    st.divider()
    st.markdown("### Pipeline Sources")
    st.checkbox("Yandex Maps", value=True)
    st.checkbox("2GIS", value=True)
    st.checkbox("Industry portals", value=True)
    st.checkbox("Company websites", value=True)
    st.divider()
    run = st.button("🚀 Run Pipeline", type="primary", use_container_width=True)


cards = st.columns(4)
cards[0].markdown(
    "<div class='mm-card'><h3>🌍 Query Expansion</h3><p>Russian translation and industry synonyms: HTV, RTV, siloxane, GOST.</p></div>",
    unsafe_allow_html=True,
)
cards[1].markdown(
    "<div class='mm-card'><h3>🕸️ Async Scraping</h3><p>Playwright-ready local directories, portals, and website crawl adapters.</p></div>",
    unsafe_allow_html=True,
)
cards[2].markdown(
    "<div class='mm-card'><h3>🧠 AI Classification</h3><p>Cost-aware manufacturer vs distributor inference before VIP LLM enrichment.</p></div>",
    unsafe_allow_html=True,
)
cards[3].markdown(
    "<div class='mm-card'><h3>✅ Verification</h3><p>Pydantic schema, fuzzy dedupe, syntax/MX/SMTP email validation hooks.</p></div>",
    unsafe_allow_html=True,
)

st.divider()
progress = st.progress(0)
log_box = st.empty()
metric_box = st.empty()
results_box = st.container()


def flatten(records: list[dict]) -> pd.DataFrame:
    rows = []
    for r in records:
        vips = r["level_3_vip_verified"].get("decision_makers", [])
        rows.append(
            {
                "company_name": r["company_name"],
                "score": r["market_confidence_score"],
                "industry": r["level_1_general"].get("industry_classification"),
                "employees": r["level_1_general"].get("estimated_employee_count"),
                "website": r["level_2_contact"].get("website"),
                "public_email": r["level_2_contact"].get("public_email"),
                "public_phone": r["level_2_contact"].get("public_phone"),
                "vip_count": len(vips),
                "top_decision_maker": vips[0].get("name") if vips else None,
                "top_role": vips[0].get("role") if vips else None,
                "evidence": r["level_3_vip_verified"].get(
                    "extracted_manufacturing_evidence"
                ),
            }
        )
    return pd.DataFrame(rows)


async def run_pipeline_ui():
    pipeline = MarketMinerPipeline(demo=demo_mode, smtp_probe=smtp_probe)
    logs: list[str] = []
    final_records = []
    event_count = 0
    async for item in pipeline.run(keywords, geography):
        if isinstance(item, list):
            final_records = item
            continue
        event_count += 1
        ts = datetime.now().strftime("%H:%M:%S")
        logs.append(
            f"<div class='mm-log'><b>{ts} · {item.level}</b><br>{item.message}</div>"
        )
        log_box.markdown(
            "### 📟 Live pipeline logs" + "".join(logs[-12:]), unsafe_allow_html=True
        )
        progress.progress(min(event_count / 13, 1.0))
        await asyncio.sleep(0.05)
    progress.progress(1.0)
    return final_records, pipeline.log_file


if run:
    try:
        records, log_file = asyncio.run(run_pipeline_ui())
        jsonable = records_to_jsonable(records)
        df = flatten(jsonable)

        with metric_box.container():
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Companies", len(df))
            m2.metric(
                "Avg confidence", f"{df['score'].mean():.1f}" if not df.empty else "0"
            )
            m3.metric("VIP contacts", int(df["vip_count"].sum()) if not df.empty else 0)
            m4.metric("Best score", int(df["score"].max()) if not df.empty else 0)
            m5.metric("Run log", log_file.name)

        with results_box:
            tab1, tab2, tab3, tab4 = st.tabs(
                ["📊 Dashboard", "🏢 Companies", "👤 VIP Contacts", "🧾 Raw JSON"]
            )

            with tab1:
                left, right = st.columns([1.15, 0.85])
                with left:
                    fig = px.bar(
                        df,
                        x="company_name",
                        y="score",
                        color="vip_count",
                        text="score",
                        title="Manufacturer confidence score",
                        color_continuous_scale="Blues",
                    )
                    fig.update_layout(
                        xaxis_tickangle=-22,
                        height=430,
                        margin=dict(l=20, r=20, t=55, b=90),
                    )
                    st.plotly_chart(fig, use_container_width=True)
                with right:
                    score_bins = pd.cut(
                        df["score"],
                        bins=[0, 84, 90, 100],
                        labels=["Level 1", "Level 2", "Level 3"],
                    )
                    pie_df = score_bins.value_counts().reset_index()
                    pie_df.columns = ["tier", "count"]
                    fig2 = px.pie(
                        pie_df,
                        values="count",
                        names="tier",
                        title="Tier distribution",
                        hole=0.45,
                    )
                    fig2.update_layout(height=430)
                    st.plotly_chart(fig2, use_container_width=True)

            with tab2:
                st.dataframe(df, use_container_width=True, hide_index=True)

            with tab3:
                vip_rows = []
                for r in jsonable:
                    for dm in r["level_3_vip_verified"].get("decision_makers", []):
                        vip_rows.append(
                            {
                                "company": r["company_name"],
                                "name": dm.get("name"),
                                "role": dm.get("role"),
                                "direct_email": dm.get("direct_email"),
                                "direct_phone": dm.get("direct_phone"),
                                "status": dm.get("email_verification_status"),
                            }
                        )
                st.dataframe(
                    pd.DataFrame(vip_rows), use_container_width=True, hide_index=True
                )

            with tab4:
                st.json(jsonable)

            st.subheader("⬇️ Export")
            json_bytes = json.dumps(jsonable, ensure_ascii=False, indent=2).encode(
                "utf-8"
            )
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            c1, c2 = st.columns(2)
            c1.download_button(
                "Download JSON",
                data=json_bytes,
                file_name="marketminer_results.json",
                mime="application/json",
                use_container_width=True,
            )
            c2.download_button(
                "Download CSV",
                data=csv_bytes,
                file_name="marketminer_results.csv",
                mime="text/csv",
                use_container_width=True,
            )
    except Exception as exc:
        st.error(f"Pipeline failed unexpectedly: {exc}")
        st.info(
            "Individual website/contact failures are normally marked Unverified. A top-level error usually means missing local dependencies."
        )
else:
    st.info(
        "Use the sidebar and click **Run Pipeline** to start the graphical workflow."
    )
