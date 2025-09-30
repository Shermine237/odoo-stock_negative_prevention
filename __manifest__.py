{
    'name': 'Stock Negative Prevention',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Empêche les ventes avec stock négatif pour les modules Vente et Point de Vente',
    'description': """
Stock Negative Prevention
=========================

Ce module empêche la validation des commandes de vente et des commandes point de vente
lorsque les produits n'ont pas suffisamment de stock disponible.

Fonctionnalités:
- Validation du stock avant confirmation des commandes de vente
- Validation du stock avant validation des commandes point de vente
- Configuration par entreprise pour activer/désactiver la validation
- Messages d'erreur détaillés avec quantités disponibles
- Support des variantes de produits
- Gestion des emplacements de stock spécifiques

Installation:
1. Installer le module
2. Aller dans Inventaire > Configuration > Paramètres
3. Activer "Prévention Stock Négatif" selon vos besoins
    """,
    'author': 'Votre Entreprise',
    'website': 'https://www.votreentreprise.com',
    'depends': [
        'base',
        'stock',
        'sale',
        'point_of_sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/sale_order_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'odoo-stock_negative_prevention/static/src/js/pos_stock_validation.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
