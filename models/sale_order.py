from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        """Override pour vérifier le stock avant confirmation"""
        # Vérifier si la prévention est activée (get_param retourne une string, pas un boolean)
        prevent_negative_param = self.env['ir.config_parameter'].sudo().get_param(
            'stock_negative_prevention.prevent_sales', 'False'
        )
        prevent_negative = prevent_negative_param in ('True', 'true', '1', 'yes')
        
        _logger.info(f"STOCK PREVENTION: prevent_negative_param={prevent_negative_param}, prevent_negative={prevent_negative}")
        
        if prevent_negative:
            _logger.info("STOCK PREVENTION: Vérification du stock activée")
            self._check_stock_availability()
        else:
            _logger.info("STOCK PREVENTION: Vérification du stock désactivée")
        
        return super().action_confirm()

    def _get_available_quantity(self, product, location):
        """Récupère la quantité disponible d'un produit dans un emplacement
        Méthode inspirée du module mrp_stock_validation pour un calcul correct"""
        quants = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id', 'child_of', location.id),
        ])
        available_qty = sum(quants.mapped('available_quantity'))
        _logger.info(f"STOCK PREVENTION: Calcul stock pour {product.display_name} dans {location.name}: {available_qty}")
        return available_qty

    def _get_stock_check_warehouse_location(self):
        warehouse = self.warehouse_id
        if not warehouse:
            warehouse = self.env['stock.warehouse'].search([
                ('company_id', '=', self.company_id.id)
            ], limit=1)
        location = warehouse.lot_stock_id if warehouse else None
        return warehouse, location

    def _check_stock_availability(self):
        """Vérifie la disponibilité du stock pour toutes les lignes de commande"""
        insufficient_products = []
        warehouse, location = self._get_stock_check_warehouse_location()
        warehouse_name = warehouse.display_name if warehouse else None
        
        for line in self.order_line:
            _logger.info(f"STOCK PREVENTION: Vérification ligne - Produit: {line.product_id.display_name}, Type: {line.product_id.type}, Qty: {line.product_uom_qty}")
            
            # Vérifier les produits stockables ET consommables (qui peuvent avoir du stock)
            if line.product_id.type in ('product', 'consu'):
                # Utiliser l'emplacement par défaut de l'entrepôt de l'entreprise
                _logger.info(f"STOCK PREVENTION: Utilisation entrepôt: {warehouse.name if warehouse else 'Aucun'}")
                
                if location:
                    # Calculer la quantité disponible avec la méthode corrigée
                    available_qty = self._get_available_quantity(line.product_id, location)
                    requested_qty = line.product_uom._compute_quantity(
                        line.product_uom_qty,
                        line.product_id.uom_id,
                    )
                    
                    _logger.info(
                        f"STOCK PREVENTION: Produit {line.product_id.display_name} - Demandé: {requested_qty} ({line.product_id.uom_id.name}), Disponible: {available_qty} ({line.product_id.uom_id.name})"
                    )
                    
                    # Vérifier si la quantité demandée est disponible
                    if requested_qty > available_qty:
                        insufficient_products.append({
                            'product': line.product_id.display_name,
                            'requested': requested_qty,
                            'available': available_qty,
                            'uom': line.product_id.uom_id.name,
                            'warehouse': warehouse_name,
                        })
                        _logger.warning(f"STOCK PREVENTION: Stock insuffisant pour {line.product_id.display_name}")
                else:
                    _logger.warning(f"STOCK PREVENTION: Aucun emplacement trouvé pour vérifier le stock")
        
        # Lever une erreur si des produits n'ont pas suffisamment de stock
        if insufficient_products:
            error_msg = _("Stock insuffisant pour les produits suivants :\n\n")
            for product_info in insufficient_products:
                error_msg += _("• %s : Demandé %.2f %s, Disponible %.2f %s dans l'entrepôt %s\n") % (
                    product_info['product'],
                    product_info['requested'],
                    product_info['uom'],
                    product_info['available'],
                    product_info['uom'],
                    product_info['warehouse'] or _('Inconnu'),
                )
            error_msg += _("\nVeuillez ajuster les quantités ou réapprovisionner le stock.")
            
            raise UserError(error_msg)

    def action_check_stock_availability(self):
        """Action pour vérifier manuellement la disponibilité du stock"""
        try:
            self._check_stock_availability()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Vérification Stock'),
                    'message': _('Stock suffisant pour tous les produits de cette commande.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except UserError as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Stock Insuffisant'),
                    'message': str(e),
                    'type': 'warning',
                    'sticky': True,
                }
            }


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.onchange('product_uom_qty')
    def _onchange_product_uom_qty_stock_check(self):
        """Vérification en temps réel lors de la modification de la quantité"""
        if self.product_id and self.product_id.type in ('product', 'consu'):
            prevent_negative_param = self.env['ir.config_parameter'].sudo().get_param(
                'stock_negative_prevention.prevent_sales', 'False'
            )
            prevent_negative = prevent_negative_param in ('True', 'true', '1', 'yes')
            
            if prevent_negative and self.product_uom_qty > 0:
                # Utiliser l'entrepôt par défaut de l'entreprise
                warehouse, location = self.order_id._get_stock_check_warehouse_location()
                warehouse_name = warehouse.display_name if warehouse else None
                
                if location:
                    # Utiliser la méthode corrigée pour calculer le stock disponible
                    available_qty = self.order_id._get_available_quantity(self.product_id, location)
                    requested_qty = self.product_uom._compute_quantity(
                        self.product_uom_qty,
                        self.product_id.uom_id,
                    )
                    
                    if requested_qty > available_qty:
                        return {
                            'warning': {
                                'title': _('Stock insuffisant'),
                                'message': _(
                                    'Attention : Stock insuffisant pour %s.\n'
                                    'Quantité demandée : %.2f %s\n'
                                    'Quantité disponible : %.2f %s\n\n'
                                    'Entrepôt : %s\n\n'
                                    'La commande ne pourra pas être confirmée en l\'état.'
                                ) % (
                                    self.product_id.display_name,
                                    requested_qty,
                                    self.product_id.uom_id.name,
                                    available_qty,
                                    self.product_id.uom_id.name,
                                    warehouse_name or _('Inconnu'),
                                )
                            }
                        }
