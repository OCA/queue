import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo10-addons-oca-queue",
    description="Meta package for oca-queue Odoo addons",
    version=version,
    install_requires=[
        'odoo10-addon-queue_job',
        'odoo10-addon-queue_job_cron',
        'odoo10-addon-queue_job_subscribe',
        'odoo10-addon-test_queue_job',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
    ]
)
