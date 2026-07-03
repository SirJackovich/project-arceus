import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const inputDir = process.argv[2] || "data/analysis";
const outputDir = process.argv[3] || "data/analysis";
const workbookPath = path.join(outputDir, "monkey_deck_analysis.xlsx");

async function parseCsv(filePath) {
  const text = await fs.readFile(filePath, "utf8");
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    const next = text[i + 1];
    if (inQuotes) {
      if (ch === '"' && next === '"') {
        field += '"';
        i += 1;
      } else if (ch === '"') {
        inQuotes = false;
      } else {
        field += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      row.push(field);
      field = "";
    } else if (ch === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else if (ch !== "\r") {
      field += ch;
    }
  }
  if (field.length || row.length) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

function coerce(value) {
  if (value === "") return null;
  if (/^-?\d+(?:\.\d+)?$/.test(value)) return Number(value);
  return value;
}

function writeSheet(workbook, name, rows, options = {}) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  const matrix = rows.map((row) => row.map(coerce));
  if (matrix.length) {
    sheet.getRangeByIndexes(0, 0, matrix.length, matrix[0].length).values = matrix;
    const header = sheet.getRangeByIndexes(0, 0, 1, matrix[0].length);
    header.format.fill.color = "#1F4E5F";
    header.format.font.color = "#FFFFFF";
    header.format.font.bold = true;
    header.format.rowHeightPx = 24;
    sheet.freezePanes.freezeRows(1);
    const used = sheet.getRangeByIndexes(0, 0, matrix.length, matrix[0].length);
    used.format.font.name = "Aptos";
    used.format.font.size = 10;
    used.format.autofitColumns();
    if (options.wrapLastColumns) {
      const start = Math.max(0, matrix[0].length - options.wrapLastColumns);
      sheet.getRangeByIndexes(0, start, matrix.length, options.wrapLastColumns).format.wrapText = true;
      sheet.getRangeByIndexes(0, start, matrix.length, options.wrapLastColumns).format.columnWidthPx = 240;
    }
  }
  return sheet;
}

function pct(n) {
  return `${Math.round(n * 1000) / 10}%`;
}

const summary = JSON.parse(await fs.readFile(path.join(inputDir, "summary.json"), "utf8"));
const games = await parseCsv(path.join(inputDir, "games.csv"));
const cards = await parseCsv(path.join(inputDir, "card_usage.csv"));
const opening = await parseCsv(path.join(inputDir, "opening_hands.csv"));
const events = await parseCsv(path.join(inputDir, "raw_events.csv"));
const attacks = await parseCsv(path.join(inputDir, "attack_usage.csv"));
const goingFirst = await parseCsv(path.join(inputDir, "going_first_summary.csv"));
const effectiveness = await parseCsv(path.join(inputDir, "card_effectiveness.csv"));
const successConditions = await parseCsv(path.join(inputDir, "success_condition_summary.csv"));
const successGroups = await parseCsv(path.join(inputDir, "success_group_summary.csv"));
const successDetails = await parseCsv(path.join(inputDir, "success_condition_details.csv"));

const cardHeader = cards[0];
const cardRows = cards.slice(1);
const idx = Object.fromEntries(cardHeader.map((h, i) => [h, i]));
const topByUse = [...cardRows]
  .sort((a, b) => Number(b[idx.played_or_used_count] || 0) - Number(a[idx.played_or_used_count] || 0))
  .slice(0, 10);
const topByWin = cardRows
  .filter((r) => Number(r[idx.games_used] || 0) >= 5)
  .sort((a, b) => Number(b[idx.win_rate_when_used] || 0) - Number(a[idx.win_rate_when_used] || 0))
  .slice(0, 10);
const lowByWin = cardRows
  .filter((r) => Number(r[idx.games_used] || 0) >= 5)
  .sort((a, b) => Number(a[idx.win_rate_when_used] || 0) - Number(b[idx.win_rate_when_used] || 0))
  .slice(0, 10);
const attackHeader = attacks[0];
const attackRows = attacks.slice(1);
const attackIdx = Object.fromEntries(attackHeader.map((h, i) => [h, i]));
const topAttacks = [...attackRows]
  .sort((a, b) => Number(b[attackIdx.uses] || 0) - Number(a[attackIdx.uses] || 0))
  .slice(0, 8);
const effectHeader = effectiveness[0];
const effectRows = effectiveness.slice(1);
const effectIdx = Object.fromEntries(effectHeader.map((h, i) => [h, i]));
const topEffect = [...effectRows]
  .sort((a, b) => Number(b[effectIdx.observable_score] || 0) - Number(a[effectIdx.observable_score] || 0))
  .slice(0, 8);
const watchList = effectRows
  .filter((r) => r[effectIdx.signal] === "watch")
  .sort((a, b) => Number(a[effectIdx.win_rate_delta_vs_deck] || 0) - Number(b[effectIdx.win_rate_delta_vs_deck] || 0))
  .slice(0, 8);
const goingHeader = goingFirst[0];
const goingRows = goingFirst.slice(1);
const goingIdx = Object.fromEntries(goingHeader.map((h, i) => [h, i]));
const successHeader = successConditions[0];
const successRows = successConditions.slice(1);
const successIdx = Object.fromEntries(successHeader.map((h, i) => [h, i]));
const successGroupHeader = successGroups[0];
const successGroupRows = successGroups.slice(1);
const successGroupIdx = Object.fromEntries(successGroupHeader.map((h, i) => [h, i]));
const weakestGoals = [...successRows]
  .sort((a, b) => Number(a[successIdx.met_rate_all] || 0) - Number(b[successIdx.met_rate_all] || 0))
  .slice(0, 6);

const completeGames = summary.games_with_complete_log;
const wins = summary.wins;
const losses = summary.losses;
const dashboardRows = [
  ["Monkey Deck Log Analysis", "", "", "", "", ""],
  ["Generated from local Pokemon TCG Live log files", "", "", "", "", ""],
  ["Metric", "Value", "", "Second-pass notes", "", ""],
  ["Files seen", summary.files_seen, "", "Attack Usage", "Damage attacks are grouped by card and attack name.", ""],
  ["Complete logs", completeGames, "", "Going First", "Your win rate is split by opening order.", ""],
  ["Partial/notes-only logs", summary.games_partial, "", "Card Effectiveness", "Role-aware scoring now separates observable value from raw usage.", ""],
  ["Record", `${wins}-${losses}`, "", "Conservative attribution", "KO/prize credit is only assigned when the source card and action are visible.", ""],
  ["Win rate", completeGames ? pct(wins / completeGames) : "", "", "Limitation", "Hidden cards, missed lines, and subjective misplays still need human review.", ""],
  ["Raw events parsed", summary.raw_events, "", "", "", ""],
  ["Cards summarized", summary.cards_summarized, "", "", "", ""],
  ["Attacks summarized", summary.attacks_summarized, "", "", "", ""],
  ["Success-condition checks", summary.success_condition_checks || "", "", "", "", ""],
  ["", "", "", "", "", ""],
  ["Success groups", "Checks", "Met", "Missed", "Unknown", "Met Rate"],
  ...successGroupRows.map((r) => [
    r[successGroupIdx.goal_group],
    coerce(r[successGroupIdx.checks]),
    coerce(r[successGroupIdx.met]),
    coerce(r[successGroupIdx.missed]),
    coerce(r[successGroupIdx.unknown]),
    r[successGroupIdx.met_rate_all] === "" ? "" : Number(r[successGroupIdx.met_rate_all]),
  ]),
  ["", "", "", "", "", ""],
  ["Weakest success conditions", "Group", "Met", "Missed", "Unknown", "Met Rate"],
  ...weakestGoals.map((r) => [
    r[successIdx.condition],
    r[successIdx.goal_group],
    coerce(r[successIdx.met]),
    coerce(r[successIdx.missed]),
    coerce(r[successIdx.unknown]),
    r[successIdx.met_rate_all] === "" ? "" : Number(r[successIdx.met_rate_all]),
  ]),
  ["", "", "", "", "", ""],
  ["Going first/second", "Games", "Wins", "Losses", "Win Rate", "Avg Total Turns"],
  ...goingRows.map((r) => [
    r[goingIdx.bucket],
    coerce(r[goingIdx.games]),
    coerce(r[goingIdx.wins]),
    coerce(r[goingIdx.losses]),
    r[goingIdx.win_rate] === "" ? "" : Number(r[goingIdx.win_rate]),
    coerce(r[goingIdx.avg_total_turns]),
  ]),
  ["", "", "", "", "", ""],
  ["Top observable effectiveness", "Role", "Games", "Uses", "Score", "Signal"],
  ...topEffect.map((r) => [
    r[effectIdx.card_name],
    r[effectIdx.role],
    coerce(r[effectIdx.games_used]),
    coerce(r[effectIdx.uses]),
    coerce(r[effectIdx.observable_score]),
    r[effectIdx.signal],
  ]),
  ["", "", "", "", "", ""],
  ["Watch list", "Role", "Games", "Uses", "Win Delta", "Signal"],
  ...watchList.map((r) => [
    r[effectIdx.card_name],
    r[effectIdx.role],
    coerce(r[effectIdx.games_used]),
    coerce(r[effectIdx.uses]),
    r[effectIdx.win_rate_delta_vs_deck] === "" ? "" : Number(r[effectIdx.win_rate_delta_vs_deck]),
    r[effectIdx.signal],
  ]),
  ["", "", "", "", "", ""],
  ["Attack usage", "Attack", "Uses", "Games", "Avg Damage", "Win Rate"],
  ...topAttacks.map((r) => [
    r[attackIdx.card_name],
    r[attackIdx.attack_name],
    coerce(r[attackIdx.uses]),
    coerce(r[attackIdx.games_used]),
    coerce(r[attackIdx.avg_damage]),
    r[attackIdx.win_rate_when_used] === "" ? "" : Number(r[attackIdx.win_rate_when_used]),
  ]),
  ["", "", "", "", "", ""],
  ["Most used cards", "Games", "Uses", "Win Rate", "Value Events", "Avg First Turn"],
  ...topByUse.map((r) => [
    r[idx.card_name],
    coerce(r[idx.games_used]),
    coerce(r[idx.played_or_used_count]),
    r[idx.win_rate_when_used] === "" ? "" : Number(r[idx.win_rate_when_used]),
    coerce(r[idx.direct_value_events_attributed]),
    coerce(r[idx.avg_first_usage_turn]),
  ]),
  ["", "", "", "", "", ""],
  ["Best win rate, min 5 games", "Games", "Uses", "Win Rate", "Value Events", "Avg First Turn"],
  ...topByWin.map((r) => [
    r[idx.card_name],
    coerce(r[idx.games_used]),
    coerce(r[idx.played_or_used_count]),
    r[idx.win_rate_when_used] === "" ? "" : Number(r[idx.win_rate_when_used]),
    coerce(r[idx.direct_value_events_attributed]),
    coerce(r[idx.avg_first_usage_turn]),
  ]),
  ["", "", "", "", "", ""],
  ["Lowest win rate, min 5 games", "Games", "Uses", "Win Rate", "Value Events", "Avg First Turn"],
  ...lowByWin.map((r) => [
    r[idx.card_name],
    coerce(r[idx.games_used]),
    coerce(r[idx.played_or_used_count]),
    r[idx.win_rate_when_used] === "" ? "" : Number(r[idx.win_rate_when_used]),
    coerce(r[idx.direct_value_events_attributed]),
    coerce(r[idx.avg_first_usage_turn]),
  ]),
];

await fs.mkdir(outputDir, { recursive: true });
const workbook = Workbook.create();
const dashboard = writeSheet(workbook, "Dashboard", dashboardRows);
dashboard.getRange("A1:F1").merge();
dashboard.getRange("A2:F2").merge();
dashboard.getRange("A1").format.font.size = 18;
dashboard.getRange("A1").format.font.bold = true;
dashboard.getRange("A1").format.font.color = "#FFFFFF";
dashboard.getRange("A2").format.font.color = "#666666";
for (let i = 0; i < dashboardRows.length; i += 1) {
  const row = dashboardRows[i];
  const isSection = row[0] && row.slice(1).some((cell) => cell !== "") && [
    "Metric",
    "Going first/second",
    "Top observable effectiveness",
    "Watch list",
    "Attack usage",
    "Success groups",
    "Weakest success conditions",
    "Most used cards",
    "Best win rate, min 5 games",
    "Lowest win rate, min 5 games",
  ].includes(row[0]);
  if (isSection) {
    const range = dashboard.getRangeByIndexes(i, 0, 1, 6);
    range.format.fill.color = "#DDEBF0";
    range.format.font.bold = true;
  }
}
function sectionRow(label) {
  return dashboardRows.findIndex((row) => row[0] === label);
}
function formatColumnFromSection(label, colIndex, rowCount, numberFormat) {
  const start = sectionRow(label) + 1;
  if (start > 0 && rowCount > 0) {
    dashboard.getRangeByIndexes(start, colIndex, rowCount, 1).format.numberFormat =
      Array.from({ length: rowCount }, () => [numberFormat]);
  }
}
formatColumnFromSection("Going first/second", 4, goingRows.length, "0.0%");
formatColumnFromSection("Success groups", 5, successGroupRows.length, "0.0%");
formatColumnFromSection("Weakest success conditions", 5, weakestGoals.length, "0.0%");
formatColumnFromSection("Watch list", 4, watchList.length, "0.0%");
formatColumnFromSection("Attack usage", 5, topAttacks.length, "0.0%");
formatColumnFromSection("Most used cards", 3, topByUse.length, "0.0%");
formatColumnFromSection("Best win rate, min 5 games", 3, topByWin.length, "0.0%");
formatColumnFromSection("Lowest win rate, min 5 games", 3, lowByWin.length, "0.0%");
dashboard.getRange("D3:F10").format.wrapText = true;
dashboard.getRange("D3:F10").format.columnWidthPx = 220;
dashboard.getRange("A:F").format.font.name = "Aptos";
dashboard.getRange("A:A").format.columnWidthPx = 230;
dashboard.getRange("B:B").format.columnWidthPx = 110;
dashboard.getRange("C:C").format.columnWidthPx = 68;
dashboard.getRange("D:D").format.columnWidthPx = 140;
dashboard.getRange("E:E").format.columnWidthPx = 220;
dashboard.getRange("F:F").format.columnWidthPx = 130;

writeSheet(workbook, "Games", games, { wrapLastColumns: 1 });
writeSheet(workbook, "Success Summary", successConditions, { wrapLastColumns: 1 });
writeSheet(workbook, "Success Groups", successGroups);
writeSheet(workbook, "Success Details", successDetails, { wrapLastColumns: 2 });
writeSheet(workbook, "Going First", goingFirst);
writeSheet(workbook, "Card Effectiveness", effectiveness);
writeSheet(workbook, "Attack Usage", attacks);
writeSheet(workbook, "Card Usage", cards);
writeSheet(workbook, "Opening Hands", opening);
writeSheet(workbook, "Raw Events", events, { wrapLastColumns: 2 });

const inspect = await workbook.inspect({
  kind: "sheet,table",
  maxChars: 5000,
  tableMaxRows: 8,
  tableMaxCols: 8,
});
console.log(inspect.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

const preview = await workbook.render({ sheetName: "Dashboard", autoCrop: "all", scale: 1, format: "png" });
const previewBytes = new Uint8Array(await preview.arrayBuffer());
await fs.writeFile(path.join(outputDir, "dashboard_preview.png"), previewBytes);

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(workbookPath);
console.log(JSON.stringify({ workbookPath: path.resolve(workbookPath) }, null, 2));
