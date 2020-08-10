# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)


{'name': 'Job Queue',
 'version': '12.0.1.5.0',
 'author': 'Camptocamp,ACSONE SA/NV,Odoo Community Association (OCA)',
 'website': 'https://github.com/OCA/queue/tree/12.0/queue_job',
 'license': 'LGPL-3',
 'category': 'Generic Modules',
 'depends': ['mail',
             'base_sparse_field'
             ],
 'external_dependencies': {'python': ['requests'
                                      ],
                           },
 'data': ['security/security.xml',
          'security/ir.model.access.csv',
          'views/queue_job_views.xml',
          'data/queue_data.xml',
          ],
 'installable': True,
 'development_status': 'Mature',
 'maintainers': ['guewen'],
 'post_init_hook': 'post_init_hook'
 }
