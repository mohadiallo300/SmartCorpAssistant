"""
app.py - Interface Streamlit pour la boutique SmartCorp
"""

import asyncio
import ast
import json
import re
from pathlib import Path

import requests
import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from LangGraph import smartcorp_assistant


# ============================================================================
# ===== CONFIG =====
# ============================================================================

BASE_IMAGE_URL = "https://scdakar.mondjago.com"


# ============================================================================
# ===== CONFIG PAGE =====
# ============================================================================

st.set_page_config(
    page_title="SmartCorp Boutique",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================================
# ===== CSS =====
# ============================================================================

st.markdown("""
<style>
    .stApp { background: linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%); }
    section[data-testid="stSidebar"] { background: white; border-right: 1px solid #e2e8f0; }
    #MainMenu, footer, header {visibility: hidden;}

    .main-header {
        background: linear-gradient(135deg, #1e40af 0%, #7c3aed 100%);
        padding: 2rem 2.5rem;
        border-radius: 20px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 10px 40px rgba(30, 64, 175, 0.25);
        position: relative;
        overflow: hidden;
    }
    .main-header::before {
        content: "";
        position: absolute;
        top: -50%; right: -10%;
        width: 300px; height: 300px;
        background: radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 70%);
        border-radius: 50%;
    }
    .main-header h1 {
        margin: 0; font-size: 2.2rem; font-weight: 800;
        color: white !important; letter-spacing: -0.5px;
        position: relative; z-index: 1;
    }
    .main-header p {
        margin: 0.5rem 0 0 0; font-size: 1rem;
        color: rgba(255,255,255,0.92) !important;
        position: relative; z-index: 1;
    }
    .status-dot {
        display: inline-block; width: 8px; height: 8px;
        background: #10b981; border-radius: 50%; margin-right: 6px;
        box-shadow: 0 0 8px #10b981; animation: pulse 2s infinite;
    }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

    .product-card {
        background: white;
        border-radius: 14px;
        padding: 1.2rem;
        box-shadow: 0 2px 12px rgba(15, 23, 42, 0.06);
        border: 1px solid #e2e8f0;
        transition: all 0.25s ease;
        display: flex; flex-direction: column;
    }
    .product-card:hover {
        box-shadow: 0 12px 32px rgba(30, 64, 175, 0.15);
        transform: translateY(-3px);
        border-color: #93c5fd;
    }
    .product-image-wrapper {
        width: 100%;
        height: 160px;
        background: linear-gradient(135deg, #f8fafc, #eff6ff) !important;
        border-radius: 10px;
        margin-bottom: 0.9rem;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        border: 1px solid #e2e8f0;
        position: relative;
        color: #94a3b8;
    }
    .product-image {
        width: 100%;
        height: 100%;
        object-fit: contain;
        padding: 8px;
        transition: transform 0.3s ease;
        background: transparent !important;
    }
    .product-card:hover .product-image { transform: scale(1.06); }
    .product-image-placeholder {
        font-size: 3rem;
        opacity: 0.35;
        display: inline-block;
    }
    .product-badges {
        display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 0.8rem;
    }
    .badge-code {
        display: inline-block;
        background: linear-gradient(135deg, #eff6ff, #dbeafe);
        color: #1d4ed8 !important;
        font-size: 0.68rem; font-weight: 700;
        padding: 4px 9px; border-radius: 6px;
        letter-spacing: 0.5px; font-family: 'Monaco', monospace;
    }
    .badge-brand {
        display: inline-block;
        background: linear-gradient(135deg, #faf5ff, #f3e8ff);
        color: #7c3aed !important;
        font-size: 0.68rem; font-weight: 700;
        padding: 4px 9px; border-radius: 6px;
        letter-spacing: 0.5px; text-transform: uppercase;
    }
    .product-name {
        font-size: 1.02rem; font-weight: 700;
        color: #0f172a !important; margin: 0 0 0.4rem 0;
        line-height: 1.35; min-height: 2.7rem;
    }
    .product-desc {
        font-size: 0.78rem; color: #64748b !important;
        margin: 0 0 0.8rem 0; line-height: 1.4; min-height: 2rem;
        display: -webkit-box; -webkit-line-clamp: 2;
        -webkit-box-orient: vertical; overflow: hidden;
    }
    .product-price {
        font-size: 1.35rem; font-weight: 800;
        color: #059669 !important; margin: 0.3rem 0 0.7rem 0;
        letter-spacing: -0.5px;
    }
    .product-price::after {
        content: " FCFA"; font-size: 0.75rem; font-weight: 600;
        color: #94a3b8 !important; letter-spacing: 0;
    }
    .stock-badge {
        display: inline-flex; align-items: center; gap: 5px;
        font-size: 0.75rem; font-weight: 600;
        padding: 5px 10px; border-radius: 8px;
        width: fit-content;
    }
    .stock-ok { background: #dcfce7; color: #166534 !important; }
    .stock-low { background: #fef3c7; color: #92400e !important; }
    .stock-out { background: #fee2e2; color: #991b1b !important; }
    .stock-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
    .stock-ok .stock-dot { background: #16a34a; }
    .stock-low .stock-dot { background: #d97706; }
    .stock-out .stock-dot { background: #dc2626; }

    .stat-card {
        background: white; border-radius: 14px;
        padding: 1.3rem 1.4rem;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
        border-left: 4px solid; height: 100%;
    }
    .stat-card.blue { border-color: #3b82f6; }
    .stat-card.green { border-color: #10b981; }
    .stat-card.amber { border-color: #f59e0b; }
    .stat-card.red { border-color: #ef4444; }
    .stat-card.purple { border-color: #8b5cf6; }
    .stat-label {
        font-size: 0.72rem; color: #64748b !important;
        font-weight: 600; text-transform: uppercase; letter-spacing: 0.7px;
    }
    .stat-value {
        font-size: 1.9rem; font-weight: 800;
        color: #0f172a !important; margin-top: 0.35rem;
        letter-spacing: -0.5px; line-height: 1;
    }
    .stat-unit {
        font-size: 0.85rem; font-weight: 500;
        color: #94a3b8 !important; margin-left: 4px;
    }
    .section-title {
        font-size: 1rem; font-weight: 700;
        color: #1e293b !important; margin: 1.2rem 0 0.8rem 0;
        display: flex; align-items: center; gap: 8px;
    }
    .section-title::before {
        content: ""; width: 4px; height: 18px;
        background: linear-gradient(180deg, #3b82f6, #7c3aed);
        border-radius: 2px;
    }
    .sidebar-logo {
        display: flex; align-items: center; gap: 12px;
        margin-bottom: 1.5rem; padding-bottom: 1rem;
        border-bottom: 1px solid #e2e8f0;
    }
    .sidebar-logo-icon {
        width: 42px; height: 42px;
        background: linear-gradient(135deg, #1e40af, #7c3aed);
        border-radius: 12px; display: flex;
        align-items: center; justify-content: center;
        font-size: 1.4rem;
        box-shadow: 0 4px 12px rgba(30, 64, 175, 0.25);
    }
    .sidebar-logo-text h3 {
        margin: 0; font-size: 1.1rem; font-weight: 800;
        color: #0f172a !important; letter-spacing: -0.3px;
    }
    .sidebar-logo-text p {
        margin: 0; font-size: 0.75rem;
        color: #64748b !important;
    }

    div[data-testid="stChatMessage"] {
        background: transparent !important;
        padding: 0.4rem 0 !important;
    }
    div[data-testid="stChatMessageContent"] {
        background: #ffffff !important;
        color: #0f172a !important;
        border-radius: 14px !important;
        padding: 1rem 1.2rem !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05) !important;
    }
    div[data-testid="stChatMessageContent"] p,
    div[data-testid="stChatMessageContent"] li,
    div[data-testid="stChatMessageContent"] span,
    div[data-testid="stChatMessageContent"] strong,
    div[data-testid="stChatMessageContent"] em,
    div[data-testid="stChatMessageContent"] a,
    div[data-testid="stChatMessageContent"] h1,
    div[data-testid="stChatMessageContent"] h2,
    div[data-testid="stChatMessageContent"] h3,
    div[data-testid="stChatMessageContent"] h4,
    div[data-testid="stChatMessageContent"] h5,
    div[data-testid="stChatMessageContent"] code,
    div[data-testid="stChatMessageContent"] td,
    div[data-testid="stChatMessageContent"] th,
    div[data-testid="stChatMessageContent"] div {
        color: #0f172a !important;
    }
    div[data-testid="stChatMessageContent"] a {
        color: #2563eb !important; text-decoration: underline;
    }
    div[data-testid="stChatMessageContent"] table {
        border-collapse: collapse; width: 100%; margin: 0.5rem 0;
    }
    div[data-testid="stChatMessageContent"] th {
        background: #f1f5f9 !important; font-weight: 700;
    }
    div[data-testid="stChatMessageContent"] th,
    div[data-testid="stChatMessageContent"] td {
        border: 1px solid #e2e8f0 !important;
        padding: 6px 10px !important;
    }

    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) div[data-testid="stChatMessageContent"] {
        background: linear-gradient(135deg, #1e40af, #3b82f6) !important;
        border: none !important;
    }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) div[data-testid="stChatMessageContent"] p,
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) div[data-testid="stChatMessageContent"] span,
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) div[data-testid="stChatMessageContent"] strong {
        color: #ffffff !important;
    }

    .stButton > button {
        border-radius: 10px; font-weight: 600;
        transition: all 0.2s; border: 1px solid #e2e8f0;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(30, 64, 175, 0.15);
        border-color: #93c5fd;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# ===== SESSION STATE =====
# ============================================================================

if "messages" not in st.session_state:
    st.session_state.messages = []
if "langchain_history" not in st.session_state:
    st.session_state.langchain_history = []
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None
if "selected_product" not in st.session_state:
    st.session_state.selected_product = None
if "event_loop" not in st.session_state:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    st.session_state.event_loop = loop


# ============================================================================
# ===== HELPERS =====
# ============================================================================

def get_event_loop():
    if "event_loop" not in st.session_state:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        st.session_state.event_loop = loop
    return st.session_state.event_loop


def run_async(coro):
    loop = get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        st.session_state.event_loop = loop
    return loop.run_until_complete(coro)


def resolve_photo_url(photo) -> str:
    if not photo or not isinstance(photo, str):
        return ""
    photo = photo.strip()
    if not photo or len(photo) < 5:
        return ""
    if photo.startswith(("http://", "https://", "data:")):
        return photo
    if BASE_IMAGE_URL:
        return BASE_IMAGE_URL.rstrip("/") + "/" + photo.lstrip("/")
    return ""


def fetch_image_bytes(url: str):
    """Télécharge une image et retourne ses bytes (ou None)."""
    if not url:
        return None
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Referer": BASE_IMAGE_URL + "/" if BASE_IMAGE_URL else "",
        }
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200 and len(r.content) > 100:
            return r.content
    except Exception:
        pass
    return None


def extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return str(content)


def parse_content(content):
    if isinstance(content, (list, dict)):
        return content
    if not isinstance(content, str):
        return None
    content = content.strip()
    if not content:
        return None
    try:
        return json.loads(content)
    except (json.JSONDecodeError, ValueError):
        pass
    try:
        return ast.literal_eval(content)
    except (ValueError, SyntaxError):
        pass
    return None


def extract_tool_data(messages):
    products = []
    stats = None
    low_stock = []

    for msg in messages:
        if isinstance(msg, ToolMessage):
            data = parse_content(msg.content)
            if data is None:
                continue

            if isinstance(data, list) and data and isinstance(data[0], dict):
                if "code_produit" in data[0]:
                    products.extend(data)
            elif isinstance(data, dict):
                if "total_produits" in data and "valeur_totale_stock" in data:
                    stats = data
                elif all(k in data for k in ("code_produit", "quantite", "en_alerte")):
                    low_stock.append(data)

    return products, stats, low_stock


def filter_products_by_response(products: list, response_text: str) -> list:
    if not products or not response_text:
        return []
    codes_in_text = set(re.findall(r'\bSC\d{3,6}[A-Z]?\b', response_text.upper()))
    if not codes_in_text:
        return []
    filtered = [
        p for p in products
        if str(p.get("code_produit", "")).upper() in codes_in_text
    ]
    return filtered


# ============================================================================
# ===== CHAT ASYNC AVEC RETRY =====
# ============================================================================

async def _invoke_with_retry(coro_factory, max_retries=3, base_delay=1.5):
    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            return await coro_factory()
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                await asyncio.sleep(delay)
            else:
                break
    raise last_exception


async def chat_async(user_message: str) -> dict:
    history_before = list(st.session_state.langchain_history)
    n_before = len(history_before)

    async def _do_invoke():
        return await smartcorp_assistant.ainvoke(
            {"messages": history_before + [HumanMessage(content=user_message)]},
            config={"recursion_limit": 25},
        )

    result = await _invoke_with_retry(_do_invoke, max_retries=3, base_delay=2)

    st.session_state.langchain_history = result["messages"]

    new_messages = result["messages"][n_before:]
    products, stats, low_stock = extract_tool_data(new_messages)
    final = result["messages"][-1]
    response_text = extract_text(final.content)
    products = filter_products_by_response(products, response_text)

    return {
        "response": response_text,
        "products": products,
        "stats": stats,
        "low_stock": low_stock,
    }


# ============================================================================
# ===== DIALOG DÉTAILS =====
# ============================================================================

@st.dialog("📦 Détails du produit", width="large")
def show_product_dialog(product: dict):
    code = product.get("code_produit", "—")
    nom = product.get("nom_du_produit", "Produit sans nom")
    marque = product.get("marque", "—")
    categorie = product.get("categorie", "—")
    desc = product.get("description") or "Aucune description disponible."
    prix = product.get("prix_de_vente", 0)
    qte = int(product.get("quantite", 0) or 0)
    seuil = int(product.get("seuil", 5) or 5)
    photo_url = resolve_photo_url(product.get("photo"))
    boutique = product.get("boutique", "—")

    # ✅ FIX : on télécharge l'image et on l'affiche avec st.image
    # (même méthode que dans les cartes produits)
    if photo_url:
        img_bytes = fetch_image_bytes(photo_url)
        if img_bytes:
            col_img_1, col_img_2, col_img_3 = st.columns([1, 3, 1])
            with col_img_2:
                st.image(img_bytes, use_container_width=True)
        else:
            st.markdown("""
                <div style="background: linear-gradient(135deg, #f8fafc, #eff6ff);
                            border-radius: 14px; padding: 2rem; margin-bottom: 1rem;
                            display: flex; justify-content: center; align-items: center;
                            border: 1px solid #e2e8f0; min-height: 200px;">
                    <span style="font-size:5rem; opacity:0.3;">📦</span>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <div style="background: linear-gradient(135deg, #f8fafc, #eff6ff);
                        border-radius: 14px; padding: 2rem; margin-bottom: 1rem;
                        display: flex; justify-content: center; align-items: center;
                        border: 1px solid #e2e8f0; min-height: 200px;">
                <span style="font-size:5rem; opacity:0.3;">📦</span>
            </div>
        """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(f'<span class="badge-code">{code}</span>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<span class="badge-brand">{marque}</span>', unsafe_allow_html=True)

    st.markdown(f"## {nom}")
    st.markdown(f"**Catégorie :** {categorie}  |  **Boutique :** {boutique}")
    st.markdown("---")

    try:
        prix_str = f"{float(prix):,.0f}".replace(",", " ")
    except (ValueError, TypeError):
        prix_str = "—"

    st.markdown(f"""
        <div style="background: linear-gradient(135deg, #ecfdf5, #d1fae5);
                    padding: 1.2rem; border-radius: 12px;
                    border-left: 4px solid #059669; margin-bottom: 1rem;">
            <div style="font-size: 0.75rem; color: #047857; font-weight: 600;
                        text-transform: uppercase; letter-spacing: 0.5px;">
                Prix de vente
            </div>
            <div style="font-size: 2rem; font-weight: 800;
                        color: #059669; letter-spacing: -0.5px;">
                {prix_str} <span style="font-size: 0.9rem; color: #64748b;
                                       font-weight: 500;">FCFA</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    s_class, s_text = stock_class(qte, seuil)
    st.markdown(f"""
        <div style="background: white; padding: 1rem 1.2rem;
                    border-radius: 12px; border: 1px solid #e2e8f0;
                    margin-bottom: 1rem; display: flex;
                    justify-content: space-between; align-items: center;">
            <div>
                <div style="font-size: 0.72rem; color: #64748b;
                            font-weight: 600; text-transform: uppercase;">
                    Disponibilité
                </div>
                <div style="font-size: 1.1rem; font-weight: 700; color: #0f172a;
                            margin-top: 0.2rem;">
                    {qte} unité(s)
                </div>
            </div>
            <div class="stock-badge {s_class}">
                <span class="stock-dot"></span>{s_text}
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("### 📝 Description")
    st.markdown(f"{desc}")
    st.markdown("---")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("💬 Demander à l'assistant", use_container_width=True, type="primary"):
            st.session_state.pending_prompt = (
                f"Donne-moi plus de détails sur le produit {code} "
                f"et propose-moi des alternatives similaires."
            )
            st.session_state.selected_product = None
            st.rerun()
    with col_b:
        if st.button("🚫 Fermer", use_container_width=True):
            st.session_state.selected_product = None
            st.rerun()


# ============================================================================
# ===== RENDER =====
# ============================================================================

def stock_class(quantite: int, seuil: int = 5) -> tuple[str, str]:
    if quantite <= 0:
        return "stock-out", "Rupture"
    if quantite <= seuil:
        return "stock-low", f"Stock faible ({quantite})"
    return "stock-ok", f"En stock ({quantite})"


def format_price(prix) -> str:
    try:
        return f"{float(prix):,.0f}".replace(",", " ")
    except (ValueError, TypeError):
        return "—"


def render_product_grid(products: list, cols: int = 3, key_prefix: str = ""):
    if not products:
        return

    st.markdown(
        f'<div class="section-title">🛍️ {len(products)} produit(s) affiché(s)</div>',
        unsafe_allow_html=True,
    )

    for i in range(0, len(products), cols):
        row = products[i:i + cols]
        col_objs = st.columns(cols, gap="medium")

        for idx, (col, p) in enumerate(zip(col_objs, row)):
            with col:
                code = p.get("code_produit", "—")
                nom = p.get("nom_du_produit", "Produit sans nom")
                marque = (p.get("marque") or "—").upper()
                desc = p.get("description") or "Aucune description disponible."
                prix = format_price(p.get("prix_de_vente"))
                qte = int(p.get("quantite", 0) or 0)
                seuil = int(p.get("seuil", 5) or 5)

                photo_url = resolve_photo_url(p.get("photo"))
                img_bytes = fetch_image_bytes(photo_url)

                s_class, s_text = stock_class(qte, seuil)

                if img_bytes:
                    st.image(img_bytes, use_container_width=True)
                else:
                    st.markdown("""
                        <div class="product-image-wrapper">
                            <span class="product-image-placeholder">📦</span>
                        </div>
                    """, unsafe_allow_html=True)

                st.markdown(f"""
                    <div class="product-card">
                        <div class="product-badges">
                            <span class="badge-code">{code}</span>
                            <span class="badge-brand">{marque}</span>
                        </div>
                        <div class="product-name">{nom}</div>
                        <div class="product-desc">{desc[:120]}</div>
                        <div class="product-price">{prix}</div>
                        <div class="stock-badge {s_class}">
                            <span class="stock-dot"></span>{s_text}
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                btn_key = f"detail_{key_prefix}_{i}_{idx}_{code}"
                if st.button(
                    "🔍 Voir détails",
                    key=btn_key,
                    use_container_width=True,
                    type="primary",
                ):
                    st.session_state.selected_product = p


def render_stats(stats: dict):
    if not stats:
        return

    st.markdown(
        '<div class="section-title">📊 Vue d\'ensemble du catalogue</div>',
        unsafe_allow_html=True,
    )

    cols = st.columns(4, gap="medium")
    cards = [
        ("blue",   "Produits",        f"{stats.get('total_produits', 0):,}".replace(",", " "), ""),
        ("green",  "Valeur du stock", f"{stats.get('valeur_totale_stock', 0):,.0f}".replace(",", " "), "FCFA"),
        ("purple", "Catégories",      stats.get("nombre_categories", 0), ""),
        ("amber",  "Marques",         stats.get("nombre_marques", 0), ""),
    ]

    for col, (color, label, value, unit) in zip(cols, cards):
        with col:
            st.markdown(f"""
                <div class="stat-card {color}">
                    <div class="stat-label">{label}</div>
                    <div class="stat-value">{value}<span class="stat-unit">{unit}</span></div>
                </div>
            """, unsafe_allow_html=True)

    rupture = stats.get("en_rupture", 0)
    alerte = stats.get("en_alerte", 0)

    if rupture > 0 or alerte > 0:
        col1, col2 = st.columns(2, gap="medium")
        with col1:
            st.markdown(f"""
                <div class="stat-card red">
                    <div class="stat-label">🚨 En rupture</div>
                    <div class="stat-value">{rupture}</div>
                </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
                <div class="stat-card amber">
                    <div class="stat-label">⚠️ En alerte</div>
                    <div class="stat-value">{alerte}</div>
                </div>
            """, unsafe_allow_html=True)


def render_bot_message(msg: dict, key_prefix: str):
    st.markdown(msg["content"])

    if msg.get("products"):
        render_product_grid(msg["products"], key_prefix=key_prefix)

    if msg.get("stats"):
        render_stats(msg["stats"])


# ============================================================================
# ===== CALLBACKS =====
# ============================================================================

def set_pending_prompt(prompt: str):
    st.session_state.pending_prompt = prompt


def reset_conversation():
    st.session_state.messages = []
    st.session_state.langchain_history = []
    st.session_state.pending_prompt = None
    st.session_state.selected_product = None


# ============================================================================
# ===== SIDEBAR =====
# ============================================================================

with st.sidebar:
    st.markdown("""
        <div class="sidebar-logo">
            <div class="sidebar-logo-icon">🛒</div>
            <div class="sidebar-logo-text">
                <h3>SmartCorp</h3>
                <p>Boutique intelligente</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-title">⚡ Actions rapides</div>', unsafe_allow_html=True)

    quick_actions = [
        ("📊 Statistiques catalogue", "Résume-moi le catalogue avec les statistiques globales"),
        ("🚨 Produits en alerte",     "Quels produits sont en rupture ou en alerte de stock ?"),
        ("💻 Top laptops",            "Montre-moi les laptops disponibles, triés par prix"),
        ("🎧 Accessoires pas chers",  "Quels accessoires coûtent moins de 25000 FCFA ?"),
        ("🔍 Rechercher un produit",  "Cherche-moi un produit Lenovo"),
    ]

    for label, prompt in quick_actions:
        st.button(
            label,
            key=f"qa_{label}",
            use_container_width=True,
            on_click=set_pending_prompt,
            args=(prompt,),
        )

    st.markdown("---")

    st.button(
        "🔄 Nouvelle conversation",
        use_container_width=True,
        on_click=reset_conversation,
        type="secondary",
    )

    st.markdown("---")

    with st.expander("🔍 Debug : URLs d'images"):
        has_any = False
        for msg in st.session_state.messages:
            for p in msg.get("products", []):
                has_any = True
                code = p.get("code_produit", "?")
                raw = p.get("photo", "")
                resolved = resolve_photo_url(raw)
                st.markdown(f"**{code}**")
                st.code(f"brut  : {raw}\nfinal : {resolved or '(aucune)'}")
        if not has_any:
            st.caption("Aucun produit affiché pour l'instant.")

    st.markdown("---")

    st.markdown("""
        <div style="font-size: 0.75rem; color: #64748b; line-height: 1.6;">
            <b>💡 Astuces</b><br>
            • Demande des produits par budget<br>
            • Vérifie la disponibilité avec un code<br>
            • Clique <b>Voir détails</b> sur une carte
        </div>
    """, unsafe_allow_html=True)


# ============================================================================
# ===== HEADER =====
# ============================================================================

st.markdown("""
    <div class="main-header">
        <h1>🛒 SmartCorp Boutique</h1>
        <p><span class="status-dot"></span>Assistant intelligent connecté — Catalogue en temps réel</p>
    </div>
""", unsafe_allow_html=True)


# ============================================================================
# ===== DIALOG DÉTAILS (affiché en priorité si un produit est sélectionné) =====
# ============================================================================

if st.session_state.selected_product is not None:
    show_product_dialog(st.session_state.selected_product)


# ============================================================================
# ===== FONCTION CENTRALE =====
# ============================================================================

def process_and_display(user_text: str):
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_text)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("💭 Traitement de votre demande en cours..."):
            try:
                result = run_async(chat_async(user_text))
                error_occurred = False
                error_message = ""
            except Exception as e:
                error_occurred = True
                error_message = str(e)
                result = None

    st.session_state.messages.append({"role": "user", "content": user_text})

    if error_occurred:
        st.session_state.messages.append({
            "role": "bot",
            "content": (
                "❌ **Le système est temporairement indisponible.**\n\n"
                "Après 3 tentatives automatiques, le serveur n'a pas répondu.\n\n"
                "Merci de réessayer dans quelques instants."
            ),
            "products": [],
            "stats": None,
            "error_detail": error_message,
        })
    else:
        st.session_state.messages.append({
            "role": "bot",
            "content": result["response"],
            "products": result.get("products", []),
            "stats": result.get("stats"),
        })

    st.rerun()


# ============================================================================
# ===== AFFICHAGE HISTORIQUE =====
# ============================================================================

for msg_idx, msg in enumerate(st.session_state.messages):
    role = msg["role"]

    if role == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant", avatar="🤖"):
            if msg.get("error_detail"):
                st.error(msg["content"])
                with st.expander("🔧 Détail technique"):
                    st.code(msg["error_detail"])
            else:
                render_bot_message(msg, key_prefix=f"msg_{msg_idx}")


# ============================================================================
# ===== DÉCLENCHEUR 1 : RACCOURCIS SIDEBAR =====
# ============================================================================

if st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None
    process_and_display(prompt)


# ============================================================================
# ===== DÉCLENCHEUR 2 : SAISIE LIBRE =====
# ============================================================================

user_input = st.chat_input("Posez votre question sur le catalogue...")

if user_input:
    process_and_display(user_input)