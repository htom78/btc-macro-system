#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import html.parser
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


IGNORED_SCHEMES = {"mailto", "tel", "javascript", "data", "blob"}
LINK_ATTRS = {
    "a": ("href",),
    "area": ("href",),
    "link": ("href",),
    "script": ("src",),
    "img": ("src", "srcset"),
    "source": ("src", "srcset"),
    "iframe": ("src",),
    "form": ("action",),
}
FETCH_RE = re.compile(r"""fetch\(\s*['"]([^'"]+)['"]""")


class LinkParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str, str]] = []
        self.anchors: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name.lower(): value for name, value in attrs if value is not None}
        if "id" in attr_map:
            self.anchors.add(attr_map["id"])
        if tag == "a" and "name" in attr_map:
            self.anchors.add(attr_map["name"])
        for attr in LINK_ATTRS.get(tag, ()):
            value = attr_map.get(attr)
            if not value:
                continue
            if attr == "srcset":
                for item in value.split(","):
                    candidate = item.strip().split(" ")[0].strip()
                    if candidate:
                        self.links.append((tag, attr, candidate))
            else:
                self.links.append((tag, attr, value.strip()))

    def handle_data(self, data: str) -> None:
        for match in FETCH_RE.finditer(data):
            self.links.append(("script", "fetch", match.group(1).strip()))


def parse_html(path: Path) -> LinkParser:
    parser = LinkParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    return parser


def is_external(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme in {"http", "https"}


def should_ignore(url: str) -> bool:
    if not url or url == "#":
        return True
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme in IGNORED_SCHEMES


def target_file_for(root: Path, current: Path, href: str, base_path: str) -> tuple[Path | None, str | None]:
    parsed = urllib.parse.urlparse(href)
    path = urllib.parse.unquote(parsed.path)
    fragment = urllib.parse.unquote(parsed.fragment)

    if not path:
        return current, fragment

    if path.startswith("/"):
        normalized_base = "/" + base_path.strip("/") + "/"
        if base_path and path.startswith(normalized_base):
            path = path[len(normalized_base) :]
        else:
            return None, fragment
        target = root / path
    else:
        target = (current.parent / path).resolve()

    try:
        target.relative_to(root.resolve())
    except ValueError:
        return None, fragment

    if target.is_dir():
        target = target / "index.html"
    elif href.endswith("/"):
        target = target / "index.html"
    return target, fragment


def check_internal(root: Path, html_files: list[Path], base_path: str) -> list[dict[str, str]]:
    parser_by_file = {path: parse_html(path) for path in html_files}
    issues: list[dict[str, str]] = []

    for current, parser in parser_by_file.items():
        rel_current = current.relative_to(root).as_posix()
        for tag, attr, href in parser.links:
            if should_ignore(href) or is_external(href):
                continue

            parsed = urllib.parse.urlparse(href)
            if href.startswith("/") and not (base_path and parsed.path.startswith("/" + base_path.strip("/") + "/")):
                issues.append({
                    "file": rel_current,
                    "link": href,
                    "kind": "root-absolute-path",
                    "detail": "Use a relative path for GitHub Pages subpath deployments.",
                })
                continue

            target, fragment = target_file_for(root, current, href, base_path)
            if target is None:
                issues.append({
                    "file": rel_current,
                    "link": href,
                    "kind": "outside-site-root",
                    "detail": "The link resolves outside the generated site root.",
                })
                continue

            if not target.exists():
                issues.append({
                    "file": rel_current,
                    "link": href,
                    "kind": "missing-target",
                    "detail": target.relative_to(root).as_posix() if target.parent.exists() else str(target),
                })
                continue

            if fragment and target.suffix.lower() == ".html":
                target_parser = parser_by_file.get(target)
                if target_parser is None:
                    target_parser = parse_html(target)
                    parser_by_file[target] = target_parser
                if fragment not in target_parser.anchors:
                    issues.append({
                        "file": rel_current,
                        "link": href,
                        "kind": "missing-anchor",
                        "detail": f"{target.relative_to(root).as_posix()}#{fragment}",
                    })
    return issues


def collect_external(html_files: list[Path]) -> list[str]:
    urls: set[str] = set()
    for path in html_files:
        parser = parse_html(path)
        for _, _, href in parser.links:
            if is_external(href):
                urls.add(href)
    return sorted(urls)


def check_one_external(url: str, timeout: float) -> dict[str, str] | None:
    opener = urllib.request.build_opener()
    headers = {"User-Agent": "btc-macro-system-link-check/1.0"}
    request = urllib.request.Request(url, headers=headers, method="HEAD")
    try:
        response = opener.open(request, timeout=timeout)
        status = getattr(response, "status", 200)
    except urllib.error.HTTPError as error:
        if error.code in {403, 405, 429}:
            get_request = urllib.request.Request(url, headers=headers, method="GET")
            try:
                response = opener.open(get_request, timeout=timeout)
                status = getattr(response, "status", 200)
            except Exception as fallback_error:  # noqa: BLE001
                return {"url": url, "status": str(error.code), "detail": str(fallback_error)}
        else:
            return {"url": url, "status": str(error.code), "detail": str(error.reason)}
    except Exception as error:  # noqa: BLE001
        return {"url": url, "status": "error", "detail": str(error)}
    if status >= 400:
        return {"url": url, "status": str(status), "detail": "HTTP status >= 400"}
    return None


def check_external(urls: list[str], timeout: float, workers: int) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        future_by_url = {executor.submit(check_one_external, url, timeout): url for url in urls}
        for future in concurrent.futures.as_completed(future_by_url):
            try:
                issue = future.result()
            except Exception as error:  # noqa: BLE001
                issue = {"url": future_by_url[future], "status": "error", "detail": str(error)}
            if issue:
                failures.append(issue)
    return sorted(failures, key=lambda item: item["url"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate links in the generated GitHub Pages site.")
    parser.add_argument("--root", default="_site", help="Generated site root to scan.")
    parser.add_argument("--base-path", default="btc-macro-system", help="GitHub Pages repository path prefix.")
    parser.add_argument("--check-external", action="store_true", help="Also probe external HTTP(S) links.")
    parser.add_argument("--fail-external", action="store_true", help="Exit non-zero on external failures.")
    parser.add_argument("--timeout", type=float, default=8.0, help="External request timeout in seconds.")
    parser.add_argument("--external-workers", type=int, default=12, help="Parallel workers for external checks.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"Site root does not exist: {root}", file=sys.stderr)
        return 2

    html_files = sorted(root.rglob("*.html"))
    internal_issues = check_internal(root, html_files, args.base_path)
    external_urls = collect_external(html_files)
    external_failures = check_external(external_urls, args.timeout, args.external_workers) if args.check_external else []

    result = {
        "root": str(root),
        "html_files": len(html_files),
        "external_links": len(external_urls),
        "internal_issues": internal_issues,
        "external_failures": external_failures,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Scanned {len(html_files)} HTML files under {root}")
        print(f"External links discovered: {len(external_urls)}")
        if internal_issues:
            print("\nInternal link issues:")
            for issue in internal_issues:
                print(f"- {issue['file']}: {issue['link']} [{issue['kind']}] {issue['detail']}")
        else:
            print("Internal links: OK")
        if args.check_external:
            if external_failures:
                print("\nExternal link failures/warnings:")
                for issue in external_failures:
                    print(f"- {issue['url']} [{issue['status']}] {issue['detail']}")
            else:
                print("External links: OK")

    if internal_issues or (args.fail_external and external_failures):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
