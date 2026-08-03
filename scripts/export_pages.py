#!/usr/bin/env python3

import argparse
import re
import shutil
import subprocess
import sys
import tempfile

from html.parser import HTMLParser
from pathlib import Path


class RenderedPageExtractor(HTMLParser):
    void_tags = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.captured_pages = []
        self.current_page_kind = None
        self.current_page_chunks = []
        self.current_page_depth = 0

    def handle_starttag(self, tag, attributes):
        start_tag_text = self.get_starttag_text()

        if self.current_page_kind is None:
            if tag == "div" and self.has_class(attributes, "cover"):
                self.current_page_kind = "cover"
                self.current_page_chunks = [start_tag_text]
                self.current_page_depth = 1
                return

            if tag == "article" and self.has_class(attributes, "comic"):
                self.current_page_kind = "comic"
                self.current_page_chunks = [start_tag_text]
                self.current_page_depth = 1
                return

        if self.current_page_kind is not None:
            self.current_page_chunks.append(start_tag_text)
            if tag not in self.void_tags:
                self.current_page_depth += 1

    def handle_endtag(self, tag):
        if self.current_page_kind is None:
            return

        self.current_page_chunks.append(f"</{tag}>")
        self.current_page_depth -= 1

        if self.current_page_depth == 0:
            self.captured_pages.append(
                (self.current_page_kind, "".join(self.current_page_chunks))
            )
            self.current_page_kind = None
            self.current_page_chunks = []

    def handle_startendtag(self, tag, attributes):
        if self.current_page_kind is not None:
            self.current_page_chunks.append(self.get_starttag_text())

    def handle_data(self, data):
        if self.current_page_kind is not None:
            self.current_page_chunks.append(data)

    def handle_comment(self, data):
        if self.current_page_kind is not None:
            self.current_page_chunks.append(f"<!--{data}-->")

    def handle_entityref(self, name):
        if self.current_page_kind is not None:
            self.current_page_chunks.append(f"&{name};")

    def handle_charref(self, name):
        if self.current_page_kind is not None:
            self.current_page_chunks.append(f"&#{name};")

    def has_class(self, attributes, class_name):
        for attribute_name, attribute_value in attributes:
            if attribute_name != "class" or not attribute_value:
                continue

            if class_name in attribute_value.split():
                return True

        return False


def parse_arguments():
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument(
        "page",
        help="Built html file or a date like 2026-07-22",
    )
    argument_parser.add_argument(
        "--output-dir",
        help="Directory for exported images",
    )
    argument_parser.add_argument(
        "--format",
        choices=["png", "jpeg"],
        default="png",
    )
    return argument_parser.parse_args()


def find_chrome_binary():
    chrome_candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]

    for chrome_candidate in chrome_candidates:
        if chrome_candidate and Path(chrome_candidate).exists():
            return chrome_candidate

    raise SystemExit("Google Chrome or Chromium was not found.")


def find_magick_binary():
    magick_binary = shutil.which("magick")

    if magick_binary:
        return magick_binary

    raise SystemExit("ImageMagick was not found.")


def find_repo_root():
    return Path(__file__).resolve().parent.parent


def resolve_built_page(page_argument, repo_root):
    page_path = Path(page_argument)

    if page_path.exists():
        return page_path.resolve()

    dated_page_path = repo_root / "_site" / f"{page_argument}.html"

    if dated_page_path.exists():
        return dated_page_path.resolve()

    raise SystemExit(f"Could not find built page: {page_argument}")


def read_rendered_pages(built_page_path):
    rendered_page_text = built_page_path.read_text()
    rendered_page_extractor = RenderedPageExtractor()
    rendered_page_extractor.feed(rendered_page_text)
    rendered_page_extractor.close()

    if not rendered_page_extractor.captured_pages:
        raise SystemExit(f"No comic pages found in {built_page_path}")

    return rendered_page_extractor.captured_pages


def read_comic_css(repo_root, built_page_path):
    built_page_text = built_page_path.read_text()
    stylesheet_matches = re.findall(
        r'href="[^"]*assets/css/([^"/]+\.css)"',
        built_page_text,
    )

    stylesheet_name = stylesheet_matches[-1] if stylesheet_matches else "3.css"
    css_path = repo_root / "assets" / "css" / stylesheet_name
    return css_path.read_text()


