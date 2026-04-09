Odoo treats task synchronously, like when you import a list of products it will treat each line in one big task.
"Queue job" gives you the ability to detail big tasks in many smaller ones.

Imagine you have a lot of data to change for thousand orders, you can do it in one step and cause a heavy load on the server, and this may affect the performance of Odoo. With queue_job you can divide the work in jobs and run thousand jobs (one job for each orders).
An other benefit is if one line failed it doesn't block the processing of the others, as the jobs are independent. 
Plus you can schedule the jobs and set a number of retries.

Here are some community usage examples:

* Mass sending invoices: [account_invoice_mass_sending](https://github.com/OCA/account-invoicing/tree/17.0/account_invoice_mass_sending)
* Import data in the background: [base_import_async](https://github.com/OCA/queue/tree/17.0/base_import_async)
* Export data in the background: [base_export_async](https://github.com/OCA/queue/tree/17.0/base_export_async)
* Generate contract invoices with jobs: [contract_queue_job](https://github.com/OCA/contract/tree/17.0/contract_queue_job)
* Generate partner invoices with jobs:[partner_invoicing_mode](https://github.com/OCA/account-invoicing/tree/17.0/partner_invoicing_mode)
* Process the Sales Automatic Workflow actions with jobs: [sale_automatic_workflow_job](https://github.com/OCA/sale-workflow/tree/17.0/sale_automatic_workflow_job)
