/** @odoo-module **/

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(Order.prototype, {
    /**
     * Override pour vérifier le stock avant validation de la commande POS
     */
    async pay() {
        // Vérifier si la prévention est activée
        const preventNegative = this.pos.config.prevent_negative_stock_pos;
        
        if (preventNegative) {
            const stockValidation = await this._checkStockAvailability();
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
     * Vérifie la disponibilité du stock pour toutes les lignes de commande
     */
    async _checkStockAvailability() {
        const insufficientProducts = [];
        
        for (const line of this.get_orderlines()) {
            const product = line.get_product();
            const qty = line.get_quantity();
            
            if (product.type === 'product' && qty > 0) {
                // Obtenir la quantité disponible depuis le cache POS ou faire un appel RPC
                let availableQty = product.qty_available || 0;
                
                // Si la quantité n'est pas en cache, faire un appel RPC
                if (availableQty === undefined) {
                    try {
                        const result = await this.pos.orm.call(
                            'product.product',
                            'read',
                            [product.id, ['qty_available']],
                            {
                                context: {
                                    location: this.pos.config.stock_location_id ? 
                                             this.pos.config.stock_location_id[0] : 
                                             this.pos.config.picking_type_id[0]
                                }
                            }
                        );
                        availableQty = result[0].qty_available;
                    } catch (error) {
                        console.error('Erreur lors de la vérification du stock:', error);
                        availableQty = 0;
                    }
                }
                
                if (qty > availableQty) {
                    insufficientProducts.push({
                        product: product.display_name,
                        requested: qty,
                        available: availableQty,
                        uom: product.uom_id[1]
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

// Extension du modèle Orderline pour validation en temps réel
import { Orderline } from "@point_of_sale/app/store/models";

patch(Orderline.prototype, {
    /**
     * Override pour vérifier le stock lors de la modification de quantité
     */
    set_quantity(quantity, keep_price) {
        const preventNegative = this.pos.config.prevent_negative_stock_pos;
        
        if (preventNegative && this.product.type === 'product' && quantity > 0) {
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
