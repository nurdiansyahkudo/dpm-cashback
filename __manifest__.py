{
    'name': 'Cashback',
    'version': '1.0',
    'summary': 'Module to create cashback invoices for customers',
    'description': """
        This module adds the ability to create cashback invoices from multiple customer invoices.
    """,
    'category': 'Accounting',
    'author': 'PT. Lintang Utama Infotek',
    'depends': ['account'],
    'data': [
        'views/cashback_view.xml',
        'views/cashback_payment_view.xml',
        'views/cashback_package_view.xml',
        # 'views/cashback_wizard_view.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
