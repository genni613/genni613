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
    opened = sum(p["state"] == "open" for p in items)
    lines = ["## 📊 开源贡献", "",
             "| 提交 PR | 已合并 PR | 贡献仓库 | 待合并 PR |",
             "| :---: | :---: | :---: | :---: |",
             f"| **{len(items)}** | **{len(merged)}** | **{len(counts)}** | **{opened}** |", "",
             f"其中，向其他账号所属仓库贡献了 **{len(external)} 个已合并 PR**。", "",
             "### 🗂️ 贡献仓库排行", "", "| 仓库 | 已合并 PR |", "| :--- | ---: |"]
    for repo, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:15]:
        lines.append(f"| [{repo}](https://github.com/{repo}) | {count} |")
    if not counts:
        lines.append("| 暂无已合并 PR | 0 |")
    lines += ["", "### 🔀 最近合并", ""]
    for p in sorted(merged, key=lambda p: p["pull_request"]["merged_at"], reverse=True)[:5]:
        date = p["pull_request"]["merged_at"][:10]
        lines.append(f"- [{escape(p['title'])}]({p['html_url']}) — `{repository(p)}#{p['number']}` · {date}")
    if not merged:
        lines.append("暂时没有已合并 PR。")
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines += ["", f"<sub>更新于 {today} · 每日自动更新</sub>", "",
              "> 统计口径：本人创建的全部公开 PR；贡献仓库为至少合并过一个本人 PR 的仓库，包含自己的仓库。私有仓库及公司 GitLab 不计入。"]
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
