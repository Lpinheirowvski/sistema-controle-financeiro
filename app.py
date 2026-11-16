"""Interactive Streamlit dashboard for Financial Analytics System v2.0."""

from datetime import date, timedelta

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from financial_analytics.analytics import (
    expense_categories,
    monthly_cash_flow,
    running_balance,
    to_frame,
    totals,
)
from financial_analytics.db import DatabaseError, configure_logging
from financial_analytics.exports import csv_bytes, excel_bytes
from financial_analytics.repository import Filters, TransactionRepository
from financial_analytics.validation import TransactionInput

st.set_page_config(page_title="Financial Analytics · v2.0", page_icon="◈", layout="wide")
configure_logging()
BLUE, GREEN, CORAL = "#60A5FA", "#34D3AC", "#FB8C8C"


def money(value):
    return f"R$ {value:,.2f}"


def style_chart(figure):
    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Arial, sans-serif", color="#C6D5E9"),
        margin=dict(l=10, r=10, t=25, b=15),
        height=340,
        legend=dict(orientation="h", y=1.15, x=0),
        hovermode="x unified",
    )
    figure.update_xaxes(showgrid=False)
    figure.update_yaxes(gridcolor="#20344F", zerolinecolor="#20344F")
    return figure


def transaction_form(repo, categories, accounts, existing=None):
    suffix = f"{existing['id']}-{existing['revision']}" if existing else "new"
    category_ids = [c["id"] for c in categories]
    account_ids = [a["id"] for a in accounts]
    category_names = {c["id"]: f"{c['name']} · {c['kind']}" for c in categories}
    account_names = {a["id"]: a["name"] for a in accounts}
    with st.form(f"transaction-{suffix}", clear_on_submit=existing is None):
        description = st.text_input(
            "Description",
            value=existing["description"] if existing else "",
            max_chars=200,
            key=f"description-{suffix}",
        )
        left, right = st.columns(2)
        amount = left.text_input(
            "Amount (BRL)",
            value=str(existing["amount"]) if existing else "",
            placeholder="250.00",
            help="Use a dot for decimals, up to two places.",
            key=f"amount-{suffix}",
        )
        day = right.date_input(
            "Transaction date",
            value=existing["transaction_date"] if existing else date.today(),
            min_value=date(1000, 1, 1),
            max_value=date(9999, 12, 31),
            key=f"day-{suffix}",
        )
        left, right = st.columns(2)
        category = left.selectbox(
            "Category",
            category_ids,
            format_func=category_names.get,
            index=category_ids.index(existing["category_id"]) if existing else 0,
            key=f"category-{suffix}",
        )
        account = right.selectbox(
            "Account",
            account_ids,
            format_func=account_names.get,
            index=account_ids.index(existing["account_id"]) if existing else 0,
            key=f"account-{suffix}",
        )
        st.caption("The category determines whether this transaction is income or an expense.")
        submitted = st.form_submit_button(
            "Save changes" if existing else "Add transaction", type="primary"
        )
    if submitted:
        try:
            item = TransactionInput.parse(description, amount, day, category, account)
            if existing:
                repo.update(existing["id"], item, existing["revision"])
            else:
                repo.create(item)
            st.session_state.pop("edit_snapshot", None)
            st.session_state["notice"] = (
                "Transaction updated." if existing else "Transaction added."
            )
            st.rerun()
        except (ValueError, DatabaseError) as exc:
            st.error(str(exc))


