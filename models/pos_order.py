from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _get_available_quantity(self, product, location):
        """Récupère la quantité disponible d'un produit dans un emplacement
        Méthode inspirée du module mrp_stock_validation pour un calcul correct"""
        quants = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id', '=', location.id),
        ])
        available_qty = sum(quants.mapped('available_quantity'))
        _logger.info(f"POS STOCK PREVENTION: Calcul stock pour {product.display_name} dans {location.name}: {available_qty}")
        return available_qty

    def _process_order(self, order, draft, existing_order=None):
        """Override pour vérifier le stock avant traitement de la commande POS"""
        # Vérifier si la prévention est activée (get_param retourne une string)
        prevent_negative_param = self.env['ir.config_parameter'].sudo().get_param(
            'stock_negative_prevention.prevent_pos', 'False'
        )
        prevent_negative = prevent_negative_param in ('True', 'true', '1', 'yes')
        
        _logger.info(f"POS STOCK PREVENTION: prevent_negative_param={prevent_negative_param}, prevent_negative={prevent_negative}")
        
        if prevent_negative and not draft:
            self._check_pos_stock_availability(order)
        
        # Appeler la méthode parent avec les bons arguments selon la version d'Odoo
        if existing_order is not None:
            return super()._process_order(order, draft, existing_order)
        else:
            return super()._process_order(order, draft)

    def _check_pos_stock_availability(self, order):
        """Vérifie la disponibilité du stock pour toutes les lignes de commande POS"""
        insufficient_products = []
        
        for line in order.get('lines', []):
            product_id = line[2].get('product_id')
            qty = line[2].get('qty', 0)
            
            if product_id and qty > 0:
                product = self.env['product.product'].browse(product_id)
                
                # Vérifier les produits stockables ET consommables (qui peuvent avoir du stock)
                if product.type in ('product', 'consu'):
                    # Déterminer l'emplacement de stock à vérifier
                    session = self.env['pos.session'].browse(order.get('pos_session_id'))
                    location = None
                    
                    if session and session.config_id and session.config_id.picking_type_id:
                        picking_type = session.config_id.picking_type_id

                        warehouse = getattr(picking_type, 'warehouse_id', False)
                        if not warehouse or not warehouse.lot_stock_id:
                            raise UserError(_(
                                "Le type d'opération du POS (%s) n'a pas d'entrepôt ou d'emplacement de stock principal.\n"
                                "Configurez warehouse_id et son lot_stock_id sur l'entrepôt lié au picking type."
                            ) % (picking_type.display_name,))

                        location = warehouse.lot_stock_id
                        _logger.info(
                            "POS STOCK PREVENTION: Utilisation entrepôt picking type '%s' (emplacement: %s)"
                            % (warehouse.display_name, location.display_name)
                        )

                    if not location:
                        # Impossible de déterminer la localisation de stock du POS
                        raise UserError(_(
                            "Impossible de déterminer l'emplacement de stock pour le point de vente.\n"
                            "Vérifiez que le type d'opération du POS possède un entrepôt configuré (picking_type_id.warehouse_id)."
                        ))
                    
                    if location:
                        # Calculer la quantité disponible avec la méthode corrigée
                        available_qty = self._get_available_quantity(product, location)
                        
                        _logger.info(f"POS STOCK PREVENTION: Produit {product.display_name} - Demandé: {qty}, Disponible: {available_qty}")
                        
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
        # Vérifier si la prévention est activée (get_param retourne une string)
        prevent_negative_param = self.env['ir.config_parameter'].sudo().get_param(
            'stock_negative_prevention.prevent_pos', 'False'
        )
        prevent_negative = prevent_negative_param in ('True', 'true', '1', 'yes')
        
        if prevent_negative:
            for vals in vals_list:
                if vals.get('product_id') and vals.get('qty', 0) > 0:
                    product = self.env['product.product'].browse(vals['product_id'])
                    
                    # Vérifier les produits stockables ET consommables (qui peuvent avoir du stock)
                    if product.type in ('product', 'consu'):
                        self._validate_pos_line_stock(product, vals.get('qty', 0))
        
        return super().create(vals_list)

    def write(self, vals):
        """Override pour vérifier le stock lors de la modification de ligne POS"""
        # Vérifier si la prévention est activée (get_param retourne une string)
        prevent_negative_param = self.env['ir.config_parameter'].sudo().get_param(
            'stock_negative_prevention.prevent_pos', 'False'
        )
        prevent_negative = prevent_negative_param in ('True', 'true', '1', 'yes')
        
        if prevent_negative and 'qty' in vals:
            for line in self:
                # Vérifier les produits stockables ET consommables (qui peuvent avoir du stock)
                if line.product_id.type in ('product', 'consu') and vals.get('qty', 0) > 0:
                    self._validate_pos_line_stock(line.product_id, vals['qty'])
        
        return super().write(vals)

    def _validate_pos_line_stock(self, product, qty):
        """Valide le stock pour une ligne POS spécifique"""
        location = None
        
        # Déterminer l'emplacement de stock
        if hasattr(self, 'order_id') and self.order_id.session_id:
            session = self.order_id.session_id
            if session.config_id and session.config_id.picking_type_id:
                picking_type = session.config_id.picking_type_id

                warehouse = getattr(picking_type, 'warehouse_id', False)
                if not warehouse or not warehouse.lot_stock_id:
                    raise UserError(_(
                        "Le type d'opération du POS (%s) n'a pas d'entrepôt ou d'emplacement de stock principal.\n"
                        "Configurez warehouse_id et son lot_stock_id sur l'entrepôt lié au picking type."
                    ) % (picking_type.display_name,))

                location = warehouse.lot_stock_id

        if not location:
            # Impossible de déterminer la localisation de stock pour le POS
            raise UserError(_(
                "Impossible de déterminer l'emplacement de stock pour le point de vente.\n"
                "Vérifiez que le type d'opération du POS possède un entrepôt configuré (picking_type_id.warehouse_id)."
            ))
        
        if location:
            # Calculer la quantité disponible avec la méthode corrigée
            available_qty = self.order_id._get_available_quantity(product, location)
            
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