def normalise_page_markup(page_markup):
    cleaned_page_markup = page_markup.replace('src="/Comics//assets/', 'src="assets/')
    cleaned_page_markup = cleaned_page_markup.replace('src="/Comics/assets/', 'src="assets/')
    cleaned_page_markup = cleaned_page_markup.replace("src='/Comics//assets/", "src='assets/")
    cleaned_page_markup = cleaned_page_markup.replace("src='/Comics/assets/", "src='assets/")
    cleaned_page_markup = cleaned_page_markup.replace('href="/Comics//assets/', 'href="assets/')
    cleaned_page_markup = cleaned_page_markup.replace('href="/Comics/assets/', 'href="assets/')
    return cleaned_page_markup


def build_wrapper_html(repo_root, comic_css, page_markup):
    base_href = (repo_root / "_site").resolve().as_uri() + "/"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <base href="{base_href}">
  <style>
{comic_css}
html, body {{
  margin: 0;
  padding: 0;
  background: white;
}}
body {{
  display: flex;
  flex-direction: column;
  align-items: center;
}}
.cover,
.comic {{
  margin: 0 auto;
}}
.cover {{
  width: 1080px;
  height: 1350px;
  max-width: none;
  max-height: none;
}}
.comic {{
  width: 730px;
  height: 913px;
  max-width: none;
  max-height: none;
}}
.comic > div,
.textpanel {{
  z-index: 0;
}}
  </style>
</head>
<body>
{page_markup}
</body>
</html>
"""


def window_size_for_page(page_kind):
    if page_kind == "cover":
        return "1120,1440"

    return "760,1120"


def export_page_image(
    chrome_binary,
    magick_binary,
    wrapper_html_path,
    output_image_path,
    page_kind,
    output_format,
    browser_state_directory,
):
    png_output_path = output_image_path.with_suffix(".png")
    chrome_environment = dict(**{"HOME": str(browser_state_directory)})
    chrome_user_data_directory = browser_state_directory / "chrome-profile"
    chrome_user_data_directory.mkdir(parents=True, exist_ok=True)

    chrome_command = [
        chrome_binary,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--disable-breakpad",
        "--disable-crash-reporter",
        "--no-first-run",
        "--no-default-browser-check",
        "--use-mock-keychain",
        "--force-device-scale-factor=1",
        "--virtual-time-budget=2000",
        f"--user-data-dir={chrome_user_data_directory}",
        f"--window-size={window_size_for_page(page_kind)}",
        f"--screenshot={png_output_path}",
        wrapper_html_path.as_uri(),
    ]

    subprocess.run(
        chrome_command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=chrome_environment,
    )

    if output_format == "png":
        return png_output_path

    subprocess.run(
        [
            magick_binary,
            str(png_output_path),
            "-quality",
            "92",
            str(output_image_path),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    png_output_path.unlink()
    return output_image_path


def main():
    arguments = parse_arguments()
    repo_root = find_repo_root()
    built_page_path = resolve_built_page(arguments.page, repo_root)
    rendered_pages = read_rendered_pages(built_page_path)
    comic_css = read_comic_css(repo_root, built_page_path)
    chrome_binary = find_chrome_binary()
    magick_binary = find_magick_binary() if arguments.format == "jpeg" else None

    default_output_directory = repo_root / "output" / built_page_path.stem
    output_directory = Path(arguments.output_dir) if arguments.output_dir else default_output_directory
    output_directory.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temporary_directory_name:
        temporary_directory = Path(temporary_directory_name)
        browser_state_directory = temporary_directory / "browser-home"
        browser_state_directory.mkdir(parents=True, exist_ok=True)

        for page_number, (page_kind, page_markup) in enumerate(rendered_pages, start=1):
            output_file_extension = "png" if arguments.format == "png" else "jpeg"
            output_image_path = output_directory / f"page-{page_number:02d}.{output_file_extension}"
            wrapper_html_path = temporary_directory / f"page-{page_number:02d}.html"
            wrapper_html = build_wrapper_html(
                repo_root,
                comic_css,
                normalise_page_markup(page_markup),
            )
            wrapper_html_path.write_text(wrapper_html)
            export_page_image(
                chrome_binary,
                magick_binary,
                wrapper_html_path,
                output_image_path,
                page_kind,
                arguments.format,
                browser_state_directory,
            )
            print(output_image_path)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        if error.stderr:
            sys.stderr.write(error.stderr.decode())
        raise SystemExit(error.returncode)
