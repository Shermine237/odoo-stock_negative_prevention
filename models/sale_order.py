from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        """Override pour vérifier le stock avant confirmation"""
        # Vérifier si la prévention est activée
        prevent_negative = self.env['ir.config_parameter'].sudo().get_param(
            'stock_negative_prevention.prevent_sales', False
        )
        
        if prevent_negative:
            self._check_stock_availability()
        
        return super().action_confirm()

    def _check_stock_availability(self):
        """Vérifie la disponibilité du stock pour toutes les lignes de commande"""
        stock_location_param = self.env['ir.config_parameter'].sudo().get_param(
            'stock_negative_prevention.stock_location_id', False
        )
        
        insufficient_products = []
        
        for line in self.order_line:
            if line.product_id.type == 'product':  # Seulement pour les produits stockables
                # Déterminer l'emplacement de stock à vérifier
                if stock_location_param:
                    location = self.env['stock.location'].browse(int(stock_location_param))
                else:
                    # Utiliser l'emplacement par défaut de l'entrepôt de l'entreprise
                    warehouse = self.env['stock.warehouse'].search([
                        ('company_id', '=', self.company_id.id)
                    ], limit=1)
                    location = warehouse.lot_stock_id if warehouse else None
                
                if location:
                    # Calculer la quantité disponible
                    available_qty = line.product_id.with_context(
                        location=location.id
                    ).qty_available
                    
                    # Vérifier si la quantité demandée est disponible
                    if line.product_uom_qty > available_qty:
                        insufficient_products.append({
                            'product': line.product_id.display_name,
                            'requested': line.product_uom_qty,
                            'available': available_qty,
                            'uom': line.product_uom.name
                        })
        
        # Lever une erreur si des produits n'ont pas suffisamment de stock
        if insufficient_products:
            error_msg = _("Stock insuffisant pour les produits suivants :\n\n")
            for product_info in insufficient_products:
                error_msg += _("• %s : Demandé %.2f %s, Disponible %.2f %s\n") % (
                    product_info['product'],
                    product_info['requested'],
                    product_info['uom'],
                    product_info['available'],
                    product_info['uom']
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
        if self.product_id and self.product_id.type == 'product':
            prevent_negative = self.env['ir.config_parameter'].sudo().get_param(
                'stock_negative_prevention.prevent_sales', False
            )
            
            if prevent_negative and self.product_uom_qty > 0:
                stock_location_param = self.env['ir.config_parameter'].sudo().get_param(
                    'stock_negative_prevention.stock_location_id', False
                )
                
                # Déterminer l'emplacement de stock
                if stock_location_param:
                    location = self.env['stock.location'].browse(int(stock_location_param))
                else:
                    warehouse = self.env['stock.warehouse'].search([
                        ('company_id', '=', self.order_id.company_id.id)
                    ], limit=1)
                    location = warehouse.lot_stock_id if warehouse else None
                
                if location:
                    available_qty = self.product_id.with_context(
                        location=location.id
                    ).qty_available
                    
                    if self.product_uom_qty > available_qty:
                        return {
                            'warning': {
                                'title': _('Stock insuffisant'),
                                'message': _(
                                    'Attention : Stock insuffisant pour %s.\n'
                                    'Quantité demandée : %.2f %s\n'
                                    'Quantité disponible : %.2f %s\n\n'
                                    'La commande ne pourra pas être confirmée en l\'état.'
                                ) % (
                                    self.product_id.display_name,
                                    self.product_uom_qty,
                                    self.product_uom.name,
                                    available_qty,
                                    self.product_uom.name
                                )
                            }
                        }
