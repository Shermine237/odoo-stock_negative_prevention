from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _process_order(self, order, draft, existing_order):
        """Override pour vérifier le stock avant traitement de la commande POS"""
        # Vérifier si la prévention est activée
        prevent_negative = self.env['ir.config_parameter'].sudo().get_param(
            'stock_negative_prevention.prevent_pos', False
        )
        
        if prevent_negative and not draft:
            self._check_pos_stock_availability(order)
        
        return super()._process_order(order, draft, existing_order)

    def _check_pos_stock_availability(self, order):
        """Vérifie la disponibilité du stock pour toutes les lignes de commande POS"""
        stock_location_param = self.env['ir.config_parameter'].sudo().get_param(
            'stock_negative_prevention.stock_location_id', False
        )
        
        insufficient_products = []
        
        for line in order.get('lines', []):
            product_id = line[2].get('product_id')
            qty = line[2].get('qty', 0)
            
            if product_id and qty > 0:
                product = self.env['product.product'].browse(product_id)
                
                if product.type == 'product':  # Seulement pour les produits stockables
                    # Déterminer l'emplacement de stock à vérifier
                    if stock_location_param:
                        location = self.env['stock.location'].browse(int(stock_location_param))
                    else:
                        # Utiliser l'emplacement de stock du point de vente ou de l'entrepôt
                        session = self.env['pos.session'].browse(order.get('pos_session_id'))
                        if session and session.config_id.picking_type_id:
                            location = session.config_id.picking_type_id.default_location_src_id
                        else:
                            # Fallback sur l'emplacement par défaut de l'entrepôt
                            warehouse = self.env['stock.warehouse'].search([
                                ('company_id', '=', self.env.company.id)
                            ], limit=1)
                            location = warehouse.lot_stock_id if warehouse else None
                    
                    if location:
                        # Calculer la quantité disponible
                        available_qty = product.with_context(
                            location=location.id
                        ).qty_available
                        
                        # Vérifier si la quantité demandée est disponible
                        if qty > available_qty:
                            insufficient_products.append({
                                'product': product.display_name,
                                'requested': qty,
                                'available': available_qty,
                                'uom': product.uom_id.name
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


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    @api.model_create_multi
    def create(self, vals_list):
        """Override pour vérifier le stock lors de la création de ligne POS"""
        # Vérifier si la prévention est activée
        prevent_negative = self.env['ir.config_parameter'].sudo().get_param(
            'stock_negative_prevention.prevent_pos', False
        )
        
        if prevent_negative:
            for vals in vals_list:
                if vals.get('product_id') and vals.get('qty', 0) > 0:
                    product = self.env['product.product'].browse(vals['product_id'])
                    
                    if product.type == 'product':  # Seulement pour les produits stockables
                        self._validate_pos_line_stock(product, vals.get('qty', 0))
        
        return super().create(vals_list)

    def write(self, vals):
        """Override pour vérifier le stock lors de la modification de ligne POS"""
        # Vérifier si la prévention est activée
        prevent_negative = self.env['ir.config_parameter'].sudo().get_param(
            'stock_negative_prevention.prevent_pos', False
        )
        
        if prevent_negative and 'qty' in vals:
            for line in self:
                if line.product_id.type == 'product' and vals.get('qty', 0) > 0:
                    self._validate_pos_line_stock(line.product_id, vals['qty'])
        
        return super().write(vals)

    def _validate_pos_line_stock(self, product, qty):
        """Valide le stock pour une ligne POS spécifique"""
        stock_location_param = self.env['ir.config_parameter'].sudo().get_param(
            'stock_negative_prevention.stock_location_id', False
        )
        
        # Déterminer l'emplacement de stock
        if stock_location_param:
            location = self.env['stock.location'].browse(int(stock_location_param))
        else:
            # Utiliser l'emplacement de stock du point de vente
            if hasattr(self, 'order_id') and self.order_id.session_id:
                session = self.order_id.session_id
                if session.config_id.picking_type_id:
                    location = session.config_id.picking_type_id.default_location_src_id
                else:
                    location = None
            else:
                # Fallback sur l'emplacement par défaut de l'entrepôt
                warehouse = self.env['stock.warehouse'].search([
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                location = warehouse.lot_stock_id if warehouse else None
        
        if location:
            # Calculer la quantité disponible
            available_qty = product.with_context(
                location=location.id
            ).qty_available
            
            # Vérifier si la quantité demandée est disponible
            if qty > available_qty:
                raise UserError(_(
                    "Stock insuffisant pour %s.\n"
                    "Quantité demandée : %.2f %s\n"
                    "Quantité disponible : %.2f %s\n\n"
                    "Veuillez ajuster la quantité ou réapprovisionner le stock."
                ) % (
                    product.display_name,
                    qty,
                    product.uom_id.name,
                    available_qty,
                    product.uom_id.name
                ))
