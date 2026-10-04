// Optional: mongosh mongodb://127.0.0.1:27017/signal_desk mongodb/verify_schema.js
const limit = 16 * 1024 * 1024;
for (const name of ["sources", "reports", "indicators", "observations", "reports_embedded", "working_set"]) {
  print(name);
  printjson(db.getCollection(name).aggregate([
    {$project: {bytes: {$bsonSize: "$$ROOT"}}},
    {$group: {_id: null, count: {$sum: 1}, averageBytes: {$avg: "$bytes"},
      maximumBytes: {$max: "$bytes"}, nearLimitCount: {$sum: {$cond: [{$gte: ["$bytes", limit * 0.8]}, 1, 0]}}}}
  ]).toArray());
}
