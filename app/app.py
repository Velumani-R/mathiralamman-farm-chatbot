import base64
import csv
import re
from pathlib import Path

import streamlit as st
from retriever import retrieve_top

st.set_page_config(page_title="VeluDevi Farm Support Virtual Assistant", page_icon="🌾")

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"

REAL_DATA_PATH = DATA_DIR / "inventory.csv"
DEMO_DATA_PATH = DATA_DIR / "inventory_demo.csv"
LOGO_PATH = ASSETS_DIR / "logo.png"


def logo_base64(path: Path) -> str:
    if not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def load_inventory_from_csv(path: Path):
    if not path.exists():
        raise FileNotFoundError(str(path))

    items = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        # Normalize headers (strip spaces / case)
        if reader.fieldnames:
            reader.fieldnames = [h.strip() for h in reader.fieldnames]

        for row in reader:
            # Defensive: support slight header variations too
            product = (row.get("product") or row.get("Product") or row.get("PRODUCT") or "").strip()
            if not product:
                continue

            price_raw = row.get("price_cad") or row.get("Price (CAD)") or row.get("price") or ""
            unit = (row.get("unit") or row.get("Unit") or "").strip()
            stock_raw = row.get("stock_qty") or row.get("Stock") or row.get("stock") or ""
            last_updated = (row.get("last_updated") or row.get("Last Updated") or "").strip()
            notes = (row.get("notes") or row.get("Notes") or "").strip()

            try:
                price_cad = float(price_raw)
            except Exception:
                price_cad = None

            try:
                stock_qty = int(float(stock_raw))
            except Exception:
                stock_qty = None

            items.append(
                {
                    "product": product,
                    "product_norm": product.lower(),
                    "price_cad": price_cad,
                    "unit": unit,
                    "stock_qty": stock_qty,
                    "last_updated": last_updated,
                    "notes": notes,
                }
            )
    return items


def find_product(text: str, products_norm):
    t = text.lower()
    for p in products_norm:
        if p and p in t:
            return p
    if "okra" in t:
        return "ladies finger"
    if "cassava" in t:
        return "yucca"
    return None


def is_product_list_question(q: str) -> bool:
    q = q.lower()
    patterns = [
        r"what\s+product",
        r"what\s+products",
        r"which\s+products",
        r"list\s+products",
        r"products\s+you\s+have",
        r"items\s+you\s+sell",
        r"what\s+do\s+you\s+sell",
        r"what\s+produce",
    ]
    return any(re.search(p, q) for p in patterns)


def format_inventory_answer(item: dict) -> str:
    price = item.get("price_cad")
    price_str = f"{price:.2f}" if isinstance(price, float) else "N/A"

    stock = item.get("stock_qty")
    stock_msg = ""
    if isinstance(stock, int):
        stock_msg = "✅ In stock" if stock > 0 else "❌ Out of stock"

    return (
        f"**{item.get('product','')}**\n\n"
        f"- Price: **${price_str} CAD** per **{item.get('unit','unit')}**\n"
        f"- Stock: **{item.get('stock_qty','N/A')}** {stock_msg}\n"
        f"- Last updated: **{item.get('last_updated','N/A')}**"
    )


# ---------- Header ----------
LOGO_B64 = logo_base64(LOGO_PATH)
logo_html = "🥥"
if LOGO_B64:
    logo_html = f"<img src='data:image/png;base64,{LOGO_B64}'/>"

