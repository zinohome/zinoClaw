#!/usr/bin/env node
// Fetch paper details by ID (arXiv ID, DOI, PMID, or Semantic Scholar ID)
// Usage: node fetch_paper.mjs <id_type> <id>
// id_type: arxiv | doi | pmid | s2
// No auth, no VPN required.

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

async function httpsGet(url) {
  for (let i = 0; i < 3; i++) {
    const resp = await httpsGetOnce(url);
    if (resp.status !== 429) return resp;
    const wait = (i + 1) * 10_000;
    process.stderr.write(`Rate limited, retrying in ${wait / 1000}s...\n`);
    await sleep(wait);
  }
  return { status: 429, body: "" };
}

function extractTag(xml, tag) {
  const re = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`, "g");
  const matches = [];
  let m;
  while ((m = re.exec(xml))) matches.push(m[1].trim());
  return matches;
}

async function fetchFromSemanticScholar(paperId) {
  const fields = [
    "paperId", "title", "authors", "year", "venue", "publicationVenue",
    "citationCount", "influentialCitationCount", "isOpenAccess",
    "abstract", "url", "externalIds", "s2FieldsOfStudy",
    "references.paperId", "references.title", "references.authors",
    "references.year", "references.citationCount",
  ].join(",");

  const url = `https://api.semanticscholar.org/graph/v1/paper/${paperId}?fields=${fields}`;
  const { status, body } = await httpsGet(url);

  if (status !== 200) {
    throw new Error(`Semantic Scholar returned ${status} for ${paperId}`);
  }

  const p = JSON.parse(body);
  const authors = (p.authors || []).map((a) => a.name);
  const refs = (p.references || []).slice(0, 20).map((r) => ({
    title: r.title,
    authors: (r.authors || []).slice(0, 3).map((a) => a.name).join(", "),
    year: r.year,
    citations: r.citationCount,
  }));

  return {
    source: "semantic_scholar",
    paper_id: p.paperId,
    title: p.title,
    authors: authors.join("; "),
    year: p.year,
    venue: p.venue || p.publicationVenue?.name || "",
    citation_count: p.citationCount,
    influential_citations: p.influentialCitationCount,
    open_access: p.isOpenAccess,
    abstract: p.abstract || null,
    url: p.url,
    doi: p.externalIds?.DOI || null,
    arxiv_id: p.externalIds?.ArXiv || null,
    pmid: p.externalIds?.PubMed || null,
    fields_of_study: (p.s2FieldsOfStudy || []).map((f) => f.category).join(", "),
    top_references: refs,
  };
}

async function fetchByArxiv(arxivId) {
  return fetchFromSemanticScholar(`ArXiv:${arxivId}`);
}

async function fetchByDoi(doi) {
  return fetchFromSemanticScholar(`DOI:${doi}`);
}

async function fetchByPmid(pmid) {
  return fetchFromSemanticScholar(`PMID:${pmid}`);
}

async function fetchByS2(s2Id) {
  return fetchFromSemanticScholar(s2Id);
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.error("Usage: node fetch_paper.mjs <id_type> <id>");
    console.error("  id_type: arxiv | doi | pmid | s2");
    console.error("Examples:");
    console.error('  node fetch_paper.mjs arxiv "2301.00001"');
    console.error('  node fetch_paper.mjs doi "10.1038/s41586-023-06747-5"');
    console.error('  node fetch_paper.mjs pmid "37258674"');
    console.error('  node fetch_paper.mjs s2 "649def34f8be52c8b66281af98ae884c09aef38b"');
    process.exit(1);
  }

  const idType = args[0].toLowerCase();
  const id = args[1];

  const handlers = {
    arxiv: fetchByArxiv,
    doi: fetchByDoi,
    pmid: fetchByPmid,
    s2: fetchByS2,
  };

  if (!handlers[idType]) {
    console.error(`Unknown id_type: ${idType}. Use: arxiv, doi, pmid, s2`);
    process.exit(1);
  }

  try {
    const result = await handlers[idType](id);
    console.log(JSON.stringify(result, null, 2));
  } catch (err) {
    console.log(JSON.stringify({ error: err.message }));
    process.exit(1);
  }
}

main();
