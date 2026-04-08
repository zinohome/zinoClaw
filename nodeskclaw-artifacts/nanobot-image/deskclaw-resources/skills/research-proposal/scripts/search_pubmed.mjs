#!/usr/bin/env node
// PubMed E-utilities search — no auth, no VPN required
// Usage: node search_pubmed.mjs <query> [max_results]
// API docs: https://www.ncbi.nlm.nih.gov/books/NBK25500/

import https from "node:https";

function httpsGet(url) {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { "User-Agent": "OpenClaw-ResearchProposal/1.0" } }, (res) => {
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

async function searchIds(query, maxResults) {
  const params = new URLSearchParams({
    db: "pubmed",
    term: query,
    retmax: String(Math.min(maxResults, 30)),
    retmode: "json",
    sort: "relevance",
  });
  const url = `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?${params}`;
  const { status, body } = await httpsGet(url);
  if (status !== 200) throw new Error(`ESearch returned ${status}`);

  const data = JSON.parse(body);
  return {
    ids: data.esearchresult?.idlist || [],
    total: parseInt(data.esearchresult?.count || "0"),
  };
}

function parseArticle(articleXml) {
  const pmid = extractTag(articleXml, "PMID")[0] || "";
  const title = (extractTag(articleXml, "ArticleTitle")[0] || "").replace(/<[^>]*>/g, "");
  const abstractTexts = extractTag(articleXml, "AbstractText");
  const abstract = abstractTexts.map((t) => t.replace(/<[^>]*>/g, "")).join(" ");

  const lastNames = extractTag(articleXml, "LastName");
  const foreNames = extractTag(articleXml, "ForeName");
  const authors = lastNames.map((ln, i) => `${ln}, ${foreNames[i] || ""}`.trim());

  const journal = extractTag(articleXml, "Title")[0] || "";
  const year = extractTag(articleXml, "Year")[0] || "";
  const volume = extractTag(articleXml, "Volume")[0] || "";
  const issue = extractTag(articleXml, "Issue")[0] || "";
  const pages = extractTag(articleXml, "MedlinePgn")[0] || "";

  const doiMatch = articleXml.match(/<ArticleId IdType="doi">([^<]+)/);
  const doi = doiMatch ? doiMatch[1] : "";

  const meshTerms = extractTag(articleXml, "DescriptorName").slice(0, 8);

  return {
    pmid,
    title,
    authors: authors.slice(0, 5).join("; ") + (authors.length > 5 ? ` et al. (${authors.length} authors)` : ""),
    year,
    journal,
    volume,
    issue,
    pages,
    doi,
    url: `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`,
    mesh_terms: meshTerms.join("; "),
    abstract: abstract.length > 500 ? abstract.slice(0, 500) + "..." : abstract,
  };
}

async function fetchDetails(ids) {
  if (ids.length === 0) return [];

  const params = new URLSearchParams({
    db: "pubmed",
    id: ids.join(","),
    retmode: "xml",
  });
  const url = `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?${params}`;
  const { status, body } = await httpsGet(url);
  if (status !== 200) throw new Error(`EFetch returned ${status}`);

  const articles = [];
  const re = /<PubmedArticle>([\s\S]*?)<\/PubmedArticle>/g;
  let m;
  while ((m = re.exec(body))) {
    articles.push(parseArticle(m[1]));
  }
  return articles;
}

async function searchPubmed(query, maxResults = 10) {
  const { ids, total } = await searchIds(query, maxResults);

  if (ids.length === 0) {
    return { source: "pubmed", query, total_results: total, returned: 0, results: [] };
  }

  const articles = await fetchDetails(ids);

  return {
    source: "pubmed",
    query,
    total_results: total,
    returned: articles.length,
    results: articles,
  };
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error("Usage: node search_pubmed.mjs <query> [max_results]");
    console.error('Example: node search_pubmed.mjs "CRISPR gene therapy" 10');
    process.exit(1);
  }

  const query = args[0];
  const maxResults = parseInt(args[1]) || 10;

  try {
    const result = await searchPubmed(query, maxResults);
    console.log(JSON.stringify(result, null, 2));
  } catch (err) {
    console.log(JSON.stringify({ error: err.message, source: "pubmed" }));
    process.exit(1);
  }
}

main();
