import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo-addons-oca-queue",
    description="Meta package for oca-queue Odoo addons",
    version=version,
    install_requires=[
        'odoo-addon-queue_job>=15.0dev,<15.1dev',
        'odoo-addon-queue_job_cron>=15.0dev,<15.1dev',
        'odoo-addon-queue_job_cron_jobrunner>=15.0dev,<15.1dev',
        'odoo-addon-queue_job_subscribe>=15.0dev,<15.1dev',
        'odoo-addon-test_queue_job>=15.0dev,<15.1dev',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 15.0',
    ]
)