st.markdown(
    f"""
    <style>
    .vd-header {{
        background: linear-gradient(90deg, #2e7d32, #66bb6a);
        padding: 14px 18px;
        border-radius: 12px;
        margin-bottom: 10px;
        color: white;
        display: flex;
        align-items: center;
        gap: 12px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.08);
    }}
    .vd-logo {{
        width: 46px;
        height: 46px;
        border-radius: 10px;
        background: rgba(255,255,255,0.18);
        display:flex;
        align-items:center;
        justify-content:center;
        overflow:hidden;
        font-size: 26px;
    }}
    .vd-logo img {{
        width: 100%;
        height: 100%;
        object-fit: cover;
    }}
    .vd-title {{
        font-size: 22px;
        font-weight: 800;
    }}
    .vd-subtitle {{
        font-size: 13px;
        opacity: 0.95;
    }}
    .demo-badge {{
        background: #fff3cd;
        color: #856404;
        border: 1px solid #ffeeba;
        padding: 6px 10px;
        border-radius: 6px;
        font-size: 12px;
        margin-bottom: 12px;
    }}
    .vd-footer {{
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background: rgba(255,255,255,0.92);
        border-top: 1px solid rgba(0,0,0,0.06);
        padding: 8px 14px;
        font-size: 12px;
        color: #444;
        z-index: 999;
        backdrop-filter: blur(6px);
    }}
    </style>

    <div class="vd-header">
        <div class="vd-logo">{logo_html}</div>
        <div>
            <div class="vd-title">VeluDevi Farm Support Virtual Assistant</div>
            <div class="vd-subtitle">
                Products • Pricing • Policies • Delivery • Hours (No guessing)
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------- Demo Mode ----------
demo_mode = st.toggle("🧪 Demo mode (safe sample data for recruiters)", value=False)

inventory_path = DEMO_DATA_PATH if demo_mode else REAL_DATA_PATH
inventory_source_name = inventory_path.name

if demo_mode:
    st.markdown(
        "<div class='demo-badge'>🧪 <b>DEMO MODE ON</b> — Using inventory_demo.csv</div>",
        unsafe_allow_html=True,
    )

try:
    inventory = load_inventory_from_csv(inventory_path)
except FileNotFoundError:
    st.error(f"Inventory file not found: {inventory_path}")
    st.stop()

products_norm = [i["product_norm"] for i in inventory]

# ---------- Chat ----------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "👋 Hi! You can ask:\n"
                "- *What products do you have?*\n"
                "- *What is the price of tomato?*\n"
                "- *Delivery policy? Refund policy?*\n"
                "- *Business hours?*"
            ),
        }
    ]

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

q = st.chat_input("Ask a question…")

if q:
    st.session_state.messages.append({"role": "user", "content": q})
    with st.chat_message("user"):
        st.markdown(q)

    match = find_product(q, products_norm)

    with st.chat_message("assistant"):
        if is_product_list_question(q):
            names = sorted({i["product"] for i in inventory if i.get("product")})
            if not names:
                answer = (
                    "I couldn’t read any product names from the inventory file.\n\n"
                    f"Please verify the first line of **{inventory_source_name}** is:\n"
                    "`product,price_cad,unit,stock_qty,last_updated,notes`"
                )
            else:
                answer = (
                    "**We currently offer the following products:**\n\n"
                    + "\n".join([f"• {n}" for n in names])
                    + "\n\nAsk me about price or availability for any item."
                )
            st.markdown(answer)

        elif match:
            item = next(i for i in inventory if i["product_norm"] == match)
            answer = format_inventory_answer(item)
            st.markdown(answer)

        else:
            top = retrieve_top(q, top_k=3)
            if not top or top[0]["score"] < 2:
                answer = (
                    "I can help with **products**, **pricing**, **policies**, "
                    "**delivery**, and **business hours**.\n\n"
                    "Try: *What products do you have?* or *Refund policy?*"
                )
                st.markdown(answer)
            else:
                best = top[0]
                answer = f"**Answer (from {best['source']})**:\n\n{best['chunk']}"
                st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})

# ---------- Footer ----------
st.markdown(
    f"""
    <div class="vd-footer">
        ℹ️ Answers come from <b>{inventory_source_name}</b> (products/pricing/stock) and farm documents (policies & FAQ).
        This assistant does not hallucinate information.
    </div>
    """,
    unsafe_allow_html=True,
)
