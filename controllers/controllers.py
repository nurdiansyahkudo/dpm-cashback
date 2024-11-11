# -*- coding: utf-8 -*-
# from odoo import http


# class Cashback(http.Controller):
#     @http.route('/cashback/cashback', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/cashback/cashback/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('cashback.listing', {
#             'root': '/cashback/cashback',
#             'objects': http.request.env['cashback.cashback'].search([]),
#         })

#     @http.route('/cashback/cashback/objects/<model("cashback.cashback"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('cashback.object', {
#             'object': obj
#         })

