from __future__ import annotations

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from app.catalog import (  # noqa: E402
    ASSET_GUIDE,
    BUNDLES,
    CHANNEL_OFFER_CAPTION,
    COLORS,
    PAYMENT_TEXT_BUNDLE,
    PAYMENT_TEXT_CHANNEL,
    PAYMENT_TEXT_SINGLE,
    PRODUCTS,
    START_TEXT,
)
from app.utils import render_text, visible_text_length  # noqa: E402


MAX_CAPTION = 1024


def assert_caption_limit(name: str, text: str) -> None:
    length = visible_text_length(text)
    if length > MAX_CAPTION:
        raise AssertionError(f"{name}: caption too long ({length} > {MAX_CAPTION})")


def main() -> None:
    demo_name = "Алексей"

    assert_caption_limit("START_TEXT", render_text(START_TEXT, name=demo_name))
    assert_caption_limit("CHANNEL_OFFER_CAPTION", render_text(CHANNEL_OFFER_CAPTION, name=demo_name))
    assert_caption_limit("PAYMENT_TEXT_SINGLE", render_text(PAYMENT_TEXT_SINGLE, name=demo_name, url="https://example.com"))
    assert_caption_limit("PAYMENT_TEXT_BUNDLE", render_text(PAYMENT_TEXT_BUNDLE, name=demo_name, url="https://example.com"))
    assert_caption_limit("PAYMENT_TEXT_CHANNEL", render_text(PAYMENT_TEXT_CHANNEL, name=demo_name, url="https://example.com"))

    for product_id, product in PRODUCTS.items():
        rendered = render_text(product.album_caption, name=demo_name)
        assert_caption_limit(f"product:{product_id}", rendered)
        if len(product.payment_urls) != len(COLORS):
            raise AssertionError(f"product:{product_id}: expected {len(COLORS)} payment urls")

    for bundle_id, bundle in BUNDLES.items():
        assert_caption_limit(f"bundle:{bundle_id}", bundle.album_caption)
        if len(bundle.payment_urls) != len(COLORS):
            raise AssertionError(f"bundle:{bundle_id}: expected {len(COLORS)} payment urls")

    for directory, files in ASSET_GUIDE.items():
        full_dir = PROJECT_DIR / directory
        if not full_dir.exists():
            raise AssertionError(f"Missing directory: {directory}")
        if not files:
            raise AssertionError(f"Empty asset guide for: {directory}")

    print("OK: catalog, routes and caption limits look valid.")


if __name__ == "__main__":
    main()
