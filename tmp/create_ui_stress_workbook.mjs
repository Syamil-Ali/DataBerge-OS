import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = "outputs/ui-stress-workbook";
await fs.mkdir(outputDir, { recursive: true });

function columnName(n) {
  let s = "";
  while (n > 0) {
    const r = (n - 1) % 26;
    s = String.fromCharCode(65 + r) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

const workbook = Workbook.create();
const headerFill = "#172033";
const headerFont = { name: "Arial", bold: true, color: "#FFFFFF" };
const bodyFont = { name: "Arial", size: 10, color: "#172033" };

const tableColumns = [
  "record_id", "name", "category", "status", "event_date",
  "amount", "score", "region", "owner", "notes",
];
const statuses = ["Active", "Pending", "Complete", "Needs review"];
const categories = ["Core", "Growth", "Retention", "Operations"];
const regions = ["Central", "North", "South", "East"];

for (let tableIndex = 1; tableIndex <= 100; tableIndex += 1) {
  const sheetName = `Table ${String(tableIndex).padStart(3, "0")}`;
  const sheet = workbook.worksheets.add(sheetName);
  sheet.showGridLines = false;
  sheet.tabColor = tableIndex % 2 ? "#08B5CF" : "#087F91";

  const rows = [tableColumns];
  for (let rowIndex = 1; rowIndex <= 4; rowIndex += 1) {
    rows.push([
      `T${String(tableIndex).padStart(3, "0")}-${String(rowIndex).padStart(3, "0")}`,
      `${categories[(tableIndex + rowIndex) % categories.length]} ${rowIndex}`,
      categories[(tableIndex + rowIndex) % categories.length],
      statuses[(tableIndex + rowIndex) % statuses.length],
      new Date(Date.UTC(2025, (tableIndex + rowIndex) % 12, 1 + rowIndex)),
      1250 * tableIndex + 275 * rowIndex,
      Number((55 + ((tableIndex * 7 + rowIndex * 3) % 45) / 10).toFixed(1)),
      regions[(tableIndex + rowIndex) % regions.length],
      `Owner ${((tableIndex + rowIndex) % 12) + 1}`,
      rowIndex === 4 ? "Longer note for wrapping and profile previews" : "Sample row",
    ]);
  }

  sheet.getRange(`A1:J5`).values = rows;
  sheet.getRange("A1:J5").format.font = bodyFont;
  sheet.getRange("A1:J1").format = { fill: headerFill, font: headerFont };
  sheet.getRange("E2:E5").format.numberFormat = "yyyy-mm-dd";
  sheet.getRange("F2:F5").format.numberFormat = "#,##0.00";
  sheet.getRange("G2:G5").format.numberFormat = "0.0";
  sheet.getRange("A1:J5").format.borders = { preset: "all", style: "thin", color: "#E2E8F0" };
  sheet.getRange("A:J").format.columnWidth = 16;
  sheet.getRange("B:B").format.columnWidth = 22;
  sheet.getRange("J:J").format.columnWidth = 34;
  sheet.freezePanes.freezeRows(1);
  sheet.tables.add("A1:J5", true, `StressTable${String(tableIndex).padStart(3, "0")}`);
}

const wide = workbook.worksheets.add("Wide Table");
wide.showGridLines = false;
wide.tabColor = "#F59E0B";
const wideHeaders = Array.from({ length: 100 }, (_, i) => `field_${String(i + 1).padStart(3, "0")}`);
const wideRows = [wideHeaders];
for (let rowIndex = 1; rowIndex <= 4; rowIndex += 1) {
  wideRows.push(wideHeaders.map((_, colIndex) => {
    if (colIndex === 0) return `WIDE-${String(rowIndex).padStart(3, "0")}`;
    if (colIndex === 1) return rowIndex * 10;
    if (colIndex === 2) return new Date(Date.UTC(2025, rowIndex - 1, rowIndex));
    if (colIndex === 3) return rowIndex % 2 === 0 ? "Ready" : "Review";
    return `value_${rowIndex}_${String(colIndex + 1).padStart(3, "0")}`;
  }));
}
wide.getRange(`A1:${columnName(100)}5`).values = wideRows;
wide.getRange(`A1:${columnName(100)}5`).format.font = bodyFont;
wide.getRange(`A1:${columnName(100)}1`).format = { fill: headerFill, font: headerFont };
wide.getRange("C2:C5").format.numberFormat = "yyyy-mm-dd";
wide.getRange(`A1:${columnName(100)}5`).format.borders = { preset: "all", style: "thin", color: "#E2E8F0" };
wide.getRange(`A:${columnName(100)}`).format.columnWidth = 14;
wide.getRange("A:A").format.columnWidth = 18;
wide.freezePanes.freezeRows(1);
wide.tables.add(`A1:${columnName(100)}5`, true, "WideStressTable");

workbook.recalculate();
const inspect = await workbook.inspect({
  kind: "workbook,sheet,table",
  maxChars: 5000,
  tableMaxRows: 3,
  tableMaxCols: 8,
});
console.log(inspect.ndjson ?? inspect);

for (const [sheetName, fileName, range] of [
  ["Table 001", "table-001-preview.png", "A1:J5"],
  ["Wide Table", "wide-table-preview.png", "A1:K5"],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(`${outputDir}/${fileName}`, new Uint8Array(await preview.arrayBuffer()));
}

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(`${outputDir}/large-workbook-ui-stress-test.xlsx`);
console.log(`created ${outputDir}/large-workbook-ui-stress-test.xlsx`);
