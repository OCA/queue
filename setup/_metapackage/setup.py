import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo11-addons-oca-queue",
    description="Meta package for oca-queue Odoo addons",
    version=version,
    install_requires=[
        'odoo11-addon-base_import_async',
        'odoo11-addon-mail_queue_job',
        'odoo11-addon-queue_job',
        'odoo11-addon-queue_job_batch',
        'odoo11-addon-queue_job_subscribe',
        'odoo11-addon-test_base_import_async',
        'odoo11-addon-test_queue_job',
        'odoo11-addon-test_queue_job_batch',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
    ]
)
