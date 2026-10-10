"""
API_SmartCorp.py - Module d'accès API Smart Corporation
+ Tools LangChain intégrés
Gère cache, validation, requêtes API asynchrones, et outils pour agents LLM
"""

# ===== IMPORTS =====
from api_class import Article, create_article, CATEGORIE_MAP
from collections import OrderedDict
from cachetools import TTLCache
import aiohttp
import asyncio
import logging
import time
from typing import Dict, List, Optional, Any
from config.settings import Config

# LangChain
from langchain_core.tools import tool


# ===== LOGGING =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ===== CONFIGURATION =====
CACHE_MAX_SIZE = 1000
CACHE_TTL = 600  # 10 minutes

cache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=CACHE_TTL)

API_URL = Config.API_URL
API_KEY = Config.API_KEY


# ============================================================================
# ===== HELPERS =====
# ============================================================================

def _get_attr(obj: Any, key: str, default: Any = '') -> Any:
    """Accès uniforme aux attributs (dict OU Article)."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _product_to_dict(product: Any) -> Dict:
    """
    Convertit un Article (ou dict) en dict JSON-sérialisable.
    Utilisé partout pour garantir la compatibilité LangChain.
    """
    if isinstance(product, dict):
        return product

    nom = (
        _get_attr(product, 'nom_du_produit', None)
        or _get_attr(product, 'nom_produit', None)
        or _get_attr(product, 'nom', None)
    )

    return {
        'id':             _get_attr(product, 'id', None),
        'code_produit':   _get_attr(product, 'code_produit', None),
        'nom_du_produit': nom,
        'marque':         _get_attr(product, 'marque', None),
        'categorie':      _get_attr(product, 'categorie', None),
        'quantite':       _get_attr(product, 'quantite', None),
        'description':    _get_attr(product, 'description', None),
        'prix_de_vente':  _get_attr(product, 'prix_de_vente', None),
        'photo':          _get_attr(product, 'photo', None),
        'boutique':       _get_attr(product, 'boutique', None),
        'seuil':          _get_attr(product, 'seuil', None),
    }


# ============================================================================
# ===== VALIDATION =====
# ============================================================================

def is_valid_product(product: Dict) -> bool:
    """Vérifie qu'un produit a tous les champs requis."""
    required_fields = [
        'code_produit', 'nom_du_produit', 'marque',
        'categorie', 'quantite', 'prix_de_vente', 'photo'
    ]
    for field in required_fields:
        value = product.get(field)
        if value is None or (isinstance(value, str) and value.strip() == ''):
            return False
    return True


# ============================================================================
# ===== CACHE MANAGEMENT =====
# ============================================================================

async def clear_cache():
    """Nettoie le cache."""
    cache.expire()
    logger.info(f"✅ Cache nettoyé - Taille: {len(cache)}")


async def get_cache_stats() -> Dict:
    """Retourne les stats du cache."""
    return {
        "size": len(cache),
        "max_size": CACHE_MAX_SIZE,
        "ttl": CACHE_TTL,
    }


async def invalidate_cache() -> bool:
    """Force le rechargement au prochain appel de get_data()."""
    try:
        if 'data' in cache:
            del cache['data']
            logger.info("🔄 Cache invalidé")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Erreur invalidate_cache: {e}")
        return False


# ============================================================================
# ===== API FETCH =====
# ============================================================================

