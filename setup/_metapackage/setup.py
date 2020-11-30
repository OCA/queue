import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo14-addons-oca-queue",
    description="Meta package for oca-queue Odoo addons",
    version=version,
    install_requires=[
        'odoo14-addon-queue_job',
        'odoo14-addon-test_queue_job',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
    ]
)
