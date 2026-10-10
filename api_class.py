"""
api_class.py - Classes produits Smart Corporation
Chaque sous-classe parse les specs depuis le champ `description` de l'API.

Données réelles API utilisées pour implémenter chaque from_string() :
  - LAPTOPS          : Processeur, Fréquence base/turbo, OS, Écran, Mémoire, Disque, Carte graphique, Couleur
  - CLE USB          : Capacité, Interface, Couleur
  - CARTE MEMOIRES   : Memory Type, Vitesse lecture, Capacité, Couleur
  - CARTOUCHES       : Technologie impression, Nombre pages, Couleur
  - DISQUE DUR EXT.  : Type disque, Capacité (To), Interface USB, Couleur
  - DISQUE INTERNE   : Type disque, Capacité (Go/To), Interface SATA, Couleur
  - IMPRIMANTES      : Type média, Connectivité, Série, OS, Interface, Capacité papier, Couleur
  - CONSOLES         : GPU, ROM, RAM, CPU, Fréquence, Couleur
  - EQUIPEMENTS RES. : Vitesse, Normes IEEE, Fréquence, Ports, Couleur
  - CAMERA           : Objectif, Puissance, Compression audio/vidéo, Cadence, Poids, Couleur
  - FITNESS          : Type, Couleur (structure de base — pas encore de produits dans l'API)
"""

import re


# =============================================================================
# CLASSE DE BASE
# =============================================================================

