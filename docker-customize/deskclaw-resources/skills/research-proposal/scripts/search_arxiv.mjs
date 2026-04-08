#!/usr/bin/env node
// arXiv API search — no auth, no VPN required
// Usage: node search_arxiv.mjs <query> [max_results]
// API docs: https://info.arxiv.org/help/api/basics.html

import https from "node:https";
import { parseArgs } from "node:util";

function httpsGet(url) {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { "User-Agent": "OpenClaw-ResearchProposal/1.0" } }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return httpsGet(res.headers.location).then(resolve, reject);
      }
      let data = "";
      res.on("data", (c) => (data += c));
      res.on("end", () => resolve({ status: res.statusCode, body: data }));
      res.on("error", reject);
    }).on("error", reject);
  });
}

function extractTag(xml, tag) {
  const re = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`, "g");
  const matches = [];
  let m;
  while ((m = re.exec(xml))) matches.push(m[1].trim());
  return matches;
}

function extractAttr(xml, tag, attr) {
  const re = new RegExp(`<${tag}[^>]*${attr}="([^"]*)"`, "g");
  const matches = [];
  let m;
  while ((m = re.exec(xml))) matches.push(m[1]);
  return matches;
}

function parseEntry(entryXml) {
  const id = extractTag(entryXml, "id")[0] || "";
  const title = (extractTag(entryXml, "title")[0] || "").replace(/\s+/g, " ");
  const summary = (extractTag(entryXml, "summary")[0] || "").replace(/\s+/g, " ");
  const published = extractTag(entryXml, "published")[0] || "";
  const updated = extractTag(entryXml, "updated")[0] || "";

  const authorBlocks = extractTag(entryXml, "author");
  const authors = authorBlocks.map((a) => extractTag(a, "name")[0] || "").filter(Boolean);

  const categories = extractAttr(entryXml, "category", "term");

  const pdfLink = entryXml.match(/<link[^>]*title="pdf"[^>]*href="([^"]*)"/);
  const pdf = pdfLink ? pdfLink[1] : "";

  return {
    arxiv_id: id.replace("http://arxiv.org/abs/", "").replace(/v\d+$/, ""),
    title,
    authors: authors.slice(0, 5).join(", ") + (authors.length > 5 ? ` et al. (${authors.length} authors)` : ""),
    year: published.slice(0, 4),
    published: published.slice(0, 10),
    updated: updated.slice(0, 10),
    categories: categories.slice(0, 5).join(", "),
    abstract: summary.length > 500 ? summary.slice(0, 500) + "..." : summary,
    url: id,
    pdf,
  };
}

async function searchArxiv(query, maxResults = 10) {
  const params = new URLSearchParams({
    search_query: `all:${query}`,
    start: "0",
    max_results: String(Math.min(maxResults, 30)),
    sortBy: "relevance",
    sortOrder: "descending",
  });

  const url = `https://export.arxiv.org/api/query?${params}`;
  const { status, body } = await httpsGet(url);

  if (status !== 200) {
    return { error: `arXiv API returned status ${status}`, results: [] };
  }

  const totalStr = body.match(/<opensearch:totalResults[^>]*>(\d+)/);
  const total = totalStr ? parseInt(totalStr[1]) : 0;

  const entries = [];
  const entryRegex = /<entry>([\s\S]*?)<\/entry>/g;
  let match;
  while ((match = entryRegex.exec(body))) {
    entries.push(parseEntry(match[1]));
  }

  return {
    source: "arxiv",
    query,
    total_results: total,
    returned: entries.length,
    results: entries,
  };
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error("Usage: node search_arxiv.mjs <query> [max_results]");
    console.error('Example: node search_arxiv.mjs "federated learning privacy" 10');
    process.exit(1);
  }

  const query = args[0];
  const maxResults = parseInt(args[1]) || 10;

  try {
    const result = await searchArxiv(query, maxResults);
    console.log(JSON.stringify(result, null, 2));
  } catch (err) {
    console.log(JSON.stringify({ error: err.message, source: "arxiv" }));
    process.exit(1);
  }
}

main();
