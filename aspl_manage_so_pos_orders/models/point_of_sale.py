# -*- coding: utf-8 -*-
#################################################################################
# Author      : Acespritech Solutions Pvt. Ltd. (<www.acespritech.com>)
# Copyright(c): 2012-Present Acespritech Solutions Pvt. Ltd.
# All Rights Reserved.
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#################################################################################

from odoo import models, fields, api, _
from datetime import datetime, timedelta
from odoo.exceptions import Warning
import time
from pytz import timezone
from odoo.tools import float_is_zero


class PosConfig(models.Model):
    _inherit = 'pos.config'

    sale_order_operations = fields.Selection([('draft','Quotations'),
                            ('confirm', 'Confirm'),('paid', 'Paid')], "Operation", default="draft")
    sale_order_last_days = fields.Char("Load Sale Orders to Last days")
    sale_order_record_per_page = fields.Char("Sale Order Per Page")
    order_last_days = fields.Char("Load Orders to Last days")
    order_record_per_page = fields.Char("Record Per Page")
    paid_amount_product = fields.Many2one('product.product', string='Paid Amount Product', domain=[('available_in_pos', '=', True)])
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
    sale_order_invoice = fields.Boolean("Invoice")
    enable_reorder = fields.Boolean("Order Management")


class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def _process_order(self, order):
        pos_line_obj = self.env['pos.order.line']
        draft_order_id = order.get('old_order_id')
        if order.get('draft_order'):
            if not draft_order_id:
                order.pop('draft_order')
                order_id = self.create(self._order_fields(order))
                return order_id
            else:
                order_id = draft_order_id
                pos_line_ids = pos_line_obj.search([('order_id', '=', order_id)])
                if pos_line_ids:
                    pos_line_obj.unlink(pos_line_ids)
                self.write([order_id],
                           {'lines': order['lines'],
                            'partner_id': order.get('partner_id')})
                return order_id

        if not order.get('draft_order') and draft_order_id:
            order_id = draft_order_id
            order_obj = self.browse(order_id)
            pos_line_ids = pos_line_obj.search([('order_id', '=', order_id)])
            if pos_line_ids:
                for line_id in pos_line_ids:
                    line_id.unlink()
            temp = order.copy()
            temp.pop('statement_ids', None)
            temp.pop('name', None)
            temp.update({
                'date_order': order.get('creation_date')
            })
            order_obj.write(temp)
            for payments in order['statement_ids']:
                order_obj.add_payment(self._payment_fields(payments[2]))

            session = self.env['pos.session'].browse(order['pos_session_id'])
            if session.sequence_number <= order['sequence_number']:
                session.write({'sequence_number': order['sequence_number'] + 1})
                session.refresh()

            if not float_is_zero(order['amount_return'], self.env['decimal.precision'].precision_get('Account')):
                cash_journal = session.cash_journal_id
                if not cash_journal:
                    cash_journal_ids = session.statement_ids.filtered(lambda st: st.journal_id.type == 'cash')
                    if not len(cash_journal_ids):
                        raise Warning(_('error!'),
                                             _("No cash statement found for this session. Unable to record returned cash."))
                    cash_journal = cash_journal_ids[0].journal_id
                order_obj.add_payment({
                    'amount':-order['amount_return'],
                    'payment_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'payment_name': _('return'),
                    'journal': cash_journal.id,
                })
            return order_obj

        if not order.get('draft_order') and not draft_order_id:
            order_id = super(PosOrder, self)._process_order(order)
            return order_id

    @api.model
    def ac_pos_search_read(self, domain):
        domain = domain.get('domain')
        search_vals = self.search_read(domain)
        user_id = self.env['res.users'].browse(self._uid)
        tz = False
        result = []
        if self._context and self._context.get('tz'):
            tz = timezone(self._context.get('tz'))
        elif user_id and user_id.tz:
            tz = timezone(user_id.tz)
        if tz:
            c_time = datetime.now(tz)
            hour_tz = int(str(c_time)[-5:][:2])
            min_tz = int(str(c_time)[-5:][3:])
            sign = str(c_time)[-6][:1]
            for val in search_vals:
                if sign == '-':
                    val.update({
                        'date_order':(val.get('date_order') - timedelta(hours=hour_tz, minutes=min_tz)).strftime('%Y-%m-%d %H:%M:%S')
                    })
                elif sign == '+':
                    val.update({
                        'date_order':(val.get('date_order') + timedelta(hours=hour_tz, minutes=min_tz)).strftime('%Y-%m-%d %H:%M:%S')
                    })
                result.append(val)
            return result
        else:
            return search_vals


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def create_from_ui(self, partner):
        if partner.get('property_product_pricelist') :
            price_list_id = int(partner.get('property_product_pricelist'))
            partner.update({'property_product_pricelist': price_list_id})
        return super(ResPartner, self).create_from_ui(partner)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: