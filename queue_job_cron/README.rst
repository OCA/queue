.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

==============
Queue Job Cron
==============

This module extends the functionality of queue_job and allows to run an Odoo
cron as a queue job.

Installation
============

To install this module, you need to:

#. Just install it.

Configuration
=============

To configure this module, you need to:

#. Nothing special to do.

Usage
=====

To use this module, you need to:

#. Go to a scheduled action, a flag "Run as queue job" will allow you to run
the action as a queue job. You will also allowed to select a channel of its
execution.
To configure dedicated channels please refers to queue_job help: https://github.com/OCA/queue/blob/10.0/queue_job/README.rst

Channels can be used to manage sequential jobs and prevent concurrency accesses.
To do that you just have to define a channel per cron limited to 1 at time.

.. image:: https://odoo-community.org/website/image/ir.attachment/5784_f2813bd/datas
   :alt: Try me on Runbot
   :target: https://runbot.odoo-community.org/runbot/230/10.0

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/OCA/queue/issues>`_. In case of trouble, please
check there if your issue has already been reported. If you spotted it first,
help us smashing it by providing a detailed and welcomed feedback.

Credits
=======

Images
------

* Odoo Community Association: `Icon <https://odoo-community.org/logo.png>`_.

Contributors
------------

* Cédric Pigeon <cedric.pigeon@acsone.eu>

Do not contact contributors directly about support or help with technical issues.

Maintainer
----------

.. image:: https://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: https://odoo-community.org

This module is maintained by the OCA.

OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.

To contribute to this module, please visit https://odoo-community.org.