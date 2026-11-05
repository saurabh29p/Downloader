"""Local conversions: images → PDF, OCR, audio/video formats, EPUB → PDF.

Inputs are files already inside the downloads folder; nothing here fetches a URL.
External tools (ocrmypdf/tesseract, ffmpeg, Calibre) run as separate processes
and are optional: `available()` says what this machine can do.
"""
