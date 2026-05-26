import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import numpy as np
import mysql.connector
import pandas as pd
import subprocess
import os
import sys
import traceback
import warnings
warnings.filterwarnings("ignore")
from DATA import DB_CONFIG

# ── Kết nối ─────────────────────────────────────────────────
def get_conn():
    cfg = dict(DB_CONFIG)
    cfg["database"] = "Olist"
    return mysql.connector.connect(**cfg)

def q(sql):
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return pd.DataFrame(rows)

# ── Load data ────────────────────────────────────────────────
print("Dang tai du lieu tu MySQL...")

SQL_REV_MONTH = """
    SELECT DATE_FORMAT(o.order_purchase_timestamp,'%Y-%m') AS month,
           ROUND(SUM(oi.price + oi.freight_value),2)       AS revenue
    FROM olist_order_items_dataset oi
    JOIN olist_orders_dataset o ON oi.order_id = o.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY month ORDER BY month
"""

SQL_REV_YEAR = """
    SELECT YEAR(o.order_purchase_timestamp)        AS year,
           ROUND(SUM(oi.price+oi.freight_value),2) AS revenue
    FROM olist_order_items_dataset oi
    JOIN olist_orders_dataset o ON oi.order_id = o.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY year ORDER BY year
"""

SQL_ORD_MONTH = """
    SELECT DATE_FORMAT(order_purchase_timestamp,'%Y-%m') AS month,
           COUNT(DISTINCT order_id)                       AS num_orders
    FROM olist_orders_dataset
    GROUP BY month ORDER BY month
"""

SQL_SEASON = """
    SELECT CASE
             WHEN MONTH(order_purchase_timestamp) IN (12,1,2)  THEN 'Summer (Dec-Feb)'
             WHEN MONTH(order_purchase_timestamp) IN (3,4,5)   THEN 'Autumn (Mar-May)'
             WHEN MONTH(order_purchase_timestamp) IN (6,7,8)   THEN 'Winter (Jun-Aug)'
             WHEN MONTH(order_purchase_timestamp) IN (9,10,11) THEN 'Spring (Sep-Nov)'
           END AS season,
           COUNT(DISTINCT order_id) AS num_orders
    FROM olist_orders_dataset
    GROUP BY season ORDER BY num_orders DESC
"""

SQL_CAT = """
    SELECT COALESCE(t.product_category_name_english,
                    p.product_category_name,'Unknown') AS category,
           COUNT(oi.order_item_id)  AS items_sold,
           ROUND(SUM(oi.price),2)   AS total_sales
    FROM olist_order_items_dataset oi
    JOIN olist_products_dataset p ON oi.product_id = p.product_id
    LEFT JOIN product_category_name_translation t
           ON p.product_category_name = t.product_category_name
    GROUP BY category ORDER BY items_sold DESC LIMIT 15
"""

SQL_AOV_PAY = """
    SELECT payment_type,
           ROUND(AVG(order_value),2) AS aov,
           COUNT(DISTINCT order_id)  AS num_orders
    FROM (SELECT op.order_id, op.payment_type,
                 SUM(op.payment_value) AS order_value
          FROM olist_order_payments_dataset op
          GROUP BY op.order_id, op.payment_type) t
    GROUP BY payment_type ORDER BY aov DESC
"""

SQL_AOV_CAT = """
    SELECT COALESCE(t.product_category_name_english,
                    p.product_category_name,'Unknown') AS category,
           ROUND(AVG(oi.price+oi.freight_value),2)     AS avg_item_value
    FROM olist_order_items_dataset oi
    JOIN olist_products_dataset p ON oi.product_id = p.product_id
    LEFT JOIN product_category_name_translation t
           ON p.product_category_name = t.product_category_name
    GROUP BY category ORDER BY avg_item_value DESC LIMIT 15
"""

try:
    df_rev_month = q(SQL_REV_MONTH)
    print("  [1/7] revenue by month OK")
    df_rev_year  = q(SQL_REV_YEAR)
    print("  [2/7] revenue by year OK")
    df_ord_month = q(SQL_ORD_MONTH)
    print("  [3/7] orders by month OK")
    df_season    = q(SQL_SEASON)
    print("  [4/7] orders by season OK")
    df_cat       = q(SQL_CAT)
    print("  [5/7] top categories OK")
    df_aov_pay   = q(SQL_AOV_PAY)
    print("  [6/7] aov by payment OK")
    df_aov_cat   = q(SQL_AOV_CAT)
    print("  [7/7] aov by category OK")
except Exception:
    traceback.print_exc()
    sys.exit(1)

print("Du lieu da tai xong. Dang ve bieu do...")

# ── Theme ────────────────────────────────────────────────────
BG     = "#0f1117"
CARD   = "#1a1f2e"
BORDER = "#2d3748"
TEXT   = "#e2e8f0"
MUTED  = "#718096"
GREEN  = "#38a169"
BLUE   = "#3182ce"
PURPLE = "#805ad5"
ORANGE = "#dd6b20"

