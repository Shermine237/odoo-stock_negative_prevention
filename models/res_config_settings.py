from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


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
        help="Empêche la validation des commandes point de vente si le stock est insuffisant. "
             "Utilise l'entrepôt défini dans la configuration du Point de Vente."
    )

    def set_values(self):
        """Override pour logger les valeurs sauvegardées"""
        super().set_values()
        _logger.info(f"STOCK PREVENTION CONFIG: prevent_sales={self.prevent_negative_stock_sales}")
        _logger.info(f"STOCK PREVENTION CONFIG: prevent_pos={self.prevent_negative_stock_pos}")

    @api.model
    def get_values(self):
        """Override pour logger les valeurs récupérées"""
        res = super().get_values()
        _logger.info(f"STOCK PREVENTION CONFIG GET: {res}")
        return res
