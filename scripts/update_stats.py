"""Update the profile from public GitHub PRs. Python standard library only."""
import collections
import datetime
import html
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request


def collect(user):
    items = []
    for page in range(1, 11):
        params = urllib.parse.urlencode({
            "q": f"author:{user} is:pr is:public", "per_page": 100,
            "page": page, "sort": "created", "order": "desc",
        })
        request = urllib.request.Request(
            "https://api.github.com/search/issues?" + params,
            headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"],
                     "Accept": "application/vnd.github+json",
                     "User-Agent": "profile-contribution-stats"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.load(response)
        if data.get("incomplete_results") or data["total_count"] > 1000:
            raise RuntimeError("Search is incomplete or exceeds 1000 PRs; keep previous README.")
        items.extend(data["items"])
        if len(items) >= data["total_count"]:
            break
    unique = {item["id"]: item for item in items}
    if len(unique) != data["total_count"]:
        raise RuntimeError("Search changed during pagination; retry instead of publishing partial data.")
    return list(unique.values())


def repository(item):
    return item["repository_url"].split("/repos/", 1)[1]


def escape(text):
    text = html.escape(text).replace("\n", " ")
    for char in "\\`*_[ ]|".replace(" ", ""):
        text = text.replace(char, "\\" + char)
    return text


def render(items, user):
    merged = [p for p in items if p["pull_request"].get("merged_at")]
    counts = collections.Counter(repository(p) for p in merged)
    external = [p for p in merged if repository(p).split("/")[0].lower() != user.lower()]
    # Only publish reviewed English summaries; new PRs still update aggregate stats.
    summaries = json.loads(Path(__file__).with_name("pr_summaries.json").read_text())
    highlights = [p for p in external if f"{repository(p)}#{p['number']}" in summaries]
    lines = ["### Open Source Highlights", ""]
    for p in sorted(highlights, key=lambda p: p["pull_request"]["merged_at"], reverse=True)[:5]:
        label = f"{repository(p)} #{p['number']}"
        summary = summaries[f"{repository(p)}#{p['number']}"]
        lines.append(f"- **[{label}]({p['html_url']})** — {escape(summary)}")
    if not highlights:
        lines.append("Selected contributions will appear here once their summaries are added.")
    lines += ["", "<details>",
              f"<summary><b>Merged PRs — {len(merged)} across {len(counts)} repositories</b></summary>", ""]
    query = urllib.parse.urlencode({"q": f"is:pr author:{user} is:merged"})
    for repo, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])):
        unit = "PR" if count == 1 else "PRs"
        lines.append(f"- [{repo}](https://github.com/{repo}/pulls?{query}) — {count} {unit}")
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    lines += ["", f"<sub>Public PRs · Includes own repositories · Updated {today}</sub>",
              "", "</details>"]
    return "\n".join(lines)


if __name__ == "__main__":
    user = os.environ.get("PROFILE_USER", "genni613")
    path = Path(__file__).resolve().parents[1] / "README.md"
    content = path.read_text()
    start, end = "<!-- contribution-stats:start -->", "<!-- contribution-stats:end -->"
    if content.count(start) != 1 or content.count(end) != 1 or content.index(start) > content.index(end):
        raise RuntimeError("README must contain one ordered pair of stats markers.")
    stats = render(collect(user), user)
    path.write_text(content.split(start)[0] + start + "\n" + stats + "\n" + end + content.split(end)[1])
    print(stats)
