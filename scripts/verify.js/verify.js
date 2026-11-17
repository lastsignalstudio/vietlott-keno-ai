
const fs = require("fs");
const path = require("path");

const file = path.join(
  __dirname,
  "../data/official-confirmed.json"
);

const data = JSON.parse(
  fs.readFileSync(file, "utf8")
);

const seen = new Set();

for (const draw of data.draws) {
  const id = String(draw.draw_id);

  if (!/^\d{7}$/.test(id)) {
    throw new Error("Mã kỳ không hợp lệ: " + id);
  }

  if (!Array.isArray(draw.numbers) ||
      draw.numbers.length !== 20) {
    throw new Error("Kỳ " + id + " không đủ 20 số");
  }

  if (new Set(draw.numbers).size !== 20) {
    throw new Error("Kỳ " + id + " có số trùng");
  }

  if (!draw.numbers.every(
    n => Number.isInteger(n) && n >= 1 && n <= 80
  )) {
    throw new Error("Kỳ " + id + " có số ngoài phạm vi");
  }

  if (seen.has(id)) {
    throw new Error("Trùng mã kỳ: " + id);
  }

  seen.add(id);
}

console.log("KENО DATA VALIDATION: PASS");
console.log("Tổng số kỳ:", seen.size);
console.log("Mã kỳ mới nhất:",
  [...seen].sort().at(-1)
);
console.log("Nguồn:", data.verification_status);