plt.rcParams.update({
    "figure.facecolor":  BG,
    "axes.facecolor":    CARD,
    "axes.edgecolor":    BORDER,
    "axes.labelcolor":   MUTED,
    "axes.titlecolor":   TEXT,
    "axes.titlesize":    11,
    "axes.titleweight":  "bold",
    "axes.titlepad":     10,
    "xtick.color":       MUTED,
    "ytick.color":       MUTED,
    "xtick.labelsize":   8,
    "ytick.labelsize":   8,
    "grid.color":        BORDER,
    "grid.linewidth":    0.5,
    "text.color":        TEXT,
    "font.family":       "DejaVu Sans",
    "legend.facecolor":  CARD,
    "legend.edgecolor":  BORDER,
    "legend.labelcolor": MUTED,
    "legend.fontsize":   8,
})

def fmt_money(v, _=None):
    if v >= 1e6:
        return f"${v/1e6:.1f}M"
    if v >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:.0f}"

def style_ax(ax):
    for spine in ax.spines.values():
        spine.set_edgecolor(BORDER)
        spine.set_linewidth(0.8)

# ── Figure ───────────────────────────────────────────────────
fig = plt.figure(figsize=(22, 26), facecolor=BG)
fig.suptitle("Olist E-Commerce Analytics  |  Brazil 2016-2018",
             fontsize=16, fontweight="bold", color=TEXT, y=0.985)

gs = gridspec.GridSpec(
    5, 3, figure=fig,
    hspace=0.55, wspace=0.35,
    top=0.96, bottom=0.03,
    left=0.06, right=0.97
)

# ── Row 0: KPI cards ─────────────────────────────────────────
total_rev = float(df_rev_month["revenue"].astype(float).sum())
total_ord = int(df_ord_month["num_orders"].astype(int).sum())
top_cat   = str(df_cat.iloc[0]["category"])

kpi_data = [
    ("Tong Doanh Thu", f"${total_rev/1e6:.2f}M", GREEN,  "don delivered"),
    ("Tong Don Hang",  f"{total_ord:,}",           BLUE,   "tat ca trang thai"),
    ("Top Category",   top_cat,                    PURPLE, "theo items sold"),
]

for i, (label, value, color, sub) in enumerate(kpi_data):
    ax = fig.add_subplot(gs[0, i])
    ax.set_facecolor(CARD)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.axhline(y=0.96, xmin=0.04, xmax=0.96, color=color, linewidth=3)
    ax.text(0.5, 0.62, value, ha="center", va="center",
            fontsize=20, fontweight="bold", color=TEXT, transform=ax.transAxes)
    ax.text(0.5, 0.36, label, ha="center", va="center",
            fontsize=9, color=MUTED, transform=ax.transAxes)
    ax.text(0.5, 0.14, sub,   ha="center", va="center",
            fontsize=8, color=color, transform=ax.transAxes)
    style_ax(ax)

# ── Row 1 col 0-1: Revenue by month ──────────────────────────
ax_a1 = fig.add_subplot(gs[1, :2])
x   = np.arange(len(df_rev_month))
rev = df_rev_month["revenue"].astype(float).values
ax_a1.fill_between(x, rev, alpha=0.18, color=GREEN)
ax_a1.plot(x, rev, color=GREEN, linewidth=2, marker="o", markersize=3)
ax_a1.set_xticks(x)
ax_a1.set_xticklabels(df_rev_month["month"].tolist(), rotation=45, ha="right", fontsize=7)
ax_a1.yaxis.set_major_formatter(plt.FuncFormatter(fmt_money))
ax_a1.set_title("A  |  Doanh Thu Theo Thang (delivered)")
ax_a1.grid(axis="y", alpha=0.35)
style_ax(ax_a1)

# ── Row 1 col 2: Revenue by year ─────────────────────────────
ax_a2 = fig.add_subplot(gs[1, 2])
years = df_rev_year["year"].astype(str).tolist()
rev_y = df_rev_year["revenue"].astype(float).values
bars  = ax_a2.bar(years, rev_y, color=[GREEN, BLUE, PURPLE],
                  width=0.5, edgecolor=BG, linewidth=0.5)
for bar, val in zip(bars, rev_y):
    ax_a2.text(bar.get_x() + bar.get_width()/2,
               bar.get_height() + rev_y.max()*0.02,
               fmt_money(val), ha="center", va="bottom", fontsize=8, color=TEXT)
ax_a2.yaxis.set_major_formatter(plt.FuncFormatter(fmt_money))
ax_a2.set_title("A  |  Doanh Thu Theo Nam")
ax_a2.grid(axis="y", alpha=0.35)
style_ax(ax_a2)

# ── Row 2 col 0-1: Orders by month ───────────────────────────
ax_b1 = fig.add_subplot(gs[2, :2])
xo   = np.arange(len(df_ord_month))
ords = df_ord_month["num_orders"].astype(int).values
ax_b1.fill_between(xo, ords, alpha=0.18, color=BLUE)
ax_b1.plot(xo, ords, color=BLUE, linewidth=2, marker="o", markersize=3)
ax_b1.set_xticks(xo)
ax_b1.set_xticklabels(df_ord_month["month"].tolist(), rotation=45, ha="right", fontsize=7)
ax_b1.set_title("B  |  So Don Hang Theo Thang")
ax_b1.grid(axis="y", alpha=0.35)
style_ax(ax_b1)