def main():
    st.markdown(
        """<style>
    .block-container {padding-top:4.5rem; padding-bottom:2rem; max-width:1500px;}
    [data-testid="stSidebar"] {border-right:1px solid #243650;}
    [data-testid="stMetric"] {background:#12233B; border:1px solid #243650;
        border-radius:12px; padding:18px;}
    [data-testid="stMetricLabel"] {color:#AFC2DE;}
    [data-testid="stMetricValue"] {font-size:clamp(1.3rem,2.4vw,2.2rem);}
    h1 {letter-spacing:-1px;} h3 {letter-spacing:-0.4px;}
    .eyebrow {color:#75AAED; font-size:.75rem; letter-spacing:2px; font-weight:600;}
    .subtitle {color:#AFC2DE; margin-bottom:1.5rem;}
    div[data-testid="stTabs"] button {font-size:1rem;}
    @media(max-width:640px) {.block-container {padding-top:4rem;}}
    </style>""",
        unsafe_allow_html=True,
    )
    repo = TransactionRepository()
    categories, accounts = repo.categories(), repo.accounts()
    if not categories or not accounts:
        st.info("Initialize the database before using the dashboard. See the README quick start.")
        st.stop()
    bounds = repo.date_bounds()
    first, last = bounds["first_date"] or date.today(), bounds["last_date"] or date.today()
    with st.sidebar:
        st.markdown("### ◈ Financial Analytics")
        st.caption("FINANCIAL ANALYTICS SYSTEM · v2.0")
        st.divider()
        st.markdown("#### Report filters")
        period = st.date_input(
            "Date range",
            value=(first, last),
            min_value=date(1000, 1, 1),
            max_value=date(9999, 12, 31),
        )
        kind = st.selectbox("Transaction type", ["All types", "Income", "Expense"])
        category_names = {c["id"]: f"{c['name']} · {c['kind']}" for c in categories}
        selected_categories = st.multiselect(
            "Categories",
            list(category_names),
            format_func=category_names.get,
            placeholder="All categories",
        )
        if st.button("Refresh data", width="stretch"):
            st.session_state.pop("edit_snapshot", None)
            st.rerun()
        st.divider()
        st.caption("CURRENCY  ·  BRL (R$)")
        st.caption("Cash flow analytics for clearer financial decisions.")
    if len(period) != 2:
        st.info("Select both a start and end date.")
        st.stop()
    start, end = period
    filters = Filters(
        start, end, tuple(selected_categories), None if kind == "All types" else kind.lower()
    )
    frame = to_frame(repo.list(filters))
    current = totals(frame)
    monthly = monthly_cash_flow(frame, start, end)
    # Compare the same number of calendar days, with the same category/type filters.
    span = (end - start).days + 1
    previous = None
    if start.toordinal() > span:
        previous_start, previous_end = start - timedelta(days=span), start - timedelta(days=1)
        previous = totals(
            to_frame(
                repo.list(Filters(previous_start, previous_end, filters.category_ids, filters.kind))
            )
        )
    st.markdown('<div class="eyebrow">PERSONAL FINANCE INTELLIGENCE</div>', unsafe_allow_html=True)
    st.title("Your finances, in focus.")
    st.markdown(
        '<div class="subtitle">Financial Analytics System v2.0 · '
        "Track cash flow. Understand patterns. Make informed decisions.</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        f"{start:%d %b %Y} — {end:%d %b %Y}  ·  {current['count']:,} transactions"
        "  ·  All figures in BRL"
    )
    if notice := st.session_state.pop("notice", None):
        st.success(notice)
    columns = st.columns(4)
    for column, label, key in zip(
        columns,
        ["Income", "Expenses", "Net cash flow", "Transactions"],
        ["income", "expenses", "net", "count"],
        strict=True,
    ):
        value = f"{current[key]:,}" if key == "count" else money(current[key])
        delta = None
        if previous:
            difference = current[key] - previous[key]
            delta = f"{difference:+,}" if key == "count" else f"R$ {difference:+,.2f}"
        column.metric(
            label, value, delta=delta, delta_color="inverse" if key == "expenses" else "normal"
        )
    if previous:
        st.caption(
            f"Indicator changes compare with {previous_start:%d %b %Y} — "
            f"{previous_end:%d %b %Y} ({span} days, same filters)."
        )
    overview, transactions_tab, manage = st.tabs(
        ["Overview", "Transactions & reports", "Manage transactions"]
    )
    with overview:
        if frame.empty:
            st.info("No transactions match these filters. Adjust the period or add a transaction.")
        left, right = st.columns([1.65, 1])
        with left:
            with st.container(border=True):
                st.subheader("Cash flow over time")
                st.caption("Income and expenses by calendar month")
                chart = monthly.copy()
                for name in ["income", "expenses", "net", "cumulative_net"]:
                    chart[name] = chart[name].astype(float)
                figure = go.Figure()
                for name, label, color in [
                    ("income", "Income", GREEN),
                    ("expenses", "Expenses", CORAL),
                ]:
                    figure.add_trace(
                        go.Scatter(
                            x=chart.month,
                            y=chart[name],
                            name=label,
                            mode="lines+markers",
                            line=dict(color=color, width=3),
                        )
                    )
                st.plotly_chart(style_chart(figure), width="stretch")
        with right:
            with st.container(border=True):
                st.subheader("Where your money goes")
                st.caption("Expense distribution by category")
                category_frame = expense_categories(frame)
                if category_frame.empty:
                    st.info("No expenses for this selection.")
                else:
                    figure = px.pie(
                        category_frame.assign(expenses=category_frame.expenses.astype(float)),
                        values="expenses",
                        names="category",
                        hole=0.68,
                        color_discrete_sequence=[
                            BLUE,
                            GREEN,
                            "#A78BFA",
                            CORAL,
                            "#FBBF24",
                            "#38BDF8",
                            "#F472B6",
                            "#94A3B8",
                        ],
                    )
                    figure.update_traces(
                        textinfo="percent",
                        textposition="outside",
                        hovertemplate="%{label}<br>R$ %{value:,.2f}<extra></extra>",
                    )
                    figure = style_chart(figure)
                    figure.update_layout(legend=dict(orientation="h", y=-0.15))
                    st.plotly_chart(figure, width="stretch")
        left, right = st.columns(2)
        with left:
            with st.container(border=True):
                st.subheader("Monthly comparison")
                figure = go.Figure()
                figure.add_bar(x=chart.month, y=chart.income, name="Income", marker_color=GREEN)
                figure.add_bar(x=chart.month, y=chart.expenses, name="Expenses", marker_color=CORAL)
                figure.update_layout(barmode="group")
                st.plotly_chart(style_chart(figure), width="stretch")
        with right:
            with st.container(border=True):
                st.subheader("Cumulative cash flow")
                st.caption(
                    "Starts at zero at the selected period boundary; excludes opening balances."
                )
                figure = go.Figure(
                    go.Scatter(
                        x=chart.month,
                        y=chart.cumulative_net,
                        name="Cumulative net",
                        fill="tozeroy",
                        line=dict(color=BLUE, width=3),
                    )
                )
                st.plotly_chart(style_chart(figure), width="stretch")
    with transactions_tab:
        st.subheader("Transaction ledger")
        st.caption("Sort columns, search the table or download the filtered report.")
        display = running_balance(frame)[
            [
                "id",
                "transaction_date",
                "description",
                "kind",
                "category",
                "account",
                "amount",
                "cumulative_balance",
            ]
        ]
        st.dataframe(
            display,
            hide_index=True,
            width="stretch",
            column_config={
                "amount": st.column_config.NumberColumn("Amount (BRL)", format="%.2f"),
                "cumulative_balance": st.column_config.NumberColumn(
                    "Cumulative net (BRL)", format="%.2f"
                ),
            },
        )
        left, right = st.columns(2)
        left.download_button(
            "↓ Export transactions · CSV",
            csv_bytes(display),
            "transactions.csv",
            "text/csv",
            width="stretch",
        )
        right.download_button(
            "↓ Export full report · Excel",
            excel_bytes(display, monthly),
            "financial-report.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
        st.markdown("#### Monthly summary")
        st.dataframe(monthly, hide_index=True, width="stretch")
    with manage:
        add, edit = st.columns(2)
        with add:
            with st.container(border=True):
                st.subheader("Add a transaction")
                transaction_form(repo, categories, accounts)
        with edit:
            with st.container(border=True):
                st.subheader("Edit or delete")
                st.caption("Choose a transaction from the current filtered selection.")
                if frame.empty:
                    st.info("No transactions available to edit.")
                else:
                    labels = {
                        r["id"]: f"#{r['id']} · {r['description']}"
                        for r in frame.to_dict("records")
                    }
                    selected = st.selectbox(
                        "Select a transaction", list(labels), format_func=labels.get
                    )
                    snapshot = st.session_state.get("edit_snapshot")
                    if not snapshot or snapshot["id"] != selected:
                        snapshot = repo.get(selected)
                        st.session_state["edit_snapshot"] = snapshot
                    transaction_form(repo, categories, accounts, snapshot)
                    confirmed = st.checkbox(
                        "I confirm deletion of this transaction", key=f"delete-confirm-{selected}"
                    )
                    if st.button("Delete transaction", disabled=not confirmed):
                        try:
                            repo.delete(selected, snapshot["revision"])
                            st.session_state.pop("edit_snapshot", None)
                            st.session_state["notice"] = "Transaction deleted."
                            st.rerun()
                        except (ValueError, DatabaseError) as exc:
                            st.error(str(exc))
    st.divider()
    st.caption("FINANCIAL ANALYTICS SYSTEM  /  v2.0  ·  Python · MySQL · Streamlit")


try:
    main()
except (ValueError, DatabaseError) as error:
    st.error(str(error))
    st.info("Check your .env settings and initialize the database using the README instructions.")
