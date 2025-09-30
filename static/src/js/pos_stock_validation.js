/** @odoo-module **/

import { Order, Orderline } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

patch(Order.prototype, {
    /**
     * Override pour vérifier le stock avant validation de la commande POS
     * Gère TOUTES les commandes : nouvelles, importées, devis, etc.
     */
    async pay() {
        // Vérifier si la prévention est activée
        const preventNegative = this.pos.config.prevent_negative_stock_pos;
        
        if (preventNegative) {
            console.log('STOCK VALIDATION: Vérification du stock avant paiement...');
            const stockValidation = await this._checkStockAvailability(true); // Force la vérification RPC
            if (!stockValidation.success) {
                this.pos.popup.add('ErrorPopup', {
                    title: _t('Stock Insuffisant'),
                    body: stockValidation.message,
                });
                return false;
            }
        }
        
        return super.pay(...arguments);
    },

    /**
     * Override pour vérifier le stock lors de la finalisation
     * Sécurité supplémentaire pour les commandes importées
     */
    async finalize() {
        const preventNegative = this.pos.config.prevent_negative_stock_pos;
        
        if (preventNegative) {
            console.log('STOCK VALIDATION: Vérification finale du stock...');
            const stockValidation = await this._checkStockAvailability(true);
            if (!stockValidation.success) {
                this.pos.popup.add('ErrorPopup', {
                    title: _t('Stock Insuffisant - Finalisation Bloquée'),
                    body: stockValidation.message,
                });
                return false;
            }
        }
        
        return super.finalize(...arguments);
    },

    /**
     * Vérifie la disponibilité du stock pour toutes les lignes de commande
     * @param {boolean} forceRPC - Force l'appel RPC même si le stock est en cache
     */
    async _checkStockAvailability(forceRPC = false) {
        const insufficientProducts = [];
        
        console.log('STOCK VALIDATION: Vérification de', this.get_orderlines().length, 'lignes de commande');
        
        for (const line of this.get_orderlines()) {
            const product = line.get_product();
            const qty = line.get_quantity();
            
            console.log('STOCK VALIDATION: Produit', product.display_name, 'Type:', product.type, 'Qty:', qty);
            
            // Vérifier les produits stockables ET consommables (qui peuvent avoir du stock)
            if ((product.type === 'product' || product.type === 'consu') && qty > 0) {
                let availableQty = 0;
                
                // TOUJOURS faire un appel RPC pour avoir le stock en temps réel
                // Particulièrement important pour les commandes importées
                if (forceRPC || product.qty_available === undefined) {
                    try {
                        console.log('STOCK VALIDATION: Appel RPC pour', product.display_name);
                        const result = await this.pos.orm.call(
                            'stock.quant',
                            '_get_available_quantity',
                            [product.id, this.pos.config.stock_location_id ? 
                                        this.pos.config.stock_location_id[0] : 
                                        this.pos.config.picking_type_id ? 
                                        this.pos.config.picking_type_id[0] : null]
                        );
                        availableQty = result || 0;
                        console.log('STOCK VALIDATION: Stock RPC pour', product.display_name, ':', availableQty);
                    } catch (error) {
                        console.error('STOCK VALIDATION: Erreur RPC pour', product.display_name, ':', error);
                        // Fallback sur l'ancienne méthode
                        try {
                            const fallbackResult = await this.pos.orm.call(
                                'product.product',
                                'read',
                                [product.id, ['qty_available']]
                            );
                            availableQty = fallbackResult[0].qty_available || 0;
                            console.log('STOCK VALIDATION: Stock fallback pour', product.display_name, ':', availableQty);
                        } catch (fallbackError) {
                            console.error('STOCK VALIDATION: Erreur fallback pour', product.display_name, ':', fallbackError);
                            availableQty = 0;
                        }
                    }
                } else {
                    availableQty = product.qty_available || 0;
                    console.log('STOCK VALIDATION: Stock cache pour', product.display_name, ':', availableQty);
                }
                
                console.log('STOCK VALIDATION: Comparaison -', product.display_name, '- Demandé:', qty, 'Disponible:', availableQty);
                
                if (qty > availableQty) {
                    console.log('STOCK VALIDATION: STOCK INSUFFISANT pour', product.display_name);
                    insufficientProducts.push({
                        product: product.display_name,
                        requested: qty,
                        available: availableQty,
                        uom: product.uom_id ? product.uom_id[1] : 'unité'
                    });
                }
            }
        }
        
        if (insufficientProducts.length > 0) {
            let errorMsg = _t("Stock insuffisant pour les produits suivants :\n\n");
            for (const productInfo of insufficientProducts) {
                errorMsg += `• ${productInfo.product} : Demandé ${productInfo.requested} ${productInfo.uom}, Disponible ${productInfo.available} ${productInfo.uom}\n`;
            }
            errorMsg += _t("\nVeuillez ajuster les quantités ou réapprovisionner le stock.");
            
            return {
                success: false,
                message: errorMsg
            };
        }
        
        return {
            success: true,
            message: _t("Stock suffisant pour tous les produits.")
        };
    }
});

// Extension de l'écran de paiement pour intercepter TOUS les paiements
patch(PaymentScreen.prototype, {
    /**
     * Override pour vérifier le stock avant TOUT paiement
     * Intercepte les commandes importées, nouvelles, etc.
     */
    async validateOrder(isForceValidate) {
        const order = this.pos.get_order();
        const preventNegative = this.pos.config.prevent_negative_stock_pos;
        
        if (preventNegative && order) {
            console.log('STOCK VALIDATION: Validation depuis PaymentScreen...');
            const stockValidation = await order._checkStockAvailability(true); // Force RPC
            if (!stockValidation.success) {
                this.popup.add('ErrorPopup', {
                    title: _t('Stock Insuffisant - Paiement Bloqué'),
                    body: stockValidation.message,
                });
                return false;
            }
        }
        
        return super.validateOrder(isForceValidate);
    }
});

// Extension du modèle Orderline pour validation en temps réel

patch(Orderline.prototype, {
    /**
     * Override pour vérifier le stock lors de la modification de quantité
     */
    set_quantity(quantity, keep_price) {
        const preventNegative = this.pos.config.prevent_negative_stock_pos;
        
        // Vérifier les produits stockables ET consommables (qui peuvent avoir du stock)
        if (preventNegative && (this.product.type === 'product' || this.product.type === 'consu') && quantity > 0) {
            const availableQty = this.product.qty_available || 0;
            
            if (quantity > availableQty) {
                this.pos.popup.add('ErrorPopup', {
                    title: _t('Stock Insuffisant'),
                    body: _t(
                        'Attention : Stock insuffisant pour %s.\n' +
                        'Quantité demandée : %s %s\n' +
                        'Quantité disponible : %s %s\n\n' +
                        'Veuillez ajuster la quantité.'
                    ).replace('%s', this.product.display_name)
                     .replace('%s', quantity)
                     .replace('%s', this.product.uom_id[1])
                     .replace('%s', availableQty)
                     .replace('%s', this.product.uom_id[1])
                });
                return false;
            }
        }
        
        return super.set_quantity(quantity, keep_price);
    }
});
