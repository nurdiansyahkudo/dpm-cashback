from odoo import models, fields, api
from odoo.exceptions import UserError
from collections import defaultdict

PAYMENT_STATE_SELECTION = [
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('reversed', 'Reversed'),
        ('invoicing_legacy', 'Invoicing App Legacy'),
]

class AccountMove(models.Model):
    _inherit = 'account.move'

    is_cashback_journal = fields.Boolean(
        compute='_compute_is_cashback_journal',
        store=True,
        string="Is Cashback Journal"
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
    cashback_package = fields.Float(
        string='Cashback Package',
    )

    # Field untuk label dinamis
    move_type_label = fields.Char(string="Move Type Label", compute="_compute_move_type_label")

    # Untuk Brand
    brand = fields.Char(
        string='Brand',
        compute="_compute_brand",
        search="_search_brand",  # Menambahkan fungsi pencarian 
        store=True,  # Store is set to True for better performance
    )

    # Define the invoice_list_ids field
    invoice_list_ids = fields.Many2many(
        'account.move',
        'account_move_cashback_rel',  # Relational table
        'cashback_id',  # Column for cashback invoice
        'invoice_id',    # Column for original invoice
        string="Invoice List"
    )

    selected_invoice_ids = fields.Many2many(
        'account.move',
        'account_move_selected_invoice_rel',
        'cashback_id',
        'selected_invoice_id'
    )

    total_selected_invoices = fields.Monetary(
        string="Total of Selected Invoices",
        compute="_compute_total_selected_invoices",
        store=True,
    )

    # Field untuk status cashback
    cashback_status = fields.Selection(
        [('cashbacked', 'Cashbacked'), ('not_yet', 'Not Yet')],
        string="Cashback Status",
        compute='_compute_cashback_status',
        store=True
    )

    @api.depends('journal_id')
    def _compute_is_cashback_journal(self):
        for record in self:
            record.is_cashback_journal = record.journal_id.name == 'Cashback'

    @api.depends('selected_invoice_ids', 'payment_state')
    def _compute_cashback_status(self):
        for record in self:
            # Check for invoice payment state
            cashbacked = any(
                invoice.move_type == 'in_invoice' and 
                invoice.journal_id.name == 'Cashback' and 
                invoice.payment_state in ['paid', 'in_payment']  # Pertimbangkan status 'paid' dan 'in_payment'
                for invoice in record.selected_invoice_ids
            )
            
            # Memperbarui status cashback
            if cashbacked:
                record.cashback_status = 'cashbacked'  # Status Cashbacked
            else:
                record.cashback_status = 'not_yet'  # Status Not Yet
            

    @api.depends('selected_invoice_ids')
    def _compute_total_selected_invoices(self):
        for record in self:
            total_out_invoice = sum(invoice.amount_untaxed for invoice in record.selected_invoice_ids if invoice.move_type == 'out_invoice')
            total_out_refund = sum(invoice.amount_untaxed for invoice in record.selected_invoice_ids if invoice.move_type == 'out_refund')
            
            # Calculate the total by subtracting out_refund from out_invoice
            record.total_selected_invoices = total_out_invoice - total_out_refund

    @api.depends('invoice_line_ids.name', 'invoice_line_ids.product_id', 'selected_invoice_ids')
    def _compute_brand(self):
        for record in self:
            brands = []
            # Cek apakah ini adalah invoice cashback (tipe 'in_invoice' dan journal adalah Customer Cashback)
            is_cashback_invoice = record.move_type == 'in_invoice' and record.journal_id.name == 'Cashback'

            # Periksa selected_invoice_ids terlebih dahulu
            if record.selected_invoice_ids:
                for selected_invoice in record.selected_invoice_ids:
                    for line in selected_invoice.invoice_line_ids:
                        # Ambil brand dari selected_invoice_ids jika tersedia
                        if line.product_id:
                            brand_value = line.product_id.product_tmpl_id.attribute_line_ids.filtered(
                                lambda x: x.attribute_id.name == 'Brand'
                            ).mapped('value_ids.name')
                            brands.extend(brand_value)
            else:
                # Jika tidak ada selected_invoice_ids, lanjutkan pengecekan di invoice_line_ids
                for line in record.invoice_line_ids:
                    if is_cashback_invoice:
                        # Jika invoice cashback, ambil Brand dari 'name' di invoice_line_ids
                        if "Brand:" in line.name:
                            # Memisahkan teks berdasarkan pola ' - Brand: '
                            brand_info = line.name.split(" - Brand: ")
                            if len(brand_info) > 1:
                                # Mendapatkan nama brand setelah 'Brand:'
                                brand_name = brand_info[1].strip()
                                brands.append(brand_name)
                    else:
                        # Jika bukan invoice cashback, ambil Brand dari product_id
                        if line.product_id:
                            brand_value = line.product_id.product_tmpl_id.attribute_line_ids.filtered(
                                lambda x: x.attribute_id.name == 'Brand'
                            ).mapped('value_ids.name')
                            brands.extend(brand_value)  # Gabungkan brand

            # Menggabungkan brand menjadi string unik
            record.brand = ', '.join(set(brands)) if brands else 'No Brand'


    def _search_brand(self, operator, value):
        # Search for brand
        domain = []
        for move in self.search([]):
            if move.brand and value.lower() in move.brand.lower():
                domain.append(move.id)
        return [('id', 'in', domain)]

    @api.depends('cashback_percentage', 'selected_invoice_ids', 'cashback_package')
    def _compute_cashback_amount(self):
        for record in self:
            # Calculate untaxed amount from selected_invoice_ids
            total_amount = sum(invoice.amount_untaxed for invoice in record.selected_invoice_ids)
            # Check and parse the cashback package value
            cashback_package_value = float(record.cashback_package or 0)
            # Get the cashback percentage and calculate the cashback amount
            cashback_percentage = record.cashback_percentage or 0

            if cashback_percentage:
                cashback_amount = (cashback_percentage / 100) * cashback_package_value
            else:
                cashback_amount = 0

            # Set the cashback amount in the field
            record.cashback_amount = cashback_amount

    @api.depends('move_type', 'journal_id')
    def _compute_move_type_label(self):
        """Ubah label move_type berdasarkan kondisi journal dan move_type."""
        for record in self:
            if record.move_type == 'out_refund' and record.journal_id.name == 'Cashback':
                record.move_type_label = "Customer Cashback"
            elif record.move_type == 'out_refund':
                record.move_type_label = "Customer Credit Note"
            else:
                record.move_type_label = dict(self.fields_get(allfields=['move_type'])['move_type']['selection']).get(record.move_type, "")

    @api.depends('amount_residual', 'move_type', 'state', 'company_id')
    def _compute_payment_state(self):
        stored_ids = tuple(self.ids)
        if stored_ids:
            self.env['account.partial.reconcile'].flush_model()
            self.env['account.payment'].flush_model(['is_matched'])

            queries = []
            for source_field, counterpart_field in (('debit', 'credit'), ('credit', 'debit')):
                queries.append(f'''
                    SELECT
                        source_line.id AS source_line_id,
                        source_line.move_id AS source_move_id,
                        account.account_type AS source_line_account_type,
                        ARRAY_AGG(counterpart_move.move_type) AS counterpart_move_types,
                        ARRAY_AGG(counterpart_move.journal_id) AS counterpart_move_journals,
                        COALESCE(BOOL_AND(COALESCE(pay.is_matched, FALSE))
                            FILTER (WHERE counterpart_move.payment_id IS NOT NULL), TRUE) AS all_payments_matched,
                        BOOL_OR(COALESCE(BOOL(pay.id), FALSE)) as has_payment,
                        BOOL_OR(COALESCE(BOOL(counterpart_move.statement_line_id), FALSE)) as has_st_line
                    FROM account_partial_reconcile part
                    JOIN account_move_line source_line ON source_line.id = part.{source_field}_move_id
                    JOIN account_account account ON account.id = source_line.account_id
                    JOIN account_move_line counterpart_line ON counterpart_line.id = part.{counterpart_field}_move_id
                    JOIN account_move counterpart_move ON counterpart_move.id = counterpart_line.move_id
                    LEFT JOIN account_payment pay ON pay.id = counterpart_move.payment_id
                    WHERE source_line.move_id IN %s AND counterpart_line.move_id != source_line.move_id
                    GROUP BY source_line.id, source_line.move_id, account.account_type
                ''')

            self._cr.execute(' UNION ALL '.join(queries), [stored_ids, stored_ids])
            payment_data = defaultdict(lambda: [])
            for row in self._cr.dictfetchall():
                payment_data[row['source_move_id']].append(row)
        else:
            payment_data = {}

        for invoice in self:
            if invoice.payment_state == 'invoicing_legacy':
                continue

            currencies = invoice._get_lines_onchange_currency().currency_id
            currency = currencies if len(currencies) == 1 else invoice.company_id.currency_id
            reconciliation_vals = payment_data.get(invoice.id, [])
            payment_state_matters = invoice.is_invoice(True)

            if payment_state_matters:
                reconciliation_vals = [x for x in reconciliation_vals if x['source_line_account_type'] in ('asset_receivable', 'liability_payable')]

            new_pmt_state = 'not_paid'
            if invoice.state == 'posted':
                if payment_state_matters:
                    if currency.is_zero(invoice.amount_residual):
                        if any(x['has_payment'] or x['has_st_line'] for x in reconciliation_vals):
                            if all(x['all_payments_matched'] for x in reconciliation_vals):
                                new_pmt_state = 'paid'
                            else:
                                new_pmt_state = invoice._get_invoice_in_payment_state()
                        else:
                            new_pmt_state = 'paid'

                            reverse_move_types = set()
                            reverse_journal_id = set()

                            for x in reconciliation_vals:
                                for move_type in x['counterpart_move_types']:
                                    reverse_move_types.add(move_type)
                            
                            for x in reconciliation_vals:
                                for journal_id in x['counterpart_move_journals']:
                                    reverse_journal_id.add(journal_id)

                            in_reverse = (invoice.move_type in ('in_invoice', 'in_receipt')
                                          and (reverse_move_types == {'in_refund'} or reverse_move_types == {'in_refund', 'entry'}))
                            out_reverse = (invoice.move_type in ('out_invoice', 'out_receipt')
                                           and (reverse_move_types == {'out_refund'} or reverse_move_types == {'out_refund', 'entry'}))
                            cashback = (invoice.move_type in ('out_invoice', 'out_receipt')
                                           and (reverse_move_types == {'out_refund'} or reverse_move_types == {'out_refund', 'entry'}) and reverse_journal_id.name == {'Cashback'})
                            misc_reverse = (invoice.move_type in ('entry', 'out_refund', 'in_refund')
                                            and reverse_move_types == {'entry'})

                            if cashback:
                                new_pmt_state = 'in_payment'
                            elif in_reverse or out_reverse or misc_reverse:
                                new_pmt_state = 'reversed'

                    elif reconciliation_vals:
                        new_pmt_state = 'partial'

            invoice.payment_state = new_pmt_state

    @api.model
    def create_cashback(self):
        # Mendapatkan invoice yang dipilih oleh user
        invoices = self.env['account.move'].browse(self.env.context.get('active_ids', []))
        
        # Pastikan semua invoice memiliki payment_state 'in_payment' atau 'paid' dan cashback_status 'not yet'
        if any(invoice.payment_state not in ['in_payment', 'paid'] for invoice in invoices):
            raise UserError("Only paid invoices are eligible for cashback. Please select the appropriate invoices.")
        
        # Menampilkan jendela pilihan paket cashback jika semua invoice valid
        return self.with_context(active_ids=invoices.ids).action_open_cashback_package_wizard()
    
    def action_open_cashback_package_wizard(self):
    # Open the cashback package selection wizard
        return {
            'type': 'ir.actions.act_window',
            'name': 'Select Cashback Package',
            'res_model': 'cashback.package.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('cashback.view_cashback_package_wizard_form').id,
            'target': 'new',
            'context': {'active_ids': self.env.context.get('active_ids', [])}
        }

    def action_post(self):
        super(AccountMove, self).action_post()

        for move in self:
            if move.move_type == 'in_invoice' and move.journal_id.name == 'Cashback':
                # Update cashback status for selected invoices
                for invoice in move.selected_invoice_ids:
                    if invoice.move_type == 'out_invoice':  # Ensure only regular invoices are checked
                        invoice.cashback_status = 'cashbacked'  # Set status to 'cashbacked'

    def action_payment_register(self):
        # Check if the journal is 'Customer Cashback'
        if self.journal_id.name == 'Cashback':
            # Execute the custom wizard
            return {
                'name': 'Register Payment for Cashback',
                'type': 'ir.actions.act_window',
                'res_model': 'account.payment.register',
                'view_mode': 'form',
                'view_id': self.env.ref('account.view_account_payment_form').id,
                'target': 'new',
                'context': {
                    'default_amount': self.amount_residual,
                    'default_partner_id': self.partner_id.id,
                    'default_payment_options': 'direct_customer',
                    'active_model': 'account.move',
                    'active_ids': [self.id],
                    'active_id': self.id,
                },
            }
        else:
            # If the journal is not 'Customer Cashback', run the default Odoo action
            return super(AccountMove, self).action_payment_register()
        
    def button_cancel(self):
        # Jalankan fungsi pembatalan default
        res = super(AccountMove, self).button_cancel()

        for move in self:
            if move.move_type == 'in_invoice' and move.journal_id.name == 'Cashback':
                # Ubah status cashback untuk invoice yang terkait menjadi 'not_yet'
                for invoice in move.selected_invoice_ids:
                    invoice.cashback_status = 'not_yet'

        return res