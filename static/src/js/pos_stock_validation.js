// Log de confirmation que le module JavaScript est chargé
console.log('🚀 STOCK NEGATIVE PREVENTION: Module JavaScript chargé avec succès !');
console.log('📦 STOCK NEGATIVE PREVENTION: Version Odoo classique pour compatibilité');

odoo.define('stock_negative_prevention.pos_stock_validation', function (require) {
    'use strict';

    var models = require('point_of_sale.models');
    var screens = require('point_of_sale.screens');
    var core = require('web.core');
    var rpc = require('web.rpc');
    var _t = core._t;

    console.log('📦 STOCK NEGATIVE PREVENTION: Modules POS chargés avec succès !');

    // Extension du modèle Order pour validation de stock
    var _super_order = models.Order.prototype;
    models.Order = models.Order.extend({
        
        /**
         * Override pour vérifier le stock avant validation de la commande POS
         * Gère TOUTES les commandes : nouvelles, importées, devis, etc.
         */
        initialize: function(attributes, options) {
            _super_order.initialize.call(this, attributes, options);
            console.log('STOCK VALIDATION: Order initialisé avec validation de stock');
        },

        /**
         * Vérifie la disponibilité du stock pour toutes les lignes de commande
         */
        check_stock_availability: function() {
            var self = this;
            var prevent_negative = this.pos.config.prevent_negative_stock_pos;
            
            console.log('STOCK VALIDATION: prevent_negative_stock_pos =', prevent_negative);
            
            if (!prevent_negative) {
                console.log('STOCK VALIDATION: Validation désactivée');
                return Promise.resolve({success: true});
            }

            console.log('STOCK VALIDATION: Vérification de', this.get_orderlines().length, 'lignes de commande');
            
            var insufficient_products = [];
            var promises = [];

            this.get_orderlines().forEach(function(line) {
                var product = line.get_product();
                var qty = line.get_quantity();
                
                console.log('STOCK VALIDATION: Produit', product.display_name, 'Type:', product.type, 'Qty:', qty);
                
                // Vérifier les produits stockables ET consommables (qui peuvent avoir du stock)
                if ((product.type === 'product' || product.type === 'consu') && qty > 0) {
                    
                    // Faire un appel RPC pour obtenir le stock en temps réel
                    var promise = rpc.query({
                        model: 'stock.quant',
                        method: '_get_available_quantity',
                        args: [product.id, self.pos.config.stock_location_id ? 
                               self.pos.config.stock_location_id[0] : null]
                    }).then(function(available_qty) {
                        available_qty = available_qty || 0;
                        console.log('STOCK VALIDATION: Stock RPC pour', product.display_name, ':', available_qty);
                        console.log('STOCK VALIDATION: Comparaison -', product.display_name, '- Demandé:', qty, 'Disponible:', available_qty);
                        
                        if (qty > available_qty) {
                            console.log('STOCK VALIDATION: STOCK INSUFFISANT pour', product.display_name);
                            insufficient_products.push({
                                product: product.display_name,
                                requested: qty,
                                available: available_qty,
                                uom: product.uom_id ? product.uom_id[1] : 'unité'
                            });
                        }
                    }).catch(function(error) {
                        console.error('STOCK VALIDATION: Erreur RPC pour', product.display_name, ':', error);
                        // En cas d'erreur, considérer le stock comme insuffisant par sécurité
                        insufficient_products.push({
                            product: product.display_name,
                            requested: qty,
                            available: 0,
                            uom: product.uom_id ? product.uom_id[1] : 'unité'
                        });
                    });
                    
                    promises.push(promise);
                }
            });

            return Promise.all(promises).then(function() {
                if (insufficient_products.length > 0) {
                    var error_msg = _t("Stock insuffisant pour les produits suivants :\n\n");
                    insufficient_products.forEach(function(product_info) {
                        error_msg += "• " + product_info.product + " : Demandé " + 
                                   product_info.requested + " " + product_info.uom + 
                                   ", Disponible " + product_info.available + " " + product_info.uom + "\n";
                    });
                    error_msg += _t("\nVeuillez ajuster les quantités ou réapprovisionner le stock.");
                    
                    return {
                        success: false,
                        message: error_msg
                    };
                }
                
                return {
                    success: true,
                    message: _t("Stock suffisant pour tous les produits.")
                };
            });
        }
    });

    // Extension de l'écran de paiement pour intercepter TOUS les paiements
    var PaymentScreenWidget = screens.PaymentScreenWidget;
    screens.PaymentScreenWidget.include({
        
        /**
         * Override pour vérifier le stock avant TOUT paiement
         * Intercepte les commandes importées, nouvelles, etc.
         */
        validate_order: function(force_validation) {
            var self = this;
            var order = this.pos.get_order();
            
            console.log('STOCK VALIDATION: Validation depuis PaymentScreen...');
            
            return order.check_stock_availability().then(function(stock_validation) {
                if (!stock_validation.success) {
                    self.gui.show_popup('error', {
                        'title': _t('Stock Insuffisant - Paiement Bloqué'),
                        'body': stock_validation.message,
                    });
                    return false;
                }
                
                // Si le stock est suffisant, continuer avec la validation normale
                return PaymentScreenWidget.prototype.validate_order.call(self, force_validation);
            }).catch(function(error) {
                console.error('STOCK VALIDATION: Erreur lors de la validation:', error);
                self.gui.show_popup('error', {
                    'title': _t('Erreur de Validation'),
                    'body': _t('Erreur lors de la vérification du stock. Veuillez réessayer.'),
                });
                return false;
            });
        }
    });

    console.log('✅ STOCK NEGATIVE PREVENTION: Module JavaScript initialisé avec succès !');
    
    return {
        Order: models.Order,
        PaymentScreenWidget: screens.PaymentScreenWidget
    };
});