class Article:
    """Classe de base pour tous les produits Smart Corporation."""

    def __init__(self, id, code_produit, nom_du_produit, marque, categorie,
                 quantite, description, prix_de_vente, photo, boutique, seuil):
        self.id = id
        self.code_produit = code_produit
        self.nom_produit = nom_du_produit
        self.marque = marque
        self.categorie = categorie
        self.quantite = int(quantite) if quantite is not None else 0
        self.description = description or ""
        self.prix_de_vente = float(prix_de_vente) if prix_de_vente is not None else 0.0
        self.photo = photo
        self.boutique = boutique
        self.seuil = int(seuil) if seuil is not None else 0

    # -------------------------------------------------------------------------
    # Méthodes métier
    # -------------------------------------------------------------------------

    def en_stock(self) -> bool:
        """True si le produit a un stock disponible."""
        return self.quantite > 0

    def sous_seuil(self) -> bool:
        """True si le stock est en dessous ou égal au seuil d'alerte."""
        return self.quantite <= self.seuil

    # -------------------------------------------------------------------------
    # Conversion dict ↔ objet
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Convertit l'article en dict — utile pour le cache et les réponses API."""
        return {
            'id': self.id,
            'code_produit': self.code_produit,
            'nom_du_produit': self.nom_produit,
            'marque': self.marque,
            'categorie': self.categorie,
            'quantite': self.quantite,
            'description': self.description,
            'prix_de_vente': self.prix_de_vente,
            'photo': self.photo,
            'boutique': self.boutique,
            'seuil': self.seuil
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Article':
        """Crée un Article depuis un dict API."""
        return cls(
            id=data.get('id'),
            code_produit=data.get('code_produit'),
            nom_du_produit=data.get('nom_du_produit'),
            marque=data.get('marque'),
            categorie=data.get('categorie'),
            quantite=data.get('quantite', 0),
            description=data.get('description', ''),
            prix_de_vente=data.get('prix_de_vente', 0),
            photo=data.get('photo'),
            boutique=data.get('boutique'),
            seuil=data.get('seuil', 0)
        )

    # -------------------------------------------------------------------------
    # Helper regex interne
    # -------------------------------------------------------------------------

    @staticmethod
    def _extract(pattern: str, text: str, cast=None):
        """
        Extrait une valeur depuis une description structurée via regex.
        cast : int | float | None — convertit la valeur extraite si fourni.
        """
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return None
        value = match.group(1).strip()
        if cast:
            try:
                return cast(value.replace(',', '.').replace('\xa0', '').replace(' ', ''))
            except (ValueError, TypeError):
                return None
        return value

    def __repr__(self):
        stock = f"{self.quantite} en stock" if self.en_stock() else "Rupture de stock"
        return f"{self.code_produit} | {self.nom_produit} | {self.prix_de_vente:,.0f} FCFA | {stock}"


# =============================================================================
# LAPTOPS
# =============================================================================
class Laptops(Article):
    def from_string(self) -> dict:
        d = self.description
        self.processeur        = self._extract(r'Processeur\s*:\s*(.+)', d)
        self.frequence_base    = self._extract(r'Fr[eé]quence de base\s*:\s*([\d.,]+)', d, float)
        self.frequence_turbo   = self._extract(r'Fr[eé]quence turbo\s*:\s*([\d.,]+)', d, float)
        self.systeme_exploit   = self._extract(r"Syst[eè]me d.exploitation\s*:\s*(.+)", d)
        self.ecran             = self._extract(r'[ÉE]cran\s*:\s*"?([\d.,]+)', d, float)
        self.memoire_go        = self._extract(r'M[eé]moire\s*:\s*(\d+)', d, int)
        self.disque_go         = self._extract(r'Disque dur\s*:\s*(\d+)', d, int)
        self.type_disque       = self._extract(r'Type de disque\s*:\s*(.+)', d)
        self.carte_graphique   = self._extract(r'Carte graphique\s*:\s*(.+)', d)
        self.couleur           = self._extract(r'Couleur\s*:\s*(.+)', d)
        return {
            'processeur'           : self.processeur,
            'frequence_base_ghz'   : self.frequence_base,
            'frequence_turbo_ghz'  : self.frequence_turbo,
            'systeme_exploitation' : self.systeme_exploit,
            'ecran_pouces'         : self.ecran,
            'memoire_go'           : self.memoire_go,
            'disque_go'            : self.disque_go,
            'type_disque'          : self.type_disque,
            'carte_graphique'      : self.carte_graphique,
            'couleur'              : self.couleur,
        }


# =============================================================================
# CLE USB
# =============================================================================
class CleUSB(Article):
    def from_string(self) -> dict:
        d = self.description
        self.capacite_go = self._extract(r'Capacit[eé]\s*:\s*(\d+)\s*Go', d, int)
        self.interface   = self._extract(r'Interface\s*:\s*(.+)', d)
        self.couleur     = self._extract(r'Couleur\s*:\s*(.+)', d)
        return {
            'capacite_go' : self.capacite_go,
            'interface'   : self.interface,
            'couleur'     : self.couleur,
        }


# =============================================================================
# CARTE MEMOIRE
# =============================================================================
class CarteMemoire(Article):
    def from_string(self) -> dict:
        d = self.description
        self.memory_type     = self._extract(r'Memory Type\s*:\s*(.+)', d)
        self.vitesse_lecture = self._extract(r'Vitesse de lecture\s*:\s*([\d.,]+)', d, float)
        self.capacite_gb     = self._extract(r'Capacit[eé]\s*[:\s]+([\d]+)\s*G[Bo]', d, int)
        self.couleur         = self._extract(r'Couleur\s*:\s*(.+)', d)
        return {
            'memory_type'         : self.memory_type,
            'vitesse_lecture_mo_s': self.vitesse_lecture,
            'capacite_gb'         : self.capacite_gb,
            'couleur'             : self.couleur,
        }


# =============================================================================
# CARTOUCHE
# =============================================================================
class Cartouche(Article):
    def from_string(self) -> dict:
        d = self.description
        self.technologie   = self._extract(r"Technologie d.impression\s*:\s*(.+)", d)
        self.nombre_pages  = self._extract(r'Nombre de pages\s*:\s*(?:Environ\s*)?(\d[\d\s]*)', d, int)
        self.couleur       = self._extract(r'Couleur(?:s)?\s*:\s*(.+)', d)
        return {
            'technologie_impression' : self.technologie,
            'nombre_pages'           : self.nombre_pages,
            'couleur'                : self.couleur,
        }


# =============================================================================
# DISQUE DUR EXTERNE
# =============================================================================
class DisqueDurExterne(Article):
    def from_string(self) -> dict:
        d = self.description
        self.type_disque  = self._extract(r'Type de Disque\s*:\s*(.+)', d)
        self.capacite_to  = self._extract(r'Capacit[eé]\s*:\s*([\d.,]+)\s*To', d, float)
        self.interface    = self._extract(r'Interface\s*[\u200e:\s]+(.+)', d)
        self.couleur      = self._extract(r'Couleur\s*:\s*(.+)', d)
        return {
            'type_disque'  : self.type_disque,
            'capacite_to'  : self.capacite_to,
            'interface'    : self.interface,
            'couleur'      : self.couleur,
        }


# =============================================================================
# DISQUE DUR INTERNE
# =============================================================================
class DisqueDurInterne(Article):
    def from_string(self) -> dict:
        d = self.description
        self.type_disque = self._extract(r'Type de Disque\s*:\s*(.+)', d)
        # Capacité peut être en To ou Go selon le produit
        capacite_to = self._extract(r'Capacit[eé]\s*:\s*([\d.,]+)\s*To', d, float)
        capacite_go = self._extract(r'Capacit[eé]\s*:\s*(\d+)\s*Go', d, int)
        self.capacite_go = int(capacite_to * 1000) if capacite_to else capacite_go
        self.interface   = self._extract(r'Interface\s*[\u200e:\s]+(.+)', d)
        self.couleur     = self._extract(r'Couleur\s*:\s*(.+)', d)
        return {
            'type_disque'  : self.type_disque,
            'capacite_go'  : self.capacite_go,
            'interface'    : self.interface,
            'couleur'      : self.couleur,
        }


# =============================================================================
# IMPRIMANTES
# =============================================================================
class Imprimantes(Article):
    def from_string(self) -> dict:
        d = self.description
        self.type_media        = self._extract(r"Type de m[eé]dia d.impression\s*:\s*(.+)", d)
        self.connectivite      = self._extract(r'Type de connecteur\s*:\s*(.+)', d)
        self.serie             = self._extract(r'S[eé]ries\s*:\s*(.+)', d)
        self.systeme_exploit   = self._extract(r"Syst[eè]me d.exploitation\s*:\s*(.+)", d)
        self.interface         = self._extract(r'Interface du mat[eé]riel\s*:\s*(.+)', d)
        self.capacite_stockage = self._extract(r'Capacit[eé] de stockage\s*:\s*(.+)', d)
        self.capacite_papier   = self._extract(r'Capacit[eé] maximale en papier[^:]*:\s*(\d+)', d, int)
        self.couleur           = self._extract(r'Couleur\s*:\s*(.+)', d)
        return {
            'type_media'           : self.type_media,
            'connectivite'         : self.connectivite,
            'serie'                : self.serie,
            'systeme_exploitation' : self.systeme_exploit,
            'interface'            : self.interface,
            'capacite_stockage'    : self.capacite_stockage,
            'capacite_papier'      : self.capacite_papier,
            'couleur'              : self.couleur,
        }


# =============================================================================
# CONSOLE
# =============================================================================
class Console(Article):
    def from_string(self) -> dict:
        d = self.description
        self.processeur_graphique = self._extract(r'Processeur graphique\s*:\s*(.+)', d)
        self.stockage             = self._extract(r'M[eé]moire ROM\s*:\s*(.+)', d)
        self.ram                  = self._extract(r'RAM\s*:\s*(.+)', d)
        self.cpu                  = self._extract(r'CPU\s*:\s*(.+)', d)
        self.frequence            = self._extract(r'Fr[eé]quence\s*:\s*(.+)', d)
        self.couleur              = self._extract(r'Couleur\s*:\s*(.+)', d)
        return {
            'processeur_graphique' : self.processeur_graphique,
            'stockage'             : self.stockage,
            'ram'                  : self.ram,
            'cpu'                  : self.cpu,
            'frequence'            : self.frequence,
            'couleur'              : self.couleur,
        }


# =============================================================================
# EQUIPEMENTS RESEAUX
# =============================================================================
class EquipementsReseaux(Article):
    def from_string(self) -> dict:
        d = self.description
        # Vitesse max (Mbps ou Mbit/s selon le produit)
        self.vitesse_max  = self._extract(r'(?:jusqu)[^\d]*([\d.,]+)\s*M(?:bit|bps)', d)
        # Normes IEEE (liste)
        normes = re.findall(r'(IEEE\s*[\d.]+[a-z]?)', d, re.IGNORECASE)
        self.normes_reseau = normes if normes else None
        # Fréquence radio
        self.frequence    = self._extract(r'([\d.,]+\s*GHz)', d)
        # Ports
        self.ports        = self._extract(r'Ports?\s*:\s*(.+)', d)
        # Sécurité
        self.securite     = self._extract(r'(?:Chiffrement|S[eé]curit[eé])[^\n:]*:\s*(.+)', d)
        self.couleur      = self._extract(r'Couleur\s*:\s*(.+)', d)
        return {
            'vitesse_max_mbps' : self.vitesse_max,
            'normes_reseau'    : self.normes_reseau,
            'frequence'        : self.frequence,
            'ports'            : self.ports,
            'securite'         : self.securite,
            'couleur'          : self.couleur,
        }


# =============================================================================
# CAMERA
# =============================================================================
class Camera(Article):
    def from_string(self) -> dict:
        d = self.description
        self.objectif_mm        = self._extract(r'Objectif f\s*:\s*([\d.,]+)', d, float)
        self.puissance          = self._extract(r'Puissance\s*:\s*(.+)', d)
        self.audio              = self._extract(r'Audio\s*:\s*(.+)', d)
        self.compression_audio  = self._extract(r'Compression audio\s*:\s*(.+)', d)
        self.compression_video  = self._extract(r'Compression vid[eé]o\s*:\s*(.+)', d)
        self.frequence_eclairage= self._extract(r"Fr[eé]quence d.[eé]clairage\s*:\s*(.+)", d)
        self.cadence_ips        = self._extract(r'Cadence d.image\s*:\s*(\d+)', d, int)
        self.poids_kg           = self._extract(r'Poids[^:]*:\s*([\d.,]+)', d, float)
        self.couleur            = self._extract(r'Couleur\s*:\s*(.+)', d)
        return {
            'objectif_mm'           : self.objectif_mm,
            'puissance'             : self.puissance,
            'audio'                 : self.audio,
            'compression_audio'     : self.compression_audio,
            'compression_video'     : self.compression_video,
            'frequence_eclairage'   : self.frequence_eclairage,
            'cadence_ips'           : self.cadence_ips,
            'poids_kg'              : self.poids_kg,
            'couleur'               : self.couleur,
        }


# =============================================================================
# FITNESS — pas encore de produits dans l'API, structure minimale prête
# =============================================================================
class Fitness(Article):
    def from_string(self) -> dict:
        d = self.description
        self.type_produit = self._extract(r'Type\s*:\s*(.+)', d)
        self.couleur      = self._extract(r'Couleur\s*:\s*(.+)', d)
        return {
            'type_produit' : self.type_produit,
            'couleur'      : self.couleur,
        }


# =============================================================================
# FACTORY — crée la bonne sous-classe selon la catégorie API
# =============================================================================

CATEGORIE_MAP = {
    'LAPTOPS'             : Laptops,
    'CLE USB'             : CleUSB,
    'CARTE MEMOIRES'      : CarteMemoire,
    'CARTOUCHES'          : Cartouche,
    'DISQUE DUR EXTERNE'  : DisqueDurExterne,
    'DISQUE INTERNE'      : DisqueDurInterne,
    'IMPRIMANTES'         : Imprimantes,
    'CONSOLES'            : Console,
    'EQUIPEMENTS RESEAUX' : EquipementsReseaux,
    'CAMERA'              : Camera,
    'FITNESS'             : Fitness,
}


def create_article(data: dict) -> Article:
    """
    Factory : crée automatiquement la bonne sous-classe selon la catégorie.

    """
    categorie = (data.get('categorie') or '').upper().strip()
    cls = CATEGORIE_MAP.get(categorie, Article)
    return cls(
        id            = data.get('id'),
        code_produit  = data.get('code_produit'),
        nom_du_produit= data.get('nom_du_produit'),
        marque        = data.get('marque'),
        categorie     = data.get('categorie'),
        quantite      = data.get('quantite', 0),
        description   = data.get('description', ''),
        prix_de_vente = data.get('prix_de_vente', 0),
        photo         = data.get('photo'),
        boutique      = data.get('boutique'),
        seuil         = data.get('seuil', 0)
    )