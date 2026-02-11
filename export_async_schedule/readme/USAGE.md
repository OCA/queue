When a scheduled export is configured, its execution is automatic based on the
schedule.

Users receive an email with a download link for the exported file. Attachments remain
in the database for 7 days by default (configurable via the `attachment.ttl` system
parameter).

## Export Groups

Group multiple exports into a single email:

1. Navigate to **Settings > Technical > Automation > Grouped Scheduled Exports**
2. Create a group specifying:
   - Recipients (users with email addresses)
   - Email template
   - Exports to include (select from standalone exports or create new ones)
   - Schedule (interval, next execution, language)
3. Use **Send Test Email Now** to verify configuration

**Important**: When an export is added to a group, it automatically inherits the
group's scheduling parameters (recipients, interval, language, etc.). Individual
exports within a group cannot be executed separately - only the group's cron job
triggers their execution as a batch.
