# Stock Negative Prevention

## Description

Ce module Odoo 18 empêche la validation des commandes de vente et des commandes point de vente lorsque les produits n'ont pas suffisamment de stock disponible.

## Fonctionnalités

### 🛒 **Module Vente**
- **Validation automatique** : Empêche la confirmation des commandes si le stock est insuffisant
- **Vérification en temps réel** : Avertissements lors de la saisie des quantités
- **Bouton de vérification manuelle** : Permet de vérifier le stock avant confirmation
- **Messages détaillés** : Affiche les quantités demandées vs disponibles

### 🏪 **Point de Vente**
- **Validation côté serveur** : Empêche la validation des commandes POS avec stock insuffisant
- **Validation côté client** : Vérification en temps réel dans l'interface POS
- **Messages d'erreur clairs** : Notifications détaillées des problèmes de stock

### ⚙️ **Configuration**
- **Activation par module** : Activation séparée pour Vente et Point de Vente
- **Emplacement personnalisé** : Choix de l'emplacement de stock à vérifier
- **Configuration par entreprise** : Paramètres spécifiques à chaque entreprise

## Installation

1. **Copier le module** dans le répertoire addons d'Odoo
2. **Redémarrer Odoo** avec `--update=all` ou mettre à jour la liste des modules
3. **Installer le module** depuis Apps > Stock Negative Prevention
4. **Configurer** dans Inventaire > Configuration > Paramètres

## Configuration

### Étapes de Configuration

1. **Aller dans Inventaire > Configuration > Paramètres**
2. **Activer les options souhaitées** :
   - ✅ **Prévention Stock Négatif - Ventes** : Pour les commandes de vente
   - ✅ **Prévention Stock Négatif - Point de Vente** : Pour le POS
3. **Choisir l'emplacement de stock** (optionnel) :
   - Si vide, utilise l'emplacement par défaut de l'entrepôt
   - Sinon, utilise l'emplacement spécifié

### Paramètres Techniques

Les paramètres sont stockés dans `ir.config_parameter` :
- `stock_negative_prevention.prevent_sales` : Boolean pour les ventes
- `stock_negative_prevention.prevent_pos` : Boolean pour le POS
- `stock_negative_prevention.stock_location_id` : ID de l'emplacement de stock

## Utilisation

### Module Vente

#### Validation Automatique
- Lors de la **confirmation d'une commande**, le système vérifie automatiquement le stock
- Si insuffisant, une **erreur détaillée** s'affiche avec les quantités manquantes

#### Vérification Manuelle
- **Bouton "Vérifier Stock"** disponible sur les commandes en brouillon
- Affiche une **notification de succès** ou d'**avertissement**

#### Avertissements Temps Réel
- Lors de la **modification des quantités**, avertissements automatiques
- **Messages informatifs** sans bloquer la saisie

### Point de Vente

#### Validation Serveur
- **Vérification automatique** lors de la validation de la commande
- **Erreur bloquante** si stock insuffisant

#### Validation Client
- **Vérification en temps réel** lors de l'ajout/modification de produits
- **Popups d'erreur** avec détails des quantités

## Structure du Module

```
stock_negative_prevention/
├── __init__.py
├── __manifest__.py
├── README.md
├── models/
│   ├── __init__.py
│   ├── res_config_settings.py    # Configuration
│   ├── sale_order.py             # Extension ventes
│   └── pos_order.py              # Extension POS
├── views/
│   ├── res_config_settings_views.xml  # Vues configuration
│   └── sale_order_views.xml           # Vues ventes
├── static/src/js/
│   └── pos_stock_validation.js    # JavaScript POS
└── security/
    └── ir.model.access.csv        # Droits d'accès
```

## Fonctionnement Technique

### Logique de Vérification

1. **Vérification activation** : Contrôle des paramètres de configuration
2. **Détermination emplacement** : Emplacement configuré ou par défaut
3. **Calcul stock disponible** : `product.qty_available` avec contexte location
4. **Comparaison quantités** : Demandée vs disponible
5. **Gestion erreurs** : Messages détaillés ou continuation

### Emplacements de Stock

- **Emplacement configuré** : Utilise `stock_location_id` des paramètres
- **Emplacement par défaut Vente** : `warehouse.lot_stock_id`
- **Emplacement par défaut POS** : `picking_type.default_location_src_id`

### Types de Produits

- **Produits stockables** (`type='product'`) : Vérification activée
- **Services/Consommables** : Pas de vérification (stock non applicable)

## Personnalisation

### Extension du Module

Le module peut être étendu pour :
- **Autres modules** : Achat, Fabrication, etc.
- **Logiques spécifiques** : Réservations, stock futur, etc.
- **Notifications** : Email, SMS, etc.

### Hooks Disponibles

- `_check_stock_availability()` : Logique de vérification personnalisable
- `_validate_pos_line_stock()` : Validation POS personnalisable
- Configuration par `ir.config_parameter` : Paramètres additionnels

## Dépendances

- **base** : Fonctionnalités de base Odoo
- **stock** : Gestion des stocks
- **sale** : Module de vente
- **point_of_sale** : Point de vente

## Compatibilité

- **Odoo 18.0** : Version supportée
- **Multi-entreprise** : Compatible
- **Multi-devises** : Compatible
- **Multi-entrepôts** : Compatible

## Support

Pour toute question ou problème :
1. **Vérifier la configuration** dans Inventaire > Paramètres
2. **Consulter les logs** Odoo pour les erreurs détaillées
3. **Tester** avec des produits stockables ayant du stock

## Licence

LGPL-3 - Voir le fichier `__manifest__.py` pour plus de détails.
