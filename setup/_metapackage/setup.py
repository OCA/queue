import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo12-addons-oca-queue",
    description="Meta package for oca-queue Odoo addons",
    version=version,
    install_requires=[
        'odoo12-addon-base_export_async',
        'odoo12-addon-base_import_async',
        'odoo12-addon-queue_job',
        'odoo12-addon-queue_job_batch',
        'odoo12-addon-queue_job_cron',
        'odoo12-addon-test_base_import_async',
        'odoo12-addon-test_queue_job',
        'odoo12-addon-test_queue_job_batch',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
    ]
)
