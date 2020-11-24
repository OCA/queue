# -*- coding: utf-8 -*-
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)


{'name': 'Job Queue',
 'version': '10.0.1.1.2',
 'author': 'Camptocamp,ACSONE SA/NV,Odoo Community Association (OCA)',
 'website': 'https://github.com/OCA/queue',
 'license': 'LGPL-3',
 'category': 'Generic Modules',
 'depends': ['mail'
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
 }
