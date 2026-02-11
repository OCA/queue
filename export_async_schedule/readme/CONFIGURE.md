## Creating an Export List

1. Open any model's list view (e.g., Partners, Sales Orders)
2. Select at least one record
3. Click **Action → Export**
4. Select fields to export
5. Save the field list with a meaningful name

## Configuring a Scheduled Export

Navigate to **Settings → Technical → Automation → Scheduled Exports** and create a new
record with:

- Model and export list (created above)
- Export domain (filter records to export)
- Export format (CSV or Excel)
- Recipients (users who will receive the export)
- Schedule (frequency and next execution date)
- Language (for field labels in the export)

A cron job runs hourly to execute scheduled exports and groups.
