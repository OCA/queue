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
   `use_queue`, `chunk_size`).
