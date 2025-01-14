from odoo import models, fields, api
from odoo.exceptions import UserError

class CashbackPackageWizard(models.TransientModel):
    _name = 'cashback.package.wizard'
    _description = 'Wizard to Select Cashback Package'

    cashback_package = fields.Float(
        string='Cashback Package',
    )
    cashback_percentage = fields.Float(
        string='Cashback Percentage',
        help="Enter a cashback percentage, e.g., 10 for 10%."
    )
    cashback_amount = fields.Monetary(
        string='Cashback Amount',
        readonly=False,
        compute='_compute_cashback_amount',
        store=True,  # Changed to store=True for better performance and usability
    )
    selected_invoice_ids = fields.Many2many(
        'account.move',
        string="Selected Invoices",
        readonly=True,
        help="List of selected invoices with their details."
    )
    total_selected_invoices = fields.Monetary(
        string="Total of Selected Invoices",
        compute="_compute_total_selected_invoices",
        store=True,
    )
    currency_id = fields.Many2one('res.currency', string="Currency", required=True)

    partner_id = fields.Many2one('res.partner', string="Partner", required=True, help="The customer associated with the selected invoices.")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            invoices = self.env['account.move'].browse(active_ids)
            res.update({
                'selected_invoice_ids': [(6, 0, invoices.ids)],
                'currency_id': self.env.user.company_id.currency_id.id,
            })
        return res

    @api.depends('selected_invoice_ids')
    def _compute_total_selected_invoices(self):
        for record in self:
            total_out_invoice = sum(invoice.amount_untaxed for invoice in record.selected_invoice_ids if invoice.move_type == 'out_invoice')
            total_out_refund = sum(invoice.amount_untaxed for invoice in record.selected_invoice_ids if invoice.move_type == 'out_refund')
            
            # Calculate the total by subtracting out_refund from out_invoice
            record.total_selected_invoices = total_out_invoice - total_out_refund

    @api.depends('cashback_percentage', 'selected_invoice_ids', 'cashback_package')
    def _compute_cashback_amount(self):
        for record in self:
            # Hitung total untaxed amount dari selected_invoice_ids
            total_amount = sum(invoice.amount_untaxed for invoice in record.selected_invoice_ids)
            # Check and parse the cashback package value
            cashback_package_value = record.cashback_package
            # Get the cashback percentage and calculate the cashback amount
            cashback_percentage = record.cashback_percentage or 0

            if cashback_percentage:
                cashback_amount = (cashback_percentage / 100) * cashback_package_value
            else:
                cashback_amount = 0

            # Set the cashback amount in the field
            record.cashback_amount = cashback_amount

    def action_create_cashback_invoice(self):
        # Mendapatkan invoice yang dipilih oleh user
        invoices = self.env['account.move'].browse(self.env.context.get('active_ids', []))

        if not invoices:
            return

        # Journal khusus untuk Customer Cashback
        cashback_journal = self.env['account.journal'].search([('name', '=', 'Cashback')], limit=1)
        if not cashback_journal:
            raise UserError("Journal 'Cashback' not found!")
        
        # Fetch the "Cashback Expenses" account
        cashback_expenses_account = self.env['account.account'].search([('code', '=', '42200000000')], limit=1)
        if not cashback_expenses_account:
            raise UserError("Account not found!")

        # Fetch the "Accrued Expenses - Customers Cashback" account
        accrued_expenses_account = self.env['account.account'].search([('code', '=', '24300000000')], limit=1)
        if not accrued_expenses_account:
            raise UserError("Account not found!")

        # Memastikan semua invoice memiliki partner yang sama
        partner = invoices[0].partner_id
        if any(invoice.partner_id != partner for invoice in invoices):
            raise UserError("All selected invoices must have the same partner for cashback.")

        # Mendapatkan nilai cashback_package dan mengonversinya ke float
        cashback_amount = self.cashback_amount

        # Inisialisasi variabel untuk menyimpan data invoice cashback
        cashback_invoice_vals = {
            'move_type': 'out_refund',  # Tipe invoice: customer refund
            'journal_id': cashback_journal.id,
            'partner_id': partner.id,
            'invoice_line_ids': [],
            'selected_invoice_ids': [(6, 0, invoices.ids)],  # Link original invoices
            'cashback_package': self.cashback_package, # Set the default cashback package in invoice
            'cashback_percentage': self.cashback_percentage, # Set the default cashback percentage in invoice
            'cashback_amount': self.cashback_amount, # Set the default cashback amount in invoice
        }

        # Membuat line product untuk "Cashback" dengan nilai cashback_amount
        product_cashback = self.env['product.product'].search([('name', 'ilike', 'Cashback')], limit=1)

        if not product_cashback:
            raise UserError("Product 'Cashback' does not exist. Please create it first.")

        # Menambahkan produk "Cashback" ke invoice line dengan nilai cashback_amount
        cashback_invoice_vals['invoice_line_ids'].append((0, 0, {
            'product_id': product_cashback.id,
            'name': f'Cashback for {partner.name}',  # Nama produk "Cashback"
            'quantity': 1,
            'price_unit': cashback_amount,  # Menggunakan nilai cashback_amount
            'tax_ids': [(6, 0, [])],  # Mengatur pajak menjadi tidak ada
            'account_id': cashback_expenses_account.id,  # Menggunakan akun Cashback Expenses
        }))

        # Membuat invoice cashback
        cashback_invoice = self.env['account.move'].create(cashback_invoice_vals)

        # Kembalikan aksi untuk membuka invoice yang baru dibuat
        return {
            'name': 'Customer Cashback',
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': cashback_invoice.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
            'views': [(self.env.ref('cashback.view_move_form_cashback').id, 'form')],
        }