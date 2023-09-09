#### Functionality

This module allows safe usage of OCA's queue_job on odoo.sh with multiple http workers.

In short: It disables the jobrunner on cron workers and uses a leader election system on
the http workers so only one jobrunner is active at any given time.

#### Usage

1. Add this repository as a submodule in your odoo.sh instance

2. Include the module in the server_wide_modules config parameter of your odoo.conf file

   ```
   [options]
   server_wide_modules=web,odoosh_queue_job
   ```

3. Restart odoo

   ```
   odoosh-restart http
   ```
