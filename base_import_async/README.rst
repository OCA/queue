.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
    :alt: License: AGPL-3

Odoo Asynchronous import module
===============================

This module extends the standard CSV import functionality
to import files in the background using the OCA/connector
framework.

The user is presented with a new checkbox in the import
screen. When selected, the import is delayed in a background
job.

This job in turn splits the CSV file in chunks of minimum 
100 lines (or more to align with record boundaries). Each
chunk is then imported in a separate background job.

When an import fails, the job is marked as such and the
user can read the error in the job status. The CSV chunk
being imported is stored as an attachment to the job, making
it easy to download it, fix it and run a new import, possibly
in synchronous mode since the chunks are small.

Scope
-----

Any file that can be imported by the standard import mechanism
can also be imported in the background.

This module's scope is limited to making standard imports
asynchronous. It does not attempt to transform the data nor
automate ETL flows.

Other modules may benefit from this infrastructure in the following way
(as illustrated in the test suite):

1. create an instance of `base_import.import` and populate its fields
   (`res_model`, `file`, `file_name`),
2. invoke the `do` method with appropriate options 
   (`header`, `encoding`, `separator`, `quoting`,
   `use_connector`, `chunk_size`).

Known limitations
=================

* There is currently no user interface to control the chunk size,
  which is currently 100 by default. Should this proves to be an issue,
  it is easy to add an option to extend the import screen.
* Validation cannot be run in the background.

Credits
=======

Contributors
------------

Sébastien Beau (Akretion) authored the initial prototype.

Stéphane Bidoul (ACSONE) extended it to version 1.0 to support
multi-line records, store data to import as attachments
and let the user control the asynchronous behaviour.

Other contributors include:

* Anthony Muschang (ACSONE)
* David Béal (Akretion)
* Jonathan Nemry (ACSONE)
* Laurent Mignon (ACSONE)

Maintainer
----------

.. image:: http://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: http://odoo-community.org

This module is maintained by the OCA.

OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.

To contribute to this module, please visit http://odoo-community.org.
