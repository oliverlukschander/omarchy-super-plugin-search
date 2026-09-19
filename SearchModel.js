function parseRows(raw) {
  try {
    var data = JSON.parse(String(raw || "[]"))
    return Array.isArray(data) ? data : []
  } catch (e) {
    return []
  }
}

function parseStatus(raw) {
  try {
    var data = JSON.parse(String(raw || "{}"))
    return data && typeof data === "object" ? data : {}
  } catch (e) {
    return {}
  }
}

if (typeof module !== "undefined") {
  module.exports = {
    parseRows: parseRows,
    parseStatus: parseStatus
  }
}
