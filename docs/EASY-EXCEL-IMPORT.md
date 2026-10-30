# One-step Excel import and sticker preview

Install `downloads/Barcode-Easy-Excel-Update.zip` by extracting the entire archive,
closing the running app console and running `Update-Barcode.cmd`. The existing
Python, driver, queue and media dimensions are retained. The update is offline.

Choose the workbook in **CSV / Excel import** and click **Import and preview labels**.
There are no import confirmation checkboxes. A dedicated Print Qty, Print Quantity,
Label Qty, Labels or Copies column is selected automatically, taking precedence
over any generic Quantity column. Otherwise the default is one label per product;
inventory counts are not treated as print requests. Each worksheet/file gets its
own detected defaults. Quantity controls remain editable when a different count
is needed.

The button converts the rows, saves valid products to the queue and opens the
actual sticker preview. If a queue already contains products, replacing it needs
confirmation. Invalid rows are counted in the result message and their errors
remain visible on the import tab. Check spreadsheet rows still offers an optional
table review without changing the queue. Numeric barcodes use the stored values;
leading zeros already lost in Excel cannot be recovered. Warnings now identify
numeric barcode cells rather than ordinary numeric prices or quantities.

Verification: the supplied 81-product workbook imports as 81 labels with Print Qty
automatically selected. Browser verification covers upload, direct preview,
persisted queue, and a subsequent stock-only workbook defaulting to one label
instead of its stock count. Physical Windows printing is not exercised here.
