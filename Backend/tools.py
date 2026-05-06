import httpx
import os
from typing import Any
from langchain_core.tools import tool

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


# ─── GitHub Tools ──────────────────────────────────────────────────────────────

@tool
async def crawl_github_repo(repo_url: str) -> str:
    """Crawl a GitHub repository and return key info like README, file tree, and stats.
    REQUIRES_APPROVAL: true
    """
    try:
        # Extract owner/repo from URL
        parts = repo_url.rstrip("/").split("/")
        if "github.com" in parts:
            idx = parts.index("github.com")
            owner, repo = parts[idx + 1], parts[idx + 2]
        else:
            return "Invalid GitHub URL format."

        headers = {}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        async with httpx.AsyncClient() as client:
            # Repo metadata
            r = await client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
            print(f"DEBUG: GitHub API response: {r.status_code} {r.text[:200]}") 
            if r.status_code != 200:
                return f"GitHub API error: {r.status_code} - {r.text}"
            data = r.json()

            # README
            readme_r = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/readme",
                headers={**headers, "Accept": "application/vnd.github.raw"},
            )
            readme_text = readme_r.text[:1500] if readme_r.status_code == 200 else "No README found."

            # Top-level file tree
            tree_r = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD",
                headers=headers,
            )
            tree = [item["path"] for item in tree_r.json().get("tree", [])] if tree_r.status_code == 200 else []

        result = f"""
## GitHub Repo: {owner}/{repo}

**Description:** {data.get('description', 'N/A')}
**Stars:** {data.get('stargazers_count', 0)} | **Forks:** {data.get('forks_count', 0)}
**Language:** {data.get('language', 'N/A')}
**Last Updated:** {data.get('updated_at', 'N/A')}
**Open Issues:** {data.get('open_issues_count', 0)}

**Top-level files:**
{chr(10).join(f'- {f}' for f in tree[:20])}

**README (first 1500 chars):**
{readme_text}
"""
        return result
    except Exception as e:
        return f"Error crawling GitHub repo: {str(e)}"


@tool
async def search_github_repos(query: str, max_results: int = 5) -> str:
    """Search GitHub for repositories matching a query.
    REQUIRES_APPROVAL: true
    """
    try:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://api.github.com/search/repositories",
                params={"q": query, "per_page": max_results, "sort": "stars"},
                headers=headers,
            )
            if r.status_code != 200:
                return f"GitHub search error: {r.status_code}"
            items = r.json().get("items", [])

        lines = [f"## GitHub Search: '{query}'\n"]
        for item in items:
            lines.append(
                f"- **[{item['full_name']}]({item['html_url']})** ⭐{item['stargazers_count']} — {item.get('description', 'No description')}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error searching GitHub: {str(e)}"


# ─── LinkedIn Tools ─────────────────────────────────────────────────────────────


@tool
async def crawl_linkedin_profile(profile_url: str) -> str:
    """Crawl a LinkedIn profile using ScrapeGraphAI extractor.
    REQUIRES_APPROVAL: true
    """
    try:
        from scrapegraph_py import AsyncScrapeGraphAI

        api_key = os.getenv("SGAI_API_KEY", "")
        if not api_key:
            api_key = "sgai-84252d56-8f0a-41f4-8cee-6e549cb07cb5"
            # return "Error: SGAI_API_KEY not set in environment variables."

        async with AsyncScrapeGraphAI(api_key=api_key) as sgai:
            res = await sgai.extract(
                """Extract the following from this LinkedIn profile:
                - full_name
                - headline
                - location
                - summary/about section
                - work experiences (title, company, duration)
                - education (degree, school)
                - skills
                Return as structured data.""",
                url=profile_url,
            )

        print(f"DEBUG ScrapeGraphAI status: {res.status}")
        print(f"DEBUG extracted data: {res.data.json_data if res.status == 'success' else res.error}")

        if res.status != "success":
            return f"ScrapeGraphAI error: {res.error}"

        data = res.data.json_data
        if not data:
            return "Could not extract profile. The profile may be private or blocked by LinkedIn."

        # Format nicely whether data comes back as dict or string
        if isinstance(data, dict):
            experiences = "\n".join(
                f"- {e.get('title','N/A')} at {e.get('company','N/A')} ({e.get('duration','')})"
                for e in data.get("experiences", data.get("work_experiences", []))[:5]
            ) or "N/A"

            education = "\n".join(
                f"- {e.get('degree','N/A')} at {e.get('school','N/A')}"
                for e in data.get("education", [])[:3]
            ) or "N/A"

            skills = ", ".join(data.get("skills", [])[:10]) or "N/A"

            return f"""
## LinkedIn Profile: {profile_url}

**Name:** {data.get('full_name', data.get('name', 'N/A'))}
**Headline:** {data.get('headline', 'N/A')}
**Location:** {data.get('location', 'N/A')}
**Summary:** {str(data.get('summary', data.get('about', 'N/A')))[:400]}

**Experience:**
{experiences}

**Education:**
{education}

**Skills:** {skills}
"""
        else:
            # If data came back as plain text/string
            return f"## LinkedIn Profile: {profile_url}\n\n{str(data)}"

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error crawling LinkedIn profile: {str(e)}"



# ─── Registry ──────────────────────────────────────────────────────────────────

TOOLS_REQUIRING_APPROVAL = {
    "crawl_github_repo",
    "search_github_repos",
    "crawl_linkedin_profile",
    "search_linkedin_profiles",
}

ALL_TOOLS = [
    crawl_github_repo,
    search_github_repos,
    crawl_linkedin_profile,
    # search_linkedin_profiles,
]

TOOLS_BY_NAME: dict[str, Any] = {t.name: t for t in ALL_TOOLS}
