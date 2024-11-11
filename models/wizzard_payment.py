from odoo import models, fields, api
from odoo.exceptions import UserError

class CashbackPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    payment_options = fields.Selection(
        [('direct_customer', 'Direct'), ('pay_another_invoice', 'Reduce another Invoice')],
        string='Payment Options',
        default='direct_customer',
    )

    selected_invoice_ids = fields.Many2many(
        'account.move',
        string='Invoices to Pay',
        domain="[('partner_id', '=', partner_id), ('state', '=', 'posted'), ('payment_state', 'in', ['not_paid', 'partial']), ('move_type', '=', 'out_invoice')]",
    )

    def action_create_payment(self):
        if self.payment_options == 'direct_customer':
            return super(CashbackPaymentRegister, self).action_create_payments()

        elif self.payment_options == 'pay_another_invoice':
            if not self.selected_invoice_ids:
                raise UserError("You must select at least one invoice to pay.")

            # Ambil jumlah cashback yang akan dibayarkan
            total_cashback_amount = self.amount

            # Iterasi melalui invoice yang dipilih
            for invoice in self.selected_invoice_ids:
                if total_cashback_amount <= 0:
                    break  # Jika cashback sudah habis, hentikan loop

                # Tentukan jumlah yang bisa dibayarkan untuk invoice ini
                amount_to_pay = min(total_cashback_amount, invoice.amount_residual)

                # Kurangi amount_residual dari invoice yang dipilih
                new_amount_residual = invoice.amount_residual - amount_to_pay
                new_amount_residual_signed = invoice.amount_residual_signed - amount_to_pay

                # Update amount_residual tanpa mengubah status pembayaran (tetap "not_paid")
                invoice.write({
                    'amount_residual': new_amount_residual,
                    'amount_residual_signed': new_amount_residual_signed,
                })

                # Check and update the payment state if necessary
                if new_amount_residual > 0 and invoice.payment_state == 'not_paid':
                    invoice.payment_state = 'partial'
                elif new_amount_residual <= 0:
                    invoice.payment_state = 'paid'  # Optionally, if it's fully paid

                # Kurangi total_cashback_amount dengan jumlah yang dibayarkan
                total_cashback_amount -= amount_to_pay

                # Tambahkan catatan pembayaran di chatter atau log aktivitas
                invoice.message_post(body=f"Invoice {invoice.name} has been partially reduced by cashback: {amount_to_pay}. New residual: {new_amount_residual}")

            # Setelah memotong tagihan pada invoice yang dipilih, lakukan pembayaran cashback untuk invoice cashback
            return super(CashbackPaymentRegister, self).action_create_payments()