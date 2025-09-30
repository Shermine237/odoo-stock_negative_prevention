from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    prevent_negative_stock_sales = fields.Boolean(
        string="Prévention Stock Négatif - Ventes",
        config_parameter='stock_negative_prevention.prevent_sales',
        help="Empêche la confirmation des commandes de vente si le stock est insuffisant"
    )
    
    prevent_negative_stock_pos = fields.Boolean(
        string="Prévention Stock Négatif - Point de Vente",
        config_parameter='stock_negative_prevention.prevent_pos',
        help="Empêche la validation des commandes point de vente si le stock est insuffisant"
    )
    
    stock_location_id = fields.Many2one(
        'stock.location',
        string="Emplacement de Stock à Vérifier",
        config_parameter='stock_negative_prevention.stock_location_id',
        domain=[('usage', '=', 'internal')],
        help="Emplacement de stock à vérifier. Si vide, utilise l'emplacement par défaut de l'entrepôt"
    )
