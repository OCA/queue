import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo13-addons-oca-queue",
    description="Meta package for oca-queue Odoo addons",
    version=version,
    install_requires=[
        'odoo13-addon-base_import_async',
        'odoo13-addon-queue_job',
        'odoo13-addon-queue_job_cron',
        'odoo13-addon-queue_job_subscribe',
        'odoo13-addon-test_base_import_async',
        'odoo13-addon-test_queue_job',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
    ]
)
