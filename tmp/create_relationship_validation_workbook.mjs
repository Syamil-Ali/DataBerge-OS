import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = "C:/Users/hasmi/Desktop/Data-Berge-OS/outputs/messy-workbook-relationship-validation";
const workbook = Workbook.create();

const scenarios = [
  {
    sheetName: "Valid Customers",
    tableName: "ValidCustomersTable",
    values: [
      ["customer_id", "customer_name", "segment"],
      [1, "Aisyah Rahman", "SME"],
      [2, "Daniel Lim", "Enterprise"],
      [3, "Mei Chen", "SME"],
    ],
  },
  {
    sheetName: "Valid Orders",
    tableName: "ValidOrdersTable",
    values: [
      ["order_id", "customer_id", "order_value"],
      ["ORD-001", "1.0", 1200],
      ["ORD-002", "2.0", 850],
      ["ORD-003", "3.0", 2100],
      ["ORD-004", null, 400],
      ["ORD-005", "1.0", 600],
    ],
  },
  {
    sheetName: "Broken Customers",
    tableName: "BrokenCustomersTable",
    values: [
      ["broken_customer_id (PK)", "customer_name"],
      [1, "Aisyah Rahman"],
      [2, "Daniel Lim"],
    ],
  },
  {
    sheetName: "Broken Orders",
    tableName: "BrokenOrdersTable",
    values: [
      ["order_id", "broken_customer_id (FK)", "order_value"],
      ["BAD-001", 98, 400],
      ["BAD-002", 99, 750],
    ],
  },
  {
    sheetName: "Status Customers",
    tableName: "StatusCustomersTable",
    values: [
      ["customer_code", "status"],
      ["CUS-01", "active"],
      ["CUS-02", "inactive"],
    ],
  },
  {
    sheetName: "Status Orders",
    tableName: "StatusOrdersTable",
    values: [
      ["order_code", "status"],
      ["SO-01", "active"],
      ["SO-02", "inactive"],
      ["SO-03", "active"],
    ],
  },
];

for (const scenario of scenarios) {
  const sheet = workbook.worksheets.add(scenario.sheetName);
  sheet.showGridLines = false;
  const rowCount = scenario.values.length;
  const columnCount = scenario.values[0].length;
  const lastColumn = String.fromCharCode(64 + columnCount);
  const range = sheet.getRange(`A1:${lastColumn}${rowCount}`);
  range.values = scenario.values;
  range.format.font = { name: "Arial", size: 10, color: "#172033" };
  sheet.getRange(`A1:${lastColumn}1`).format = {
    fill: "#172033",
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  sheet.getRange(`A1:${lastColumn}${rowCount}`).format.borders = {
    preset: "outside",
    style: "thin",
    color: "#E2E8F0",
  };
  sheet.getRange(`A1:${lastColumn}${rowCount}`).format.autofitColumns();
  sheet.getRange(`A1:${lastColumn}${rowCount}`).format.autofitRows();
  sheet.freezePanes.freezeRows(1);
  sheet.tables.add(`A1:${lastColumn}${rowCount}`, true, scenario.tableName);
}

workbook.recalculate();

const inspection = await workbook.inspect({
  kind: "workbook,sheet,table",
  maxChars: 6000,
  tableMaxRows: 6,
  tableMaxCols: 4,
});
console.log(inspection.ndjson);

await fs.mkdir(outputDir, { recursive: true });
for (const scenario of scenarios) {
  const preview = await workbook.render({
    sheetName: scenario.sheetName,
    autoCrop: "all",
    scale: 1,
    format: "png",
  });
  const previewName = scenario.sheetName.toLowerCase().replaceAll(" ", "-");
  await fs.writeFile(`${outputDir}/${previewName}.png`, new Uint8Array(await preview.arrayBuffer()));
}
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(`${outputDir}/relationship-inference-validation.xlsx`);
