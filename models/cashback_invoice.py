from odoo import models, fields, api

class CashbackInvoice(models.Model):
    _name = 'cashback.invoice'
    _description = 'Cashback Invoice'

    name = fields.Char(string='Invoice Reference', required=True)
    amount = fields.Float(string='Cashback Amount', required=True)
    percentage = fields.Float(string='Cashback Percentage', required=True)
    date = fields.Date(string='Date', default=fields.Date.context_today)
