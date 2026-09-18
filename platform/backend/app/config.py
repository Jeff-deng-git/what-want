"""What Want backend config."""
import os

BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8011"))
DB_PATH = os.getenv("WW_DB_PATH", "data/ww.db")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3011")

# Book content locations (relative to backend dir unless absolute)
BOOK_MD_DIR = os.getenv("WW_BOOK_MD_DIR", "book/chapters_md")
# Phase A: multi-chapter reading sources. Both relative paths are resolved
# against platform/ root (one level above backend/) so users can keep sources
# outside the backend tree.
CHAPTER_HTML_DIR = os.getenv("WW_CHAPTER_HTML_DIR", "../chapter_html")
CHAPTER_MD_DIR_NEW = os.getenv("WW_CHAPTER_MD_DIR_NEW", "../chapter_md")