# ── Row 2 col 2: Season pie ───────────────────────────────────
ax_b2 = fig.add_subplot(gs[2, 2])
wedges, texts, autotexts = ax_b2.pie(
    df_season["num_orders"].astype(int).values,
    labels=df_season["season"].tolist(),
    colors=[BLUE, GREEN, PURPLE, ORANGE],
    autopct="%1.1f%%",
    startangle=90,
    pctdistance=0.75,
    wedgeprops=dict(edgecolor=BG, linewidth=2),
)
for t in texts:
    t.set_color(MUTED)
    t.set_fontsize(8)
for at in autotexts:
    at.set_color(TEXT)
    at.set_fontsize(8)
    at.set_fontweight("bold")
ax_b2.set_title("B  |  Don Hang Theo Mua (Brazil)")
style_ax(ax_b2)

# ── Row 3 full: Top categories ────────────────────────────────
ax_c  = fig.add_subplot(gs[3, :])
cats  = df_cat["category"].tolist()
idx   = np.arange(len(cats))
w     = 0.4
items = df_cat["items_sold"].astype(int).values
sales = df_cat["total_sales"].astype(float).values

ax_c.bar(idx - w/2, items, w, color=PURPLE, edgecolor=BG, linewidth=0.4)
ax_c2 = ax_c.twinx()
ax_c2.bar(idx + w/2, sales, w, color=ORANGE, edgecolor=BG, linewidth=0.4)

ax_c.set_xticks(idx)
ax_c.set_xticklabels(cats, rotation=35, ha="right", fontsize=8)
ax_c.set_ylabel("Items Sold",         color=PURPLE, fontsize=9)
ax_c.tick_params(axis="y",            colors=PURPLE)
ax_c2.set_ylabel("Total Sales (USD)", color=ORANGE, fontsize=9)
ax_c2.tick_params(axis="y",           colors=ORANGE)
ax_c2.yaxis.set_major_formatter(plt.FuncFormatter(fmt_money))
ax_c.set_title("C  |  Top 15 Danh Muc - Items Sold vs Total Sales")
ax_c.grid(axis="y", alpha=0.3)
ax_c.set_facecolor(CARD)
ax_c2.set_facecolor(CARD)
style_ax(ax_c)
style_ax(ax_c2)
ax_c.legend(
    handles=[mpatches.Patch(color=PURPLE, label="Items Sold"),
             mpatches.Patch(color=ORANGE, label="Total Sales (USD)")],
    loc="upper right"
)

# ── Row 4 col 0: AOV by payment ──────────────────────────────
ax_d1     = fig.add_subplot(gs[4, 0])
aov_vals  = df_aov_pay["aov"].astype(float).values
pay_types = df_aov_pay["payment_type"].tolist()
hbars = ax_d1.barh(pay_types, aov_vals,
                   color=[ORANGE, BLUE, GREEN, PURPLE, MUTED][:len(df_aov_pay)],
                   edgecolor=BG, linewidth=0.4)
for bar, val in zip(hbars, aov_vals):
    ax_d1.text(val + aov_vals.max()*0.01,
               bar.get_y() + bar.get_height()/2,
               f"${val:.2f}", va="center", fontsize=8, color=TEXT)
ax_d1.set_xlabel("AOV (USD)", color=MUTED)
ax_d1.set_title("D  |  AOV Theo Payment Method")
ax_d1.grid(axis="x", alpha=0.35)
style_ax(ax_d1)

# ── Row 4 col 1-2: Avg item value by category ────────────────
ax_d2    = fig.add_subplot(gs[4, 1:])
cmap     = plt.cm.get_cmap("cool", len(df_aov_cat))
cats_d2  = df_aov_cat["category"].tolist()[::-1]
vals_d2  = df_aov_cat["avg_item_value"].astype(float).values[::-1]
hbars2   = ax_d2.barh(cats_d2, vals_d2,
                      color=[cmap(i) for i in range(len(df_aov_cat))][::-1],
                      edgecolor=BG, linewidth=0.4)
for bar, val in zip(hbars2, vals_d2):
    ax_d2.text(val + vals_d2.max()*0.01,
               bar.get_y() + bar.get_height()/2,
               f"${val:.0f}", va="center", fontsize=8, color=TEXT)
ax_d2.set_xlabel("Avg Item Value (USD)", color=MUTED)
ax_d2.set_title("D  |  Avg Item Value Theo Danh Muc (Top 15)")
ax_d2.grid(axis="x", alpha=0.35)
ax_d2.tick_params(axis="y", labelsize=8)
style_ax(ax_d2)

# ── Save & open ──────────────────────────────────────────────
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "olist_dashboard.png")
plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=BG, edgecolor="none")
print(f"Da luu: {out}")
subprocess.Popen(["explorer", out])