async def get_products_from_api(retries: int = 3, timeout: int = 60) -> List:
    """
    Récupère les produits depuis l'API Smart Corporation.
    Retry automatique avec backoff exponentiel + timeout configurable.
    """
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json',
    }

    for attempt in range(1, retries + 1):
        try:
            logger.info(f"🔄 Récupération API... (tentative {attempt}/{retries})")

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    API_URL,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:

                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"✅ {len(data)} produits reçus de l'API")

                        products = []
                        invalid_count = 0

                        for product_data in data:
                            product_data = {
                                key.replace(' ', '_').lower(): value
                                for key, value in product_data.items()
                            }

                            if not is_valid_product(product_data):
                                invalid_count += 1
                                logger.warning(
                                    f"⚠️ Produit invalide: "
                                    f"{product_data.get('code_produit', 'UNKNOWN')}"
                                )
                                continue

                            try:
                                article = create_article(product_data)
                                products.append(article)
                            except Exception as e:
                                logger.error(
                                    f"❌ Erreur création article "
                                    f"{product_data.get('code_produit', 'UNKNOWN')}: {e}"
                                )
                                invalid_count += 1
                                continue

                        logger.info(
                            f"✅ {len(products)} produits valides | "
                            f"❌ {invalid_count} rejetés"
                        )
                        return products

                    else:
                        error_msg = await response.text()
                        logger.error(f"❌ Erreur API {response.status}: {error_msg}")
                        return []

        except asyncio.TimeoutError:
            logger.warning(f"⏱️ Timeout ({timeout}s) - tentative {attempt}/{retries}")
            if attempt < retries:
                backoff = 2 ** attempt
                await asyncio.sleep(backoff)
            else:
                logger.error(f"❌ Échec après {retries} tentatives")
                return []

        except Exception as e:
            logger.error(f"❌ Exception API: {e}", exc_info=True)
            if attempt < retries:
                await asyncio.sleep(2 ** attempt)
            else:
                return []

    return []


async def get_data() -> List:
    """
    Récupère les données avec gestion du cache.
    Retourne une liste d'objets Article.
    """
    try:
        cache.expire()

        if 'data' in cache:
            logger.info(f"✅ Données depuis cache ({len(cache['data'])} produits)")
            return cache['data']

        logger.info("📡 Récupération depuis API...")
        data = await get_products_from_api()

        if data:
            cache['data'] = data
            logger.info(f"✅ {len(data)} produits mis en cache")
        else:
            logger.warning("⚠️ Aucune donnée retournée par l'API")

        return data

    except Exception as e:
        logger.error(f"❌ Erreur get_data: {e}", exc_info=True)
        return []


# ============================================================================
# ===== FILTRAGE PAR CATÉGORIE / MARQUE =====
# ============================================================================

# ----- TOOL LangChain (avant la fonction) -----
@tool
async def tool_filtrer_produits(
    categorie: Optional[str] = None,
    marque: Optional[str] = None,
) -> list:
    """Filtre les produits par catégorie et/ou marque.

    Utilise ce tool quand l'utilisateur veut une liste filtrée
    (ex: "tous les laptops", "les produits Lenovo", "clés USB Kingston").

    Args:
        categorie: Nom exact de la catégorie en MAJUSCULES (ex: "LAPTOPS", "CLE_USB")
        marque: Nom exact de la marque en MAJUSCULES (ex: "LENOVO", "HP")

    Retourne une liste de produits (max 50).
    """
    results = await filtre_marques_categories(categorie, marque)
    return [_product_to_dict(p) for p in results[:50]]


# ----- Fonction métier -----
async def filtre_marques_categories(
    categorie: Optional[str] = None,
    marque: Optional[str] = None,
) -> List:
    """Filtre les produits par catégorie et/ou marque (case-insensitive)."""
    try:
        products = await get_data()
        if not products:
            return []

        categorie = categorie.upper() if categorie else None
        marque = marque.upper() if marque else None

        filtered = [
            p for p in products
            if (
                (categorie is None or
                 str(_get_attr(p, 'categorie', '')).upper() == categorie) and
                (marque is None or
                 str(_get_attr(p, 'marque', '')).upper() == marque)
            )
        ]

        logger.info(
            f"✅ Filtre cat={categorie} marque={marque} → {len(filtered)}"
        )
        return filtered

    except Exception as e:
        logger.error(f"❌ Erreur filtrage: {e}", exc_info=True)
        return []


# ============================================================================
# ===== EXTRACTION VALEURS UNIQUES =====
# ============================================================================

