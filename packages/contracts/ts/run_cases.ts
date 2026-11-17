import { readFileSync } from "node:fs";

import { validateTaskOutput } from "./task_contract.ts";

interface Case {
  id: string;
  group: string;
  raw: string;
  expect: string;
}

interface Fixture {
  max_results: number;
  cases: Case[];
}

const fixtureUrl = new URL("../fixtures/cases.json", import.meta.url);
const fixture: Fixture = JSON.parse(readFileSync(fixtureUrl, "utf8"));

const results = fixture.cases.map((item) => {
  const result = validateTaskOutput(item.raw, fixture.max_results);
  return {
    id: item.id,
    verdict: result.ok ? "PASS" : result.code,
  };
});

console.log(JSON.stringify(results));