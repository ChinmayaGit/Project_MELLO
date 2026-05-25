import os
import re
import shutil
import json
import subprocess
import platform
import datetime

class BaseSkill:
    """Base class for all Mello Skills"""
    name = "base_skill"
    description = "Base skill description"
    enabled = True
    
    def execute(self, params):
        if not self.enabled:
            return f"Error: Skill '{self.name}' is currently disabled."
        raise NotImplementedError("Skills must implement execute()")

class FileSystemSkill(BaseSkill):
    name = "file_system"
    description = "Manage folders and move files"
    category = "file_system"
    
    def execute(self, params):
        if not self.enabled: return super().execute(params)
        action = params.get("action")
        path = params.get("path")

        if action == "mkdir":
            os.makedirs(path, exist_ok=True)
            return f"Created folder: {path}"
        elif action == "create_file":
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            content = params.get("content", "")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Created file: {path}"
        elif action == "move":
            src = params.get("source")
            dst = params.get("destination")
            shutil.move(src, dst)
            return f"Moved {src} to {dst}"
        return f"Unknown action: {action}"

class FileReadSkill(BaseSkill):
    name = "file_reader"
    description = "Read contents of text-based files"
    category = "file_system"
    
    def execute(self, params):
        if not self.enabled: return super().execute(params)
        path = params.get("path")
        if not os.path.exists(path):
            return f"Error: File {path} not found."
            
        # Security: check extension
        if not path.lower().endswith(('.txt', '.csv', '.md', '.json', '.py', '.log')):
            return "Error: Unsupported file type."
            
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read(2048) # Limit read size
            return content

class AppAutomationSkill(BaseSkill):
    name = "app_automation"
    description = "Open applications"
    category = "automation"
    
    def execute(self, params):
        if not self.enabled: return super().execute(params)
        app_name = params.get("app_name")
        # Common Windows aliases
        aliases = {
            "calculator": "calc",
            "notepad": "notepad",
            "command prompt": "cmd",
            "cmd": "cmd",
            "explorer": "explorer",
            "chrome": "chrome",
            "edge": "msedge"
        }
        
        executable = aliases.get(app_name.lower(), app_name)
        
        try:
            if platform.system() == "Windows":
                # Using 'start' is generally best for apps in PATH
                subprocess.Popen(f"start {executable}", shell=True)
            elif platform.system() == "Darwin": # macOS
                subprocess.Popen(["open", "-a", executable])
            else: # Linux
                subprocess.Popen([executable])
            return f"Attempted to open: {executable}"
        except Exception as e:
            return f"Error opening app: {str(e)}"

class ShellExecutionSkill(BaseSkill):
    name = "shell_execution"
    description = "Run shell commands (PowerShell/CMD)"
    category = "automation"
    
    def execute(self, params):
        if not self.enabled: return super().execute(params)
        command = params.get("command")
        
        # Translation Layer: Convert common Linux commands to Windows equivalents
        if platform.system() == "Windows":
            if command.startswith("touch "):
                file_path = command.replace("touch ", "").strip()
                command = f"New-Item -Path {file_path} -ItemType File -Force"
            elif command.startswith("ls "):
                command = command.replace("ls ", "dir ")
            elif command.startswith("rm "):
                command = command.replace("rm ", "Remove-Item ")

        try:
            # Note: In a production app, we would add strict security checks here
            result = subprocess.run(
                ["powershell", "-Command", command] if platform.system() == "Windows" else [command],
                capture_output=True,
                text=True,
                shell=True
            )
            output = result.stdout if result.returncode == 0 else result.stderr
            if not output and result.returncode == 0:
                return "Command executed successfully (no output)."
            return f"Command executed. Output:\n{output[:1000]}"
        except Exception as e:
            return f"Error executing command: {str(e)}"

import pyautogui

class VisionSkill(BaseSkill):
    name = "vision"
    description = "Take a screenshot to 'see' the desktop"
    category = "vision"
    
    def execute(self, params):
        if not self.enabled: return super().execute(params)
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            # Ensure a screenshots folder exists
            os.makedirs("screenshots", exist_ok=True)
            path = os.path.join("screenshots", filename)
            pyautogui.screenshot(path)
            return f"Screenshot saved to {path}. I can now 'see' your desktop state."
        except Exception as e:
            return f"Error taking screenshot: {str(e)}"

class SortSkill(BaseSkill):
    name = "sort"
    description = "Sort files in a folder into a best-practice nested folder structure"
    category = "file_system"

    MUSIC_EXTS    = {'.mp3', '.flac', '.wav', '.aac', '.ogg', '.m4a', '.wma', '.opus', '.aiff', '.alac'}
    VIDEO_EXTS    = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.3gp', '.ts', '.vob'}
    DOCUMENT_EXTS = {'.pdf', '.doc', '.docx', '.txt', '.xlsx', '.xls', '.pptx', '.ppt', '.odt', '.rtf', '.csv', '.md'}
    IMAGE_EXTS    = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.tiff', '.tif', '.webp', '.ico', '.heic', '.raw', '.cr2', '.nef'}
    CODE_EXTS     = {'.py', '.js', '.ts', '.html', '.css', '.java', '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.sh', '.bat', '.ps1', '.json', '.xml', '.yaml', '.yml', '.toml', '.sql', '.lua', '.r'}
    ARCHIVE_EXTS  = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.iso', '.cab'}
    EBOOK_EXTS    = {'.epub', '.mobi', '.azw', '.azw3', '.fb2'}

    _DOC_SUBFOLDERS = {
        '.pdf': 'PDFs', '.doc': 'Word Docs', '.docx': 'Word Docs', '.odt': 'Word Docs', '.rtf': 'Word Docs',
        '.xlsx': 'Spreadsheets', '.xls': 'Spreadsheets', '.csv': 'Spreadsheets',
        '.pptx': 'Presentations', '.ppt': 'Presentations',
        '.txt': 'Text Files', '.md': 'Text Files',
    }
    _MONTH_NAMES = {
        '01': '01-Jan', '02': '02-Feb', '03': '03-Mar', '04': '04-Apr',
        '05': '05-May', '06': '06-Jun', '07': '07-Jul', '08': '08-Aug',
        '09': '09-Sep', '10': '10-Oct', '11': '11-Nov', '12': '12-Dec',
    }

    def _sanitize(self, name):
        return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(name)).strip()[:80] or 'Unknown'

    def _music_meta(self, filepath):
        try:
            from mutagen import File as MFile
            audio = MFile(filepath, easy=True)
            if audio:
                # Prefer albumartist (primary/main artist, no features)
                # Fall back to first value in artist tag
                raw_artist = (
                    audio.get('albumartist') or
                    audio.get('artist') or
                    ['Unknown Artist']
                )[0]
                # Take only the first artist when comma-separated
                artist = re.split(r'\s*[,;]\s*', str(raw_artist))[0].strip()
                album  = str((audio.get('album') or ['Unknown Album'])[0])
                return self._sanitize(artist) or 'Unknown Artist', \
                       self._sanitize(album)  or 'Unknown Album'
        except Exception:
            pass
        return 'Unknown Artist', 'Unknown Album'

    def _movie_year(self, filename):
        m = re.search(r'\b(19|20)\d{2}\b', filename)
        return m.group(0) if m else 'Unknown Year'

    def _image_date(self, filepath):
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS
            with Image.open(filepath) as img:
                exif = img._getexif() or {}
            for tag_id, val in exif.items():
                if TAGS.get(tag_id) == 'DateTimeOriginal' and isinstance(val, str) and len(val) >= 7:
                    return val[:4], val[5:7]
        except Exception:
            pass
        dt = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
        return str(dt.year), f"{dt.month:02d}"

    def _dest_for(self, filepath, base, sort_type):
        ext  = os.path.splitext(filepath)[1].lower()
        name = os.path.basename(filepath)
        t    = sort_type

        # For mixed sorts (all/auto) add a category subfolder so types don't clash.
        # For a specific type the caller is already inside that folder — no prefix needed.
        mixed = t in ('all', 'auto')

        def p(category): return os.path.join(base, category) if mixed else base

        if t in ('music', 'audio', 'all', 'auto') and ext in self.MUSIC_EXTS:
            artist, album = self._music_meta(filepath)
            return os.path.join(p('Music'), artist, album), 'Music'

        if t in ('movies', 'videos', 'all', 'auto') and ext in self.VIDEO_EXTS:
            year = self._movie_year(name)
            return os.path.join(p('Movies'), year), 'Movies'

        if t in ('documents', 'docs', 'all', 'auto') and ext in self.DOCUMENT_EXTS:
            sub = self._DOC_SUBFOLDERS.get(ext, 'Other Docs')
            return os.path.join(p('Documents'), sub), 'Documents'

        if t in ('images', 'photos', 'all', 'auto') and ext in self.IMAGE_EXTS:
            year, month = self._image_date(filepath)
            return os.path.join(p('Images'), year, self._MONTH_NAMES.get(month, month)), 'Images'

        if t in ('code', 'all', 'auto') and ext in self.CODE_EXTS:
            return p('Code'), 'Code'

        if t in ('archives', 'all', 'auto') and ext in self.ARCHIVE_EXTS:
            return p('Archives'), 'Archives'

        if t in ('ebooks', 'all', 'auto') and ext in self.EBOOK_EXTS:
            return p('eBooks'), 'eBooks'

        if mixed:
            return os.path.join(base, 'Other'), 'Other'

        return None, None

    def _unique_dest(self, dest_dir, filename):
        dest = os.path.join(dest_dir, filename)
        if not os.path.exists(dest):
            return dest
        base, ext = os.path.splitext(filename)
        i = 1
        while os.path.exists(dest):
            dest = os.path.join(dest_dir, f"{base}_{i}{ext}")
            i += 1
        return dest

    def execute(self, params):
        if not self.enabled:
            return super().execute(params)

        path      = params.get("path", "")
        sort_type = params.get("type", "auto").lower()
        dry_run   = params.get("dry_run", False)

        if not path or not os.path.isdir(path):
            return f"Error: '{path}' is not a valid directory."

        # Collect all files recursively
        all_files = []
        for root, _, filenames in os.walk(path):
            for filename in filenames:
                all_files.append(os.path.join(root, filename))

        if not all_files:
            return f"No files found in '{path}'."

        moved, skipped = [], []

        for src in all_files:
            filename  = os.path.basename(src)
            dest_dir, category = self._dest_for(src, path, sort_type)

            if dest_dir is None or os.path.normcase(os.path.dirname(src)) == os.path.normcase(dest_dir):
                skipped.append(os.path.relpath(src, path))
                continue

            dest_path = self._unique_dest(dest_dir, filename)
            rel       = os.path.relpath(dest_dir, path)

            if dry_run:
                moved.append(f"[PREVIEW] {os.path.relpath(src, path)}  ->  {rel}")
            else:
                os.makedirs(dest_dir, exist_ok=True)
                shutil.move(src, dest_path)
                moved.append(f"{filename}  ->  {rel}  ({category})")

        # Remove empty directories left behind (skip root path itself)
        if not dry_run:
            for root, dirs, files in os.walk(path, topdown=False):
                if root == path:
                    continue
                try:
                    if not os.listdir(root):
                        os.rmdir(root)
                except OSError:
                    pass

        mode  = "Preview" if dry_run else "Sorted"
        lines = [f"{mode}: {len(moved)} file(s) in '{path}'"]
        lines += [f"  {m}" for m in moved]

        if skipped:
            lines.append(f"\nSkipped {len(skipped)} file(s) (type not matched or already in place):")
            lines += [f"  {s}" for s in skipped[:10]]
            if len(skipped) > 10:
                lines.append(f"  ... and {len(skipped) - 10} more")

        return "\n".join(lines)