async def nom_marques_categories(mec: str) -> List[Dict]:
    """Retourne les marques/catégories uniques (avec index)."""
    try:
        liste_articles = await get_data()
        if not liste_articles:
            return []

        carac_uniques = list(OrderedDict.fromkeys(
            _get_attr(article, mec)
            for article in liste_articles
            if _get_attr(article, mec)
        ))

        return [
            {'index': f"{mec}{i}", mec: carac}
            for i, carac in enumerate(carac_uniques)
        ]
    except Exception as e:
        logger.error(f"❌ Erreur extraction {mec}: {e}", exc_info=True)
        return []


# ============================================================================
# ===== LISTE MARQUES / CATÉGORIES =====
# ============================================================================

# ----- TOOL LangChain -----
@tool
async def tool_liste_marques() -> list:
    """Retourne la liste de toutes les marques disponibles dans le catalogue.

    Utilise ce tool avant un filtre par marque pour connaître les noms exacts.
    """
    result = await nom_marques_categories('marque')
    return [item['marque'] for item in result]


# ----- TOOL LangChain -----
@tool
async def tool_liste_categories() -> list:
    """Retourne la liste de toutes les catégories disponibles dans le catalogue.

    Utilise ce tool avant un filtre par catégorie pour connaître les noms exacts.
    """
    result = await nom_marques_categories('categorie')
    return [item['categorie'] for item in result]


# ----- Fonctions métier (wrappers simples) -----
async def get_all_marques() -> List[str]:
    result = await nom_marques_categories('marque')
    return [item['marque'] for item in result]


async def get_all_categories() -> List[str]:
    result = await nom_marques_categories('categorie')
    return [item['categorie'] for item in result]


# ============================================================================
# ===== DÉTAILS PRODUIT =====
# ============================================================================

# ----- TOOL LangChain -----
@tool
async def tool_details_produit(code_produit: str) -> dict:
    """Récupère tous les détails d'un produit par son code unique.

    Utilise ce tool quand l'utilisateur donne un code produit précis
    (ex: "SC0226F") ou après une recherche pour obtenir plus d'infos.

    Args:
        code_produit: Code unique du produit (ex: "SC0226F")

    Retourne un dict avec tous les champs du produit, ou {} si non trouvé.
    """
    result = await get_product_details(code_produit)
    return result if result else {}


# ----- Fonction métier -----
async def get_product_details(product_id: str) -> Optional[Dict]:
    """Récupère les détails d'un produit par code. Retourne TOUJOURS un dict."""
    try:
        if not product_id or not isinstance(product_id, str):
            logger.warning(f"⚠️ ID produit invalide: {product_id}")
            return None

        api_data = await get_data()
        if not api_data:
            return None

        for product in api_data:
            if _get_attr(product, 'code_produit', None) == product_id:
                logger.info(f"✅ Produit trouvé: {product_id}")
                return _product_to_dict(product)

        logger.warning(f"⚠️ Produit non trouvé: {product_id}")
        return None

    except Exception as e:
        logger.error(f"❌ Erreur get_product_details: {e}", exc_info=True)
        return None


# ============================================================================
# ===== RECHERCHE TEXTUELLE =====
# ============================================================================

# ----- TOOL LangChain -----
@tool
async def tool_rechercher_produits(
    query: str,
    limit: int = 20,
    categorie: Optional[str] = None,
) -> list:
    """Recherche des produits par mot-clé dans le nom, la marque,
    la description ou le code produit.

    Utilise ce tool quand l'utilisateur cherche par terme libre :
    "lenovo", "clé usb 64Go", "imprimante HP", "souris sans fil".

    Args:
        query: Terme de recherche (au moins 2 caractères)
        limit: Nombre max de résultats (défaut 20, max 50)
        categorie: Filtre optionnel par catégorie (MAJUSCULES)

    Retourne une liste de produits correspondants.
    """
    limit = min(limit, 50)
    return await search_products(query, limit=limit, categorie=categorie)


# ----- Fonction métier -----
async def search_products(
    query: str,
    limit: int = 20,
    categorie: Optional[str] = None,
) -> List[Dict]:
    """Recherche par mot-clé dans nom/marque/description/code."""
    try:
        if not query or not query.strip():
            return []

        products = await get_data()
        if not products:
            return []

        query_lower = query.strip().lower()
        cat_filter = categorie.upper() if categorie else None

        results = []
        for p in products:
            if cat_filter:
                if str(_get_attr(p, 'categorie', '')).upper() != cat_filter:
                    continue

            nom = str(_get_attr(p, 'nom_du_produit', '') or
                      _get_attr(p, 'nom_produit', '')).lower()
            marque = str(_get_attr(p, 'marque', '')).lower()
            desc = str(_get_attr(p, 'description', '')).lower()
            code = str(_get_attr(p, 'code_produit', '')).lower()

            if (query_lower in nom or query_lower in marque or
                query_lower in desc or query_lower in code):
                results.append(_product_to_dict(p))

            if len(results) >= limit:
                break

        logger.info(f"🔍 Recherche '{query}' → {len(results)} résultats")
        return results

    except Exception as e:
        logger.error(f"❌ Erreur search_products: {e}", exc_info=True)
        return []


# ============================================================================
# ===== FILTRE PAR PRIX =====
# ============================================================================

# ----- TOOL LangChain -----
@tool
async def tool_filtrer_par_prix(
    prix_min: Optional[float] = None,
    prix_max: Optional[float] = None,
    categorie: Optional[str] = None,
    limit: int = 30,
) -> list:
    """Filtre les produits par gamme de prix en FCFA.

    Utilise ce tool quand l'utilisateur mentionne un budget :
    "moins de 300000 FCFA", "entre 100000 et 500000", "pas cher".

    Args:
        prix_min: Prix minimum en FCFA (inclus)
        prix_max: Prix maximum en FCFA (inclus)
        categorie: Filtre optionnel par catégorie
        limit: Nombre max de résultats (défaut 30)

    Retourne les produits triés par prix croissant.
    """
    return await filter_by_price(prix_min, prix_max, categorie, limit)


# ----- Fonction métier -----
async def filter_by_price(
    prix_min: Optional[float] = None,
    prix_max: Optional[float] = None,
    categorie: Optional[str] = None,
    limit: int = 50,
) -> List[Dict]:
    """Filtre les produits par gamme de prix (triés par prix croissant)."""
    try:
        products = await get_data()
        if not products:
            return []

        cat_filter = categorie.upper() if categorie else None
        results = []

        for p in products:
            if cat_filter:
                if str(_get_attr(p, 'categorie', '')).upper() != cat_filter:
                    continue

            try:
                prix = float(_get_attr(p, 'prix_de_vente', 0) or 0)
            except (ValueError, TypeError):
                continue

            if prix_min is not None and prix < prix_min:
                continue
            if prix_max is not None and prix > prix_max:
                continue

            results.append(_product_to_dict(p))

        results.sort(key=lambda x: x.get('prix_de_vente', 0) or 0)
        results = results[:limit]

        logger.info(
            f"💰 Filtre prix [{prix_min} - {prix_max}] cat={categorie} "
            f"→ {len(results)} résultats"
        )
        return results

    except Exception as e:
        logger.error(f"❌ Erreur filter_by_price: {e}", exc_info=True)
        return []


# ============================================================================
# ===== VÉRIFICATION STOCK =====
# ============================================================================

# ----- TOOL LangChain -----
@tool
async def tool_verifier_stock(code_produit: str) -> dict:
    """Vérifie la disponibilité et le niveau de stock d'un produit.

    Utilise ce tool quand l'utilisateur demande :
    "est-ce disponible ?", "il en reste combien ?", "en stock ?".

    Args:
        code_produit: Code unique du produit (ex: "SC0226F")

    Retourne un dict avec quantite, seuil, en_alerte, en_rupture, disponible.
    """
    result = await check_stock(code_produit)
    return result if result else {}


# ----- Fonction métier -----
async def check_stock(code_produit: str) -> Optional[Dict]:
    """Vérifie le stock d'un produit spécifique."""
    try:
        product = await get_product_details(code_produit)
        if not product:
            return None

        quantite = product.get('quantite', 0) or 0
        seuil = product.get('seuil', 5) or 5

        return {
            'code_produit': product.get('code_produit'),
            'nom_du_produit': product.get('nom_du_produit'),
            'quantite': quantite,
            'seuil': seuil,
            'en_alerte': quantite <= seuil,
            'en_rupture': quantite <= 0,
            'disponible': quantite > 0,
        }
    except Exception as e:
        logger.error(f"❌ Erreur check_stock: {e}", exc_info=True)
        return None


# ============================================================================
# ===== ALERTES STOCK =====
# ============================================================================

# ----- TOOL LangChain -----
@tool
async def tool_produits_en_alerte(limit: int = 20) -> list:
    """Liste les produits sous leur seuil d'alerte ou en rupture de stock.

    Utilise ce tool quand l'utilisateur demande :
    "qu'est-ce qu'il faut réapprovisionner ?", "produits en rupture ?",
    "alertes stock".

    Args:
        limit: Nombre max de produits à retourner (défaut 20)

    Retourne les produits triés par criticité (le plus bas en premier).
    """
    return await get_low_stock_products(limit=limit)


# ----- Fonction métier -----
async def get_low_stock_products(limit: int = 20) -> List[Dict]:
    """Retourne les produits sous leur seuil d'alerte."""
    try:
        products = await get_data()
        if not products:
            return []

        alerts = []
        for p in products:
            try:
                qte = int(_get_attr(p, 'quantite', 0) or 0)
                seuil = int(_get_attr(p, 'seuil', 5) or 5)
            except (ValueError, TypeError):
                continue

            if qte <= seuil:
                d = _product_to_dict(p)
                d['en_rupture'] = qte <= 0
                alerts.append(d)

        alerts.sort(key=lambda x: x.get('quantite', 0) or 0)
        alerts = alerts[:limit]

        logger.info(f"⚠️ {len(alerts)} produits en alerte stock")
        return alerts

    except Exception as e:
        logger.error(f"❌ Erreur get_low_stock_products: {e}", exc_info=True)
        return []


# ============================================================================
# ===== STATISTIQUES =====
# ============================================================================

# ----- TOOL LangChain -----
@tool
async def tool_statistiques() -> dict:
    """Retourne un résumé global du catalogue.

    Utilise ce tool quand l'utilisateur demande un état des lieux :
    "résume-moi le catalogue", "combien de produits ?",
    "quelle est la valeur du stock ?", "top marques".

    Retourne un dict avec :
    - total_produits, valeur_totale_stock
    - nombre_categories, nombre_marques
    - en_rupture, en_alerte
    - categories (répartition), top_marques
    """
    return await get_statistics()


# ----- Fonction métier -----
async def get_statistics() -> Dict:
    """Retourne des statistiques globales sur le catalogue."""
    try:
        products = await get_data()
        if not products:
            return {"total_produits": 0}

        total = len(products)
        valeur_totale = 0
        categories: Dict[str, int] = {}
        marques: Dict[str, int] = {}
        en_rupture = 0
        en_alerte = 0

        for p in products:
            try:
                prix = float(_get_attr(p, 'prix_de_vente', 0) or 0)
                qte = int(_get_attr(p, 'quantite', 0) or 0)
                seuil = int(_get_attr(p, 'seuil', 5) or 5)
            except (ValueError, TypeError):
                continue

            valeur_totale += prix * qte

            cat = str(_get_attr(p, 'categorie', 'INCONNU'))
            categories[cat] = categories.get(cat, 0) + 1

            mar = str(_get_attr(p, 'marque', 'INCONNU'))
            marques[mar] = marques.get(mar, 0) + 1

            if qte <= 0:
                en_rupture += 1
            elif qte <= seuil:
                en_alerte += 1

        return {
            'total_produits': total,
            'valeur_totale_stock': round(valeur_totale, 2),
            'nombre_categories': len(categories),
            'nombre_marques': len(marques),
            'en_rupture': en_rupture,
            'en_alerte': en_alerte,
            'categories': dict(sorted(
                categories.items(), key=lambda x: x[1], reverse=True
            )),
            'top_marques': dict(sorted(
                marques.items(), key=lambda x: x[1], reverse=True
            )[:10]),
        }

    except Exception as e:
        logger.error(f"❌ Erreur get_statistics: {e}", exc_info=True)
        return {}


