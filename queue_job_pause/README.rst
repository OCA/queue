===================
Queue Job Pause
===================

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3
.. |badge3| image:: https://img.shields.io/badge/github-OCA%2Fqueue-lightgray.png?logo=github
    :target: https://github.com/OCA/queue/tree/18.0/queue_job_pause
    :alt: OCA/queue
.. |badge4| image:: https://img.shields.io/badge/weblate-Translate%20me-F47D42.png
    :target: https://translation.odoo-community.org/projects/queue-18-0/queue-18-0-queue_job_pause
    :alt: Translate me on Weblate
.. |badge5| image:: https://img.shields.io/badge/runboat-Try%20me-875A7B.png
    :target: https://runboat.odoo-community.org/builds?repo=OCA/queue&target_branch=18.0
    :alt: Try me on Runboat

|badge1| |badge2| |badge3| |badge4| |badge5|

This module inherith of `queue_job` module to add a new feature, allows to change a channel job to a paused channel (capacity equals zero) using a wizard.

**Table of contents**

.. contents::
   :local:

Usage
=====

In some cases, we need to pause only a job since that it is used to schedule a process for a future date but is needed to filter only the paused ones.

Allows to change a channel job to a paused channel (capacity equals zero) using a wizard.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/OCA/queue/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us to smash it by providing a detailed and welcomed
`feedback <https://github.com/OCA/queue/issues/new?body=module:%20queue_job_pause%0Aversion:%2018.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

Do not contact contributors directly about support or help with technical issues.

Credits
=======

Authors
-------

* Vauxoo

Contributors
------------

-  Jonathan Osorio Alcalá <jonathan@vauxoo.com>

Other credits
-------------

This module was created based on this patch: https://github.com/Vauxoo/queue/pull/10

Maintainers
-----------

This module is maintained by the OCA.

.. image:: https://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: https://odoo-community.org

OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.

This module is part of the `OCA/queue <https://github.com/OCA/queue/tree/18.0/queue_job_subscribe>`_ project on GitHub.

You are welcome to contribute. To learn how please visit https://odoo-community.org/page/Contribute.