class WebSearchSkill(BaseSkill):
    name = "web_search"
    description = "Search the web using DuckDuckGo (no API key needed)"
    category = "web"

    def execute(self, params):
        if not self.enabled:
            return super().execute(params)

        import urllib.request, urllib.parse

        query = params.get("query", "").strip()
        if not query:
            return "Error: No search query provided."

        try:
            url = (
                "https://api.duckduckgo.com/?q="
                + urllib.parse.quote(query)
                + "&format=json&no_html=1&skip_disambig=1"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Mello/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            lines = []

            if data.get("Answer"):
                lines.append(f"Answer: {data['Answer']}")

            if data.get("AbstractText"):
                lines.append(f"Summary: {data['AbstractText']}")
                if data.get("AbstractURL"):
                    lines.append(f"Source: {data['AbstractURL']}")

            topics = [t for t in data.get("RelatedTopics", [])
                      if isinstance(t, dict) and t.get("Text")][:4]
            if topics:
                lines.append("Related:")
                for t in topics:
                    lines.append(f"  - {t['Text'][:200]}")

            return "\n".join(lines) if lines else f"No results found for: {query}"

        except Exception as e:
            return f"Search error: {e}"


class ThumbnailDownloaderSkill(BaseSkill):
    """
    Scans a folder for video files, searches IMDb for each movie's poster,
    and downloads the thumbnail image next to the video file.
    Requires only Python standard library — no extra pip installs.
    """
    name        = "thumbnail_downloader"
    description = "Find and download movie poster thumbnails from IMDb for videos in a folder"
    category    = "media"

    VIDEO_EXTS = {
        '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v',
        '.flv', '.webm', '.mpg', '.mpeg', '.3gp', '.ts', '.vob',
    }

    # ── Filename parsing ─────────────────────────────────────────────────────

    def _parse_filename(self, filename):
        """Return (clean_title, year_or_None) from a typical ripped-movie filename."""
        stem = os.path.splitext(filename)[0]

        # Extract year before stripping everything
        year_m = re.search(r'[\(\[\.\s]((?:19|20)\d{2})[\)\]\.\s]', stem)
        year   = year_m.group(1) if year_m else None

        # Remove year and everything after it (quality tags, scene info …)
        name = re.sub(r'[\(\[\.\s](?:19|20)\d{2}.*', '', stem)
        # Replace separators with spaces
        name = re.sub(r'[._\-]', ' ', name).strip()
        # Strip leftover quality tags in case there was no year
        name = re.sub(
            r'\s*\b(1080p|720p|480p|2160p|4K|UHD|BluRay|Blu[-\s]Ray|HDRip'
            r'|WEBRip|WEB[-\s]DL|HEVC|x264|x265|H\.?264|H\.?265|AC3|AAC'
            r'|DTS|YIFY|YTS|DVDRip|BRRip|PROPER|REPACK|EXTENDED|UNRATED)\b.*',
            '', name, flags=re.IGNORECASE,
        ).strip()

        return (name.strip() or stem), year

    # ── IMDb lookup ──────────────────────────────────────────────────────────

    def _fetch(self, url, extra_headers=None):
        """Return decoded HTML string for *url* or raise."""
        import urllib.request
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0 Safari/537.36'
            ),
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            return resp.read().decode('utf-8', errors='replace')

    def _search_imdb(self, movie_name, year=None):
        """
        Returns (poster_url, canonical_title) or (None, None).
        Strategy:
          1. Search IMDb /find for a title link
          2. Load the title page and extract JSON-LD schema → 'image'
          3. Fall back to og:image meta tag
        """
        import urllib.parse
        from html.parser import HTMLParser

        # ── Step 1: search ────────────────────────────────────────────────
        q   = urllib.parse.quote(f"{movie_name} {year}" if year else movie_name)
        url = f"https://www.imdb.com/find/?q={q}&s=tt&ttype=ft&ref_=fn_ft"

        class _FirstTitleLink(HTMLParser):
            """Grab the first /title/ttXXXXXXXX/ href in the page."""
            def __init__(self):
                super().__init__()
                self.path = None
            def handle_starttag(self, tag, attrs):
                if self.path or tag != 'a':
                    return
                d = dict(attrs)
                href = d.get('href', '')
                if re.match(r'^/title/tt\d+/?', href):
                    self.path = href.split('?')[0].rstrip('/') + '/'

        try:
            html = self._fetch(url)
        except Exception as e:
            return None, None

        p = _FirstTitleLink()
        p.feed(html)
        if not p.path:
            return None, None

        # ── Step 2: title page ────────────────────────────────────────────
        try:
            title_html = self._fetch(f"https://www.imdb.com{p.path}")
        except Exception:
            return None, None

        # Try JSON-LD first (most reliable — contains high-res poster)
        m = re.search(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            title_html, re.DOTALL,
        )
        if m:
            try:
                data   = json.loads(m.group(1))
                img    = data.get('image')
                poster = img if isinstance(img, str) else (img or {}).get('url') if isinstance(img, dict) else None
                title  = data.get('name', movie_name)
                if poster and poster.startswith('http'):
                    return poster, title
            except Exception:
                pass

        # Fall back to og:image
        og = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            title_html,
        )
        if og:
            return og.group(1), movie_name

        return None, None

    # ── Main execute ─────────────────────────────────────────────────────────

    def execute(self, params):
        if not self.enabled:
            return super().execute(params)

        import urllib.request

        folder      = params.get('path', '.').strip()
        save_folder = params.get('save_path', folder).strip() or folder

        if not os.path.isdir(folder):
            return f"Error: '{folder}' is not a valid directory."

        # Collect video files (non-recursive by default)
        videos = [
            f for f in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, f))
            and os.path.splitext(f)[1].lower() in self.VIDEO_EXTS
        ]

        if not videos:
            return f"No video files found in '{folder}'."

        os.makedirs(save_folder, exist_ok=True)

        success, failed = [], []

        for filename in videos:
            movie_name, year = self._parse_filename(filename)

            # Skip if thumbnail already exists
            safe = re.sub(r'[<>:"/\\|?*]', '_', movie_name)
            existing = os.path.join(save_folder, f"{safe}.jpg")
            if os.path.exists(existing):
                success.append(f"  ⏭  {movie_name} — already downloaded, skipped")
                continue

            try:
                poster_url, title = self._search_imdb(movie_name, year)
            except Exception as e:
                failed.append(f"  ✗ {filename} — IMDb search error: {e}")
                continue

            if not poster_url:
                failed.append(f"  ✗ {filename} — no poster found for '{movie_name}'")
                continue

            try:
                safe_title = re.sub(r'[<>:"/\\|?*]', '_', title or movie_name)
                save_path  = os.path.join(save_folder, f"{safe_title}.jpg")
                req = urllib.request.Request(
                    poster_url,
                    headers={'User-Agent': 'Mozilla/5.0'},
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    image_data = resp.read()
                with open(save_path, 'wb') as f:
                    f.write(image_data)
                success.append(f"  ✓ {title or movie_name}  →  {os.path.basename(save_path)}")
            except Exception as e:
                failed.append(f"  ✗ {filename} — download failed: {e}")

        total = len(videos)
        ok    = len([s for s in success if s.startswith('  ✓')])
        lines = [
            f"🎬 Thumbnail download complete — {ok}/{total} new poster(s) saved to '{save_folder}'"
        ]
        if success:
            lines.append("\nDownloaded:")
            lines += success
        if failed:
            lines.append("\nFailed:")
            lines += failed
        return "\n".join(lines)


from ..security import SecurityLayer

class SkillManager:
    """Loads and manages Mello's modular skills with a Security Layer"""
    def __init__(self):
        self.security = SecurityLayer()
        self.skills = {
            "mkdir":                FileSystemSkill(),
            "create_file":          FileSystemSkill(),
            "move":                 FileSystemSkill(),
            "read_file":            FileReadSkill(),
            "open_app":             AppAutomationSkill(),
            "run_command":          ShellExecutionSkill(),
            "screenshot":           VisionSkill(),
            "sort":                 SortSkill(),
            "web_search":           WebSearchSkill(),
            "thumbnail_downloader": ThumbnailDownloaderSkill(),
        }
        # Load any user-created custom skills from src/skills/custom/
        self.load_custom_skills()

    # ── Custom skill hot-loader ──────────────────────────────────────────────

    def load_custom_skills(self):
        """
        Scan src/skills/custom/ for .py files, import each one, and register
        any BaseSkill subclass found.  Safe to call multiple times — re-registers
        on every call so newly saved files are picked up immediately.
        """
        import importlib.util

        custom_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom")
        os.makedirs(custom_dir, exist_ok=True)

        # Ensure the custom package has an __init__.py
        init_path = os.path.join(custom_dir, "__init__.py")
        if not os.path.exists(init_path):
            with open(init_path, "w") as _f:
                _f.write("# Mello custom skills — auto-generated\n")

        loaded = []
        for fname in sorted(os.listdir(custom_dir)):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            fpath = os.path.join(custom_dir, fname)
            try:
                spec = importlib.util.spec_from_file_location(
                    f"mello_custom.{fname[:-3]}", fpath
                )
                mod = importlib.util.module_from_spec(spec)

                # Inject common names so generated skills don't need explicit imports
                _inject = {
                    "BaseSkill": BaseSkill,
                    "os": os, "re": re, "json": json,
                    "subprocess": subprocess, "platform": platform,
                    "datetime": datetime, "shutil": shutil,
                }
                for k, v in _inject.items():
                    setattr(mod, k, v)

                spec.loader.exec_module(mod)
            except Exception as exc:
                print(f"[SkillLoader] ⚠ Error loading '{fname}': {exc}")
                continue

            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                try:
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseSkill)
                        and attr is not BaseSkill
                        and getattr(attr, "name", "base_skill") not in ("base_skill", "")
                    ):
                        instance = attr()
                        self.skills[instance.name] = instance
                        loaded.append(instance.name)
                        print(f"[SkillLoader] ✓ Registered custom skill: '{instance.name}'")
                except Exception:
                    pass

        return loaded

    def toggle_skill(self, skill_name, state: bool):
        if skill_name in self.skills:
            self.skills[skill_name].enabled = state
            return True
        return False

    def get_skill_manifest(self):
        """Returns a string description of all available skills for the LLM prompt"""
        manifest = "Available Skills:\n"
        for name, skill in self.skills.items():
            if skill.enabled:
                if name == "mkdir": manifest += '- mkdir: Create a folder. Params: { "action": "mkdir", "path": "string" }\n'
                elif name == "create_file": manifest += '- create_file: Create a file with optional content. Params: { "action": "create_file", "path": "string", "content": "string" }\n'
                elif name == "move": manifest += '- move: Move a file. Params: { "action": "move", "source": "string", "destination": "string" }\n'
                elif name == "read_file": manifest += "- read_file: Read file content. Params: { 'path': 'string' }\n"
                elif name == "open_app": manifest += "- open_app: Open an application. Params: { 'app_name': 'string' }\n"
                elif name == "run_command": manifest += "- run_command: Run a shell command. Params: { 'command': 'string' }\n"
                elif name == "screenshot": manifest += "- screenshot: Take a screenshot of the current screen. Params: {}\n"
                elif name == "sort": manifest += '- sort: Sort files in a folder into a structured hierarchy. Params: { "action": "sort", "path": "string", "type": "auto|music|movies|documents|images|code|archives|ebooks|all", "dry_run": false }\n'
                elif name == "web_search": manifest += '- web_search: Search the web for information. Params: { "action": "web_search", "query": "string" }\n'
                elif name == "thumbnail_downloader": manifest += '- thumbnail_downloader: Download IMDb movie poster thumbnails for all video files in a folder. Params: { "action": "thumbnail_downloader", "path": "string", "save_path": "string (optional, defaults to same folder)" }\n'
        return manifest

    def run_skill(self, action, params):
        # 1. Permission Checks
        if action in ["mkdir", "move", "read_file", "sort"]:
            path = params.get("path") or params.get("source") or params.get("destination")
            if path and not self.security.is_path_allowed(path):
                return f"Security Error: Access to path '{path}' is denied by policy."
        
        if action == "open_app":
            app_name = params.get("app_name")
            if not self.security.is_app_allowed(app_name):
                return f"Security Error: Application '{app_name}' is not in the allowed list."
        
        if action == "run_command":
            command = params.get("command")
            if not self.security.is_command_allowed(command):
                return f"Security Error: Command '{command}' contains restricted keywords or is disallowed."

        if action == "thumbnail_downloader":
            path = params.get("path", ".")
            if path and path != "." and not self.security.is_path_allowed(path):
                return f"Security Error: Access to path '{path}' is denied by policy."

        # 2. Execution
        skill = self.skills.get(action)
        if skill:
            return skill.execute(params)
        return f"Skill for action '{action}' not found."