# ============================================================================
# ===== PRODUITS SIMILAIRES =====
# ============================================================================

# ----- TOOL LangChain -----
@tool
async def tool_produits_similaires(code_produit: str, limit: int = 5) -> list:
    """Trouve des produits similaires (même catégorie, prix proche ±50%).

    Utilise ce tool quand l'utilisateur demande des alternatives :
    "autre option ?", "produit similaire", "équivalent moins cher".

    Args:
        code_produit: Code du produit de référence (ex: "SC0226F")
        limit: Nombre de suggestions (défaut 5)

    Retourne une liste triée par proximité de prix.
    """
    return await get_similar_products(code_produit, limit=limit)


# ----- Fonction métier -----
async def get_similar_products(
    code_produit: str, limit: int = 5
) -> List[Dict]:
    """Trouve des produits similaires (même catégorie, prix proche)."""
    try:
        ref = await get_product_details(code_produit)
        if not ref:
            return []

        ref_cat = ref.get('categorie')
        ref_prix = float(ref.get('prix_de_vente', 0) or 0)

        products = await get_data()
        similar = []

        for p in products:
            p_code = _get_attr(p, 'code_produit')
            if p_code == code_produit:
                continue

            if _get_attr(p, 'categorie') != ref_cat:
                continue

            try:
                p_prix = float(_get_attr(p, 'prix_de_vente', 0) or 0)
            except (ValueError, TypeError):
                continue

            if ref_prix > 0:
                ecart = abs(p_prix - ref_prix) / ref_prix
                if ecart > 0.5:
                    continue

            similar.append((abs(p_prix - ref_prix), _product_to_dict(p)))

        similar.sort(key=lambda x: x[0])
        results = [s[1] for s in similar[:limit]]

        logger.info(f"🎯 {len(results)} similaires à {code_produit}")
        return results

    except Exception as e:
        logger.error(f"❌ Erreur get_similar_products: {e}", exc_info=True)
        return []


# ============================================================================
# ===== PAGINATION =====
# ============================================================================

# ----- TOOL LangChain -----
@tool
async def tool_paginer_produits(
    page: int = 1,
    page_size: int = 20,
    categorie: Optional[str] = None,
    marque: Optional[str] = None,
) -> dict:
    """Retourne une page de produits (utile pour gros catalogues).

    Utilise ce tool quand l'utilisateur veut voir beaucoup de produits
    page par page, ou quand tu dois éviter de saturer le contexte.

    Args:
        page: Numéro de page (1-indexed)
        page_size: Taille de page (défaut 20, max 50)
        categorie: Filtre optionnel
        marque: Filtre optionnel

    Retourne : {page, page_size, total, total_pages, produits}
    """
    page_size = min(page_size, 50)
    return await get_products_paginated(page, page_size, categorie, marque)


# ----- Fonction métier -----
async def get_products_paginated(
    page: int = 1,
    page_size: int = 20,
    categorie: Optional[str] = None,
    marque: Optional[str] = None,
) -> Dict:
    """Retourne une page de produits."""
    try:
        products = await get_data()
        if not products:
            return {'page': page, 'page_size': page_size,
                    'total': 0, 'total_pages': 0, 'produits': []}

        cat_filter = categorie.upper() if categorie else None
        mar_filter = marque.upper() if marque else None

        filtered = []
        for p in products:
            if cat_filter and str(_get_attr(p, 'categorie', '')).upper() != cat_filter:
                continue
            if mar_filter and str(_get_attr(p, 'marque', '')).upper() != mar_filter:
                continue
            filtered.append(p)

        total = len(filtered)
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = max(1, min(page, total_pages))

        start = (page - 1) * page_size
        end = start + page_size

        return {
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': total_pages,
            'produits': [_product_to_dict(p) for p in filtered[start:end]],
        }

    except Exception as e:
        logger.error(f"❌ Erreur pagination: {e}", exc_info=True)
        return {'page': page, 'page_size': page_size,
                'total': 0, 'total_pages': 0, 'produits': []}


