#!/usr/bin/env node
// Semantic Scholar API search — no auth, no VPN required
// Usage: node search_semantic.mjs <query> [max_results]
// API docs: https://api.semanticscholar.org/api-docs/

import https from "node:https";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function httpsGetOnce(url) {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { "User-Agent": "OpenClaw-ResearchProposal/1.0" } }, (res) => {
      let data = "";
      res.on("data", (c) => (data += c));
      res.on("end", () => resolve({ status: res.statusCode, body: data }));
      res.on("error", reject);
    }).on("error", reject);
  });
}

async function httpsGet(url, retries = 3) {
  for (let i = 0; i < retries; i++) {
    const resp = await httpsGetOnce(url);
    if (resp.status !== 429) return resp;
    const wait = (i + 1) * 10_000;
    process.stderr.write(`Rate limited, retrying in ${wait / 1000}s...\n`);
    await sleep(wait);
  }
  return { status: 429, body: '{"error":"Rate limited after retries. Try again later."}' };
}

function formatPaper(p) {
  const authors = (p.authors || [])
    .slice(0, 5)
    .map((a) => a.name)
    .join("; ");
  const authorSuffix = (p.authors || []).length > 5 ? ` et al. (${p.authors.length} authors)` : "";

  return {
    paper_id: p.paperId || "",
    title: p.title || "",
    authors: authors + authorSuffix,
    year: p.year || null,
    venue: p.venue || p.publicationVenue?.name || "",
    citation_count: p.citationCount ?? null,
    influential_citation_count: p.influentialCitationCount ?? null,
    open_access: p.isOpenAccess || false,
    abstract: p.abstract
      ? p.abstract.length > 500
        ? p.abstract.slice(0, 500) + "..."
        : p.abstract
      : null,
    url: p.url || (p.paperId ? `https://www.semanticscholar.org/paper/${p.paperId}` : ""),
    doi: p.externalIds?.DOI || null,
    arxiv_id: p.externalIds?.ArXiv || null,
    fields_of_study: (p.s2FieldsOfStudy || []).slice(0, 5).map((f) => f.category).join(", "),
  };
}

async function searchSemantic(query, maxResults = 10) {
  const limit = Math.min(maxResults, 30);
  const fields = [
    "paperId", "title", "authors", "year", "venue", "publicationVenue",
    "citationCount", "influentialCitationCount", "isOpenAccess",
    "abstract", "url", "externalIds", "s2FieldsOfStudy",
  ].join(",");

  const params = new URLSearchParams({
    query,
    limit: String(limit),
    fields,
  });

  const url = `https://api.semanticscholar.org/graph/v1/paper/search?${params}`;
  const { status, body } = await httpsGet(url);

  if (status !== 200) {
    let errMsg;
    try {
      errMsg = JSON.parse(body).error || JSON.parse(body).message || `Status ${status}`;
    } catch {
      errMsg = `Semantic Scholar API returned status ${status}`;
    }
    return { error: errMsg, source: "semantic_scholar", results: [] };
  }

  const data = JSON.parse(body);
  const papers = (data.data || []).map(formatPaper);

  return {
    source: "semantic_scholar",
    query,
    total_results: data.total || papers.length,
    returned: papers.length,
    results: papers,
  };
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error("Usage: node search_semantic.mjs <query> [max_results]");
    console.error('Example: node search_semantic.mjs "transformer attention mechanism" 10');
    process.exit(1);
  }

  const query = args[0];
  const maxResults = parseInt(args[1]) || 10;

  try {
    const result = await searchSemantic(query, maxResults);
    console.log(JSON.stringify(result, null, 2));
  } catch (err) {
    console.log(JSON.stringify({ error: err.message, source: "semantic_scholar" }));
    process.exit(1);
  }
}

main();
