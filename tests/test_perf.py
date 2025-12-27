"""Performance profiler with Streamlit UI."""

import streamlit as st
import cProfile
import pstats
import pandas as pd
from src.processor.core import extract_blocks

st.set_page_config(page_title="Performance Profiler", layout="wide")

st.title("🔍 Performance Profiler")

# Sidebar controls
with st.sidebar:
    st.header("Configuration")
    test_url = st.text_input("Test URL", value="https://example.com")
    min_time_ms = st.slider("Min time to show (ms)", 1, 100, 10)
    max_rows = st.slider("Max rows to display", 10, 100, 30)

    run_profile = st.button("▶️ Run Profile", type="primary", use_container_width=True)

if "profiler_data" not in st.session_state:
    st.session_state.profiler_data = None

if run_profile:
    with st.spinner("Running profiler..."):
        profiler = cProfile.Profile()

        try:
            profiler.enable()
            result = extract_blocks(test_url)
            profiler.disable()

            stats = pstats.Stats(profiler)

            # Collect all functions
            all_functions = []
            for func_key, data in stats.stats.items():
                filename, line, func_name = func_key
                ncalls = data[0]
                tottime = data[2] * 1000
                cumtime = data[3] * 1000

                if cumtime >= min_time_ms:
                    all_functions.append(
                        {
                            "filename": filename,
                            "line": line,
                            "function": func_name,
                            "calls": ncalls,
                            "total_time_ms": tottime,
                            "cumulative_time_ms": cumtime,
                            "time_per_call_ms": tottime / ncalls if ncalls > 0 else 0,
                            "is_src": "src/" in filename,
                        }
                    )

            st.session_state.profiler_data = {
                "functions": all_functions,
                "total_time": stats.total_tt * 1000,
                "success": True,
                "result_type": str(type(result)),
            }

        except Exception as e:
            st.session_state.profiler_data = {"success": False, "error": str(e)}

# Display results
if st.session_state.profiler_data:
    data = st.session_state.profiler_data

    if not data["success"]:
        st.error(f"❌ Profiling failed: {data['error']}")
    else:
        st.success("✅ Profiling completed successfully")

        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Execution Time", f"{data['total_time']:.2f} ms")
        with col2:
            st.metric("Functions Analyzed", len(data["functions"]))
        with col3:
            src_funcs = sum(1 for f in data["functions"] if f["is_src"])
            st.metric("Your Code Functions", src_funcs)

        st.divider()

        # Create tabs
        tab1, tab2, tab3, tab4 = st.tabs(["All Functions", "Time Consumers", "Most Called", "Code Only"])

        # Tab 1: All functions
        with tab1:
            st.subheader("All Functions (sorted by cumulative time)")

            df = pd.DataFrame(data["functions"])
            df = df.sort_values("cumulative_time_ms", ascending=False).head(max_rows)

            # Format the dataframe
            df["file"] = df["filename"].apply(lambda x: x.split("/")[-1])
            df["location"] = df["file"] + ":" + df["line"].astype(str)
            df["%_of_total"] = (df["total_time_ms"] / data["total_time"] * 100).round(1)

            display_df = df[
                [
                    "location",
                    "function",
                    "calls",
                    "total_time_ms",
                    "cumulative_time_ms",
                    "time_per_call_ms",
                    "%_of_total",
                ]
            ].copy()

            display_df.columns = [
                "Location",
                "Function",
                "Calls",
                "Total Time (ms)",
                "Cumulative Time (ms)",
                "Time/Call (ms)",
                "% of Total",
            ]

            st.dataframe(
                display_df,
                width="stretch",
                hide_index=True,
                column_config={
                    "Total Time (ms)": st.column_config.NumberColumn(format="%.2f"),
                    "Cumulative Time (ms)": st.column_config.NumberColumn(format="%.2f"),
                    "Time/Call (ms)": st.column_config.NumberColumn(format="%.4f"),
                },
            )

        # Tab 2: Time consumers
        with tab2:
            st.subheader("Top Time Consumers (by total time, excluding subcalls)")

            df = pd.DataFrame(data["functions"])
            df_src = df[df["is_src"]].copy()
            df_src = df_src.sort_values("total_time_ms", ascending=False).head(max_rows)

            if len(df_src) > 0:
                df_src["file"] = df_src["filename"].apply(
                    lambda x: x.split("src/")[-1] if "src/" in x else x.split("/")[-1]
                )
                df_src["%_of_total"] = (df_src["total_time_ms"] / data["total_time"] * 100).round(1)

                display_df = df_src[["file", "function", "total_time_ms", "%_of_total", "calls"]].copy()

                display_df.columns = ["File", "Function", "Total Time (ms)", "% of Total", "Calls"]

                st.dataframe(
                    display_df,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "Total Time (ms)": st.column_config.ProgressColumn(
                            format="%.2f",
                            min_value=0,
                            max_value=float(df_src["total_time_ms"].max()),
                        ),
                    },
                )

                # Bar chart
                chart_df = df_src.head(15)[["function", "total_time_ms"]].copy()
                chart_df.columns = ["Function", "Time (ms)"]
                st.bar_chart(chart_df.set_index("Function"))
            else:
                st.info("No functions from src/ directory found")

        # Tab 3: Most called
        with tab3:
            st.subheader("Most Frequently Called Functions")

            df = pd.DataFrame(data["functions"])
            df_src = df[df["is_src"]].copy()
            df_src = df_src.sort_values("calls", ascending=False).head(max_rows)

            if len(df_src) > 0:
                df_src["file"] = df_src["filename"].apply(
                    lambda x: x.split("src/")[-1] if "src/" in x else x.split("/")[-1]
                )

                display_df = df_src[["file", "function", "calls", "time_per_call_ms", "total_time_ms"]].copy()

                display_df.columns = ["File", "Function", "Calls", "Time/Call (ms)", "Total Time (ms)"]

                st.dataframe(
                    display_df,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "Calls": st.column_config.NumberColumn(format="%d"),
                        "Time/Call (ms)": st.column_config.NumberColumn(format="%.4f"),
                        "Total Time (ms)": st.column_config.NumberColumn(format="%.2f"),
                    },
                )

                # Highlight hot loops
                hot_loops = df_src[(df_src["calls"] > 100) & (df_src["total_time_ms"] > 50)]
                if len(hot_loops) > 0:
                    st.warning(f"⚠️ Found {len(hot_loops)} potential hot loops (>100 calls, >50ms total)")
            else:
                st.info("No functions from src/ directory found")

        # Tab 4: Your code only
        with tab4:
            st.subheader("Functions from src/ Directory")

            df = pd.DataFrame(data["functions"])
            df_src = df[df["is_src"]].copy()
            df_src = df_src.sort_values("cumulative_time_ms", ascending=False)

            if len(df_src) > 0:
                df_src["file"] = df_src["filename"].apply(lambda x: x.split("src/")[-1])
                df_src["%_of_total"] = (df_src["total_time_ms"] / data["total_time"] * 100).round(1)

                display_df = df_src[
                    ["file", "line", "function", "calls", "total_time_ms", "cumulative_time_ms", "%_of_total"]
                ].copy()

                display_df.columns = [
                    "File",
                    "Line",
                    "Function",
                    "Calls",
                    "Total Time (ms)",
                    "Cumulative Time (ms)",
                    "% of Total",
                ]

                st.dataframe(
                    display_df,
                    width="stretch",
                    hide_index=True,
                    height=600,
                    column_config={
                        "Total Time (ms)": st.column_config.NumberColumn(format="%.2f"),
                        "Cumulative Time (ms)": st.column_config.NumberColumn(format="%.2f"),
                    },
                )

                # Download button
                csv = display_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download as CSV", data=csv, file_name="profile_results.csv", mime="text/csv"
                )
            else:
                st.info("No functions from src/ directory found")

else:
    st.info("Configure settings and click 'Run Profile' to start")
