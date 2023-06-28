import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo-addons-oca-queue",
    description="Meta package for oca-queue Odoo addons",
    version=version,
    install_requires=[
        'odoo-addon-base_import_async>=16.0dev,<16.1dev',
        'odoo-addon-queue_job>=16.0dev,<16.1dev',
        'odoo-addon-queue_job_cron>=16.0dev,<16.1dev',
        'odoo-addon-queue_job_cron_jobrunner>=16.0dev,<16.1dev',
        'odoo-addon-test_queue_job>=16.0dev,<16.1dev',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 16.0',
    ]
)