# ============================================================================
# ===== TRI =====
# ============================================================================

# ----- TOOL LangChain -----
@tool
async def tool_produits_tries(
    sort_by: str = "prix",
    order: str = "asc",
    categorie: Optional[str] = None,
    limit: int = 20,
) -> list:
    """Retourne les produits triés selon un critère.

    Utilise ce tool quand l'utilisateur veut :
    "le plus cher", "le moins cher", "top 10 prix", "triés par nom".

    Args:
        sort_by: 'prix' | 'nom' | 'quantite' | 'marque'
        order: 'asc' | 'desc'
        categorie: Filtre optionnel
        limit: Nombre max (défaut 20)
    """
    return await get_sorted_products(sort_by, order, categorie, limit)


# ----- Fonction métier -----
async def get_sorted_products(
    sort_by: str = 'prix',
    order: str = 'asc',
    categorie: Optional[str] = None,
    limit: int = 20,
) -> List[Dict]:
    """Retourne les produits triés."""
    try:
        products = await get_data()
        if not products:
            return []

        cat_filter = categorie.upper() if categorie else None

        key_map = {
            'prix': 'prix_de_vente',
            'nom': 'nom_du_produit',
            'quantite': 'quantite',
            'marque': 'marque',
        }
        sort_key = key_map.get(sort_by, 'prix_de_vente')

        filtered = []
        for p in products:
            if cat_filter and str(_get_attr(p, 'categorie', '')).upper() != cat_filter:
                continue
            filtered.append(_product_to_dict(p))

        reverse = (order.lower() == 'desc')

        try:
            filtered.sort(
                key=lambda x: (x.get(sort_key) if x.get(sort_key) is not None else 0),
                reverse=reverse
            )
        except TypeError:
            filtered.sort(key=lambda x: str(x.get(sort_key, '')), reverse=reverse)

        results = filtered[:limit]
        logger.info(f"🔄 Tri {sort_by} ({order}) → {len(results)} résultats")
        return results

    except Exception as e:
        logger.error(f"❌ Erreur get_sorted_products: {e}", exc_info=True)
        return []


# ============================================================================
# ===== HEALTH CHECK =====
# ============================================================================

# ----- TOOL LangChain -----
@tool
async def tool_health_check() -> dict:
    """Vérifie que l'API SmartCorp répond correctement.

    Utilise ce tool en cas de doute sur la disponibilité du service
    avant de lancer une action importante.

    Retourne : {status, produits_recus, temps_reponse_ms, cache_actif}
    """
    return await check_api_health()


# ----- Fonction métier -----
async def check_api_health() -> Dict:
    """Vérifie que l'API répond."""
    start = time.time()
    try:
        data = await get_products_from_api(retries=1, timeout=10)
        elapsed = round((time.time() - start) * 1000, 2)
        return {
            'status': 'ok' if data else 'empty',
            'produits_recus': len(data),
            'temps_reponse_ms': elapsed,
            'cache_actif': 'data' in cache,
        }
    except Exception as e:
        return {
            'status': 'error',
            'erreur': str(e),
            'temps_reponse_ms': round((time.time() - start) * 1000, 2),
        }


# ============================================================================
# ===== REGISTRE DES TOOLS LANGCHAIN =====
# ============================================================================

ALL_TOOLS = [
    tool_rechercher_produits,
    tool_filtrer_produits,
    tool_filtrer_par_prix,
    tool_verifier_stock,
    tool_produits_en_alerte,
    tool_statistiques,
    tool_produits_similaires,
    tool_liste_marques,
    tool_liste_categories,
    tool_details_produit,
    tool_paginer_produits,
    tool_produits_tries,
    tool_health_check,
]


