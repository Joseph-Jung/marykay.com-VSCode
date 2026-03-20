#!/usr/bin/env python3
"""
MaryKay.com Corpus Builder — Compliant Web Scraper
Builds a structured, deduplicated corpus for RAG from publicly accessible pages.
"""

import asyncio
import csv
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin, parse_qs, urlencode

import httpx
from bs4 import BeautifulSoup

# ── Configuration ──────────────────────────────────────────────────────────────

BASE_URL = "https://www.marykay.com"
USER_AGENT = "MaryKayCorpusBot/1.0 (educational-research)"
CRAWL_DELAY = 2.0  # seconds between requests
MAX_RETRIES = 3
TIMEOUT = 30.0
MAX_CONCURRENT = 3
OUTPUT_DIR = Path(__file__).parent.parent / "3.Result"

# Tracking params to strip
TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
                   "utm_content", "gclid", "fbclid", "ref", "src"}

# Disallowed paths from robots.txt
DISALLOWED_PATHS = [
    "/account", "/profile", "/login", "/register", "/passwordreset",
    "/setpassword", "/confirmednewpassword", "/addressbook",
    "/cart", "/addAllToCart", "/checkout", "/confirmation",
    "/ibcprofile", "/shopwithme", "/mylists", "/sharefavorites", "/unsubscribe",
]

# Disallowed URL params from robots.txt
DISALLOWED_PARAMS = ["pmin", "pmax", "prefn1", "prefn2", "prefn3", "prefn4",
                     "prefv1", "prefv2", "prefv3", "prefv4"]

# ── Sitemap URLs (pre-loaded from sitemap_0.xml) ──────────────────────────────

SITEMAP_URLS = [
    "https://www.marykay.com/en/makeup/face/cc-cream/mary-kay-cc-cream-sunscreen-broad-spectrum-spf-15/4US.html",
    "https://www.marykay.com/es/makeup/face/cc-cream/mary-kay-cc-cream-sunscreen-broad-spectrum-spf-15/4US.html",
    "https://www.marykay.com/en/makeup/eyes/eye-shadow/mary-kay-chromafusion-eye-shadow/163122US.html",
    "https://www.marykay.com/es/makeup/eyes/eye-shadow/mary-kay-chromafusion-eye-shadow/163122US.html",
    "https://www.marykay.com/en/makeup/cheeks/contour-and-highlight/mary-kay-chromafusion-highlighter/164262US.html",
    "https://www.marykay.com/es/makeup/cheeks/contour-and-highlight/mary-kay-chromafusion-highlighter/164262US.html",
    "https://www.marykay.com/en/makeup/face/foundation/timewise-matte-3d-foundation/175427US.html",
    "https://www.marykay.com/es/makeup/face/foundation/timewise-matte-3d-foundation/175427US.html",
    "https://www.marykay.com/en/makeup/lips/lip-gloss/mary-kay-unlimited-lip-gloss/182865US.html",
    "https://www.marykay.com/es/makeup/lips/lip-gloss/mary-kay-unlimited-lip-gloss/182865US.html",
    "https://www.marykay.com/en/makeup/lips/lipstick/mary-kay-supreme-hydrating-lipstick/190821US.html",
    "https://www.marykay.com/es/makeup/lips/lipstick/mary-kay-supreme-hydrating-lipstick/190821US.html",
    "https://www.marykay.com/en/makeup/eyes/eye-shadow/mary-kay-shimmer-eye-shadow-stick/233128US.html",
    "https://www.marykay.com/es/makeup/eyes/eye-shadow/mary-kay-shimmer-eye-shadow-stick/233128US.html",
    "https://www.marykay.com/en/makeup/face/concealer/mary-kay-multibenefit-concealer/237071US.html",
    "https://www.marykay.com/es/makeup/face/concealer/mary-kay-multibenefit-concealer/237071US.html",
    "https://www.marykay.com/en/root/mary-kay-gel-semishine-lipstick-naturally-buff-301084/301084US10094608.html",
    "https://www.marykay.com/es/root/mary-kay-gel-semishine-lipstick-naturally-buff-301084/301084US10094608.html",
    "https://www.marykay.com/en/mens/mens-skincare/mkmen-regimen-10242538/990275224US10242538.html",
    "https://www.marykay.com/es/mens/mens-skincare/mkmen-regimen-10242538/990275224US10242538.html",
    "https://www.marykay.com/en/skincare/collection/mk-men/mkmen-moisturizing-shave-cream-10234520/990319184US10234520.html",
    "https://www.marykay.com/es/skincare/collection/mk-men/mkmen-moisturizing-shave-cream-10234520/990319184US10234520.html",
    "https://www.marykay.com/en/skincare/collection/mary-kay-skin-care/mary-kay-hydrating-regimen-990322397/990322397US10230672.html",
    "https://www.marykay.com/es/skincare/collection/mary-kay-skin-care/mary-kay-hydrating-regimen-990322397/990322397US10230672.html",
    "https://www.marykay.com/en/hidden-subcategory/cello-gift-bag-990323876/990323876US10228894.html",
    "https://www.marykay.com/es/hidden-subcategory/cello-gift-bag-990323876/990323876US10228894.html",
    "https://www.marykay.com/en/skincare/collection/clear-proof/clear-proof-clarifying-cleansing-gel-10233551/990331674US10233551.html",
    "https://www.marykay.com/es/skincare/collection/clear-proof/clear-proof-clarifying-cleansing-gel-10233551/990331674US10233551.html",
    "https://www.marykay.com/en/mens/mens-fragrance",
    "https://www.marykay.com/es/mens/mens-fragrance",
    "https://www.marykay.com/en/gifts/gifts-for/gifts-her",
    "https://www.marykay.com/es/gifts/gifts-for/gifts-her",
    "https://www.marykay.com/en/skincare/product/makeup-remover",
    "https://www.marykay.com/es/skincare/product/makeup-remover",
    "https://www.marykay.com/en/makeup/face/primer",
    "https://www.marykay.com/es/makeup/face/primer",
    "https://www.marykay.com/en/makeup/face/concealer",
    "https://www.marykay.com/es/makeup/face/concealer",
    "https://www.marykay.com/en/makeup/eyes/eyeliner",
    "https://www.marykay.com/es/makeup/eyes/eyeliner",
    "https://www.marykay.com/en/makeup/eyes/mascara-lashes",
    "https://www.marykay.com/es/makeup/eyes/mascara-lashes",
    "https://www.marykay.com/en/gifts/gifts-category/pampering-gifts",
    "https://www.marykay.com/es/gifts/gifts-category/pampering-gifts",
    "https://www.marykay.com/en/gifts/price-range/dollar-15-and-under",
    "https://www.marykay.com/es/gifts/price-range/dollar-15-and-under",
    "https://www.marykay.com/en/gifts/price-range/dollar-50-and-under",
    "https://www.marykay.com/es/gifts/price-range/dollar-50-and-under",
    "https://www.marykay.com/en/discover/makeup-trends-techniques/blackberry-vinyl",
    "https://www.marykay.com/es/discover/makeup-trends-techniques/blackberry-vinyl",
    "https://www.marykay.com/en/new-products",
    "https://www.marykay.com/es/new-products",
    "https://www.marykay.com/en/gifts/gifts-category/gift-sets",
    "https://www.marykay.com/es/gifts/gifts-category/gift-sets",
    "https://www.marykay.com/en/body-sun/body-sun-concern",
    "https://www.marykay.com/es/body-sun/body-sun-concern",
    "https://www.marykay.com/en/discover/virtual-beauty-tools/mirrorme",
    "https://www.marykay.com/es/discover/virtual-beauty-tools/mirrorme",
    "https://www.marykay.com/en/skincare/product/cleanser",
    "https://www.marykay.com/es/skincare/product/cleanser",
    "https://www.marykay.com/en/makeup/face/foundation",
    "https://www.marykay.com/es/makeup/face/foundation",
    "https://www.marykay.com/en/makeup/face/loose-powder",
    "https://www.marykay.com/es/makeup/face/loose-powder",
    "https://www.marykay.com/en/makeup/cheeks/blush",
    "https://www.marykay.com/es/makeup/cheeks/blush",
    "https://www.marykay.com/en/makeup/makeup-tools/custom-palettes",
    "https://www.marykay.com/es/makeup/makeup-tools/custom-palettes",
    "https://www.marykay.com/en/body-sun/body-sun-concern/hand-care",
    "https://www.marykay.com/es/body-sun/body-sun-concern/hand-care",
    "https://www.marykay.com/en/fragrance/scent/floral",
    "https://www.marykay.com/es/fragrance/scent/floral",
    "https://www.marykay.com/en/fragrance/scent/masculine",
    "https://www.marykay.com/es/fragrance/scent/masculine",
    "https://www.marykay.com/en/gifts/gifts-category/gifts-category-tools",
    "https://www.marykay.com/es/gifts/gifts-category/gifts-category-tools",
    "https://www.marykay.com/en/gifts/gifts-for/gifts-him",
    "https://www.marykay.com/es/gifts/gifts-for/gifts-him",
    "https://www.marykay.com/en/gifts/price-range/dollar-25-and-under",
    "https://www.marykay.com/es/gifts/price-range/dollar-25-and-under",
    "https://www.marykay.com/en/discover/makeup-trends-techniques",
    "https://www.marykay.com/es/discover/makeup-trends-techniques",
    "https://www.marykay.com/en/body-sun/body-sun-product-type",
    "https://www.marykay.com/es/body-sun/body-sun-product-type",
    "https://www.marykay.com/en/gifts/gifts-category/gifts-category-skin-care",
    "https://www.marykay.com/es/gifts/gifts-category/gifts-category-skin-care",
    "https://www.marykay.com/en/gifts/gifts-category/gifts-category-fragrance",
    "https://www.marykay.com/es/gifts/gifts-category/gifts-category-fragrance",
    "https://www.marykay.com/en/gifts/gifts-for/gifts-teens",
    "https://www.marykay.com/es/gifts/gifts-for/gifts-teens",
    "https://www.marykay.com/en/discover",
    "https://www.marykay.com/es/discover",
    "https://www.marykay.com/en/be-a-beauty-consultant",
    "https://www.marykay.com/es/be-a-beauty-consultant",
    "https://www.marykay.com/en/discover/love-your-skin/ingredient-glossary",
    "https://www.marykay.com/es/discover/love-your-skin/ingredient-glossary",
    "https://www.marykay.com/en/skincare",
    "https://www.marykay.com/es/skincare",
    "https://www.marykay.com/en/skincare/collection",
    "https://www.marykay.com/es/skincare/collection",
    "https://www.marykay.com/en/skincare/collection/mary-kay-skin-care",
    "https://www.marykay.com/es/skincare/collection/mary-kay-skin-care",
    "https://www.marykay.com/en/skincare/collection/timewise",
    "https://www.marykay.com/es/skincare/collection/timewise",
    "https://www.marykay.com/en/skincare/collection/clear-proof",
    "https://www.marykay.com/es/skincare/collection/clear-proof",
    "https://www.marykay.com/en/skincare/collection/satin-collection",
    "https://www.marykay.com/es/skincare/collection/satin-collection",
    "https://www.marykay.com/en/skincare/collection/mk-men",
    "https://www.marykay.com/es/skincare/collection/mk-men",
    "https://www.marykay.com/en/skincare/collection/clinical-solutions",
    "https://www.marykay.com/es/skincare/collection/clinical-solutions",
    "https://www.marykay.com/en/skincare/concern/age-fighting",
    "https://www.marykay.com/es/skincare/concern/age-fighting",
    "https://www.marykay.com/en/skincare/concern/advanced-age-fighting",
    "https://www.marykay.com/es/skincare/concern/advanced-age-fighting",
    "https://www.marykay.com/en/skincare/concern/skin-care-concern-moisturizing",
    "https://www.marykay.com/es/skincare/concern/skin-care-concern-moisturizing",
    "https://www.marykay.com/en/skincare/concern/sensitive-skin",
    "https://www.marykay.com/es/skincare/concern/sensitive-skin",
    "https://www.marykay.com/en/skincare/concern/blemishes-acne",
    "https://www.marykay.com/es/skincare/concern/blemishes-acne",
    "https://www.marykay.com/en/skincare/concern/skin-care-concern-sun-care",
    "https://www.marykay.com/es/skincare/concern/skin-care-concern-sun-care",
    "https://www.marykay.com/en/mens/mens-skincare",
    "https://www.marykay.com/es/mens/mens-skincare",
    "https://www.marykay.com/en/skincare/product",
    "https://www.marykay.com/es/skincare/product",
    "https://www.marykay.com/en/makeup",
    "https://www.marykay.com/es/makeup",
    "https://www.marykay.com/en/makeup/face",
    "https://www.marykay.com/es/makeup/face",
    "https://www.marykay.com/en/makeup/eyes",
    "https://www.marykay.com/es/makeup/eyes",
    "https://www.marykay.com/en/makeup/cheeks",
    "https://www.marykay.com/es/makeup/cheeks",
    "https://www.marykay.com/en/makeup/lips",
    "https://www.marykay.com/es/makeup/lips",
    "https://www.marykay.com/en/makeup/makeup-tools",
    "https://www.marykay.com/es/makeup/makeup-tools",
    "https://www.marykay.com/en/fragrance/womens-collection",
    "https://www.marykay.com/es/fragrance/womens-collection",
    "https://www.marykay.com/en/gifts/price-range",
    "https://www.marykay.com/es/gifts/price-range",
    "https://www.marykay.com/en/body-sun/body-sun-concern/sun",
    "https://www.marykay.com/es/body-sun/body-sun-concern/sun",
    "https://www.marykay.com/en/body-sun/body-sun-product-type/body-wash-shower-gel",
    "https://www.marykay.com/es/body-sun/body-sun-product-type/body-wash-shower-gel",
    "https://www.marykay.com/en/discover/love-your-skin",
    "https://www.marykay.com/es/discover/love-your-skin",
    "https://www.marykay.com/en/discover/love-your-skin/build-a-skin-care-routine",
    "https://www.marykay.com/es/discover/love-your-skin/build-a-skin-care-routine",
    "https://www.marykay.com/en/gifts",
    "https://www.marykay.com/es/gifts",
    "https://www.marykay.com/en/skincare/product/exfoliator",
    "https://www.marykay.com/es/skincare/product/exfoliator",
    "https://www.marykay.com/en/body-sun/body-sun-concern/cleansing",
    "https://www.marykay.com/es/body-sun/body-sun-concern/cleansing",
    "https://www.marykay.com/en/body-sun/body-sun-concern/foot-care",
    "https://www.marykay.com/es/body-sun/body-sun-concern/foot-care",
    "https://www.marykay.com/en/discover/makeup-trends-techniques/saharan-dusk",
    "https://www.marykay.com/es/discover/makeup-trends-techniques/saharan-dusk",
    "https://www.marykay.com/en/discover/virtual-beauty-tools/foundation-finder",
    "https://www.marykay.com/es/discover/virtual-beauty-tools/foundation-finder",
    "https://www.marykay.com/en/best-sellers",
    "https://www.marykay.com/es/best-sellers",
    "https://www.marykay.com/en/discover/makeup-trends-techniques/how-to-strawberry-makeup",
    "https://www.marykay.com/es/discover/makeup-trends-techniques/how-to-strawberry-makeup",
    "https://www.marykay.com/en/body-sun",
    "https://www.marykay.com/es/body-sun",
    "https://www.marykay.com/en/fragrance",
    "https://www.marykay.com/es/fragrance",
    "https://www.marykay.com/en/mens",
    "https://www.marykay.com/es/mens",
    "https://www.marykay.com/en/gifts/gifts-for",
    "https://www.marykay.com/es/gifts/gifts-for",
    "https://www.marykay.com/en/skincare/product/skin-care-essentials",
    "https://www.marykay.com/es/skincare/product/skin-care-essentials",
    "https://www.marykay.com/en/skincare/product/targeted-solutions",
    "https://www.marykay.com/es/skincare/product/targeted-solutions",
    "https://www.marykay.com/en/makeup/face/cc-cream",
    "https://www.marykay.com/es/makeup/face/cc-cream",
    "https://www.marykay.com/en/makeup/cheeks/contour-and-highlight",
    "https://www.marykay.com/es/makeup/cheeks/contour-and-highlight",
    "https://www.marykay.com/en/makeup/lips/lip-liner",
    "https://www.marykay.com/es/makeup/lips/lip-liner",
    "https://www.marykay.com/en/makeup/lips/lip-balm",
    "https://www.marykay.com/es/makeup/lips/lip-balm",
    "https://www.marykay.com/en/body-sun/body-sun-concern/body-sun-concern-age-fighting",
    "https://www.marykay.com/es/body-sun/body-sun-concern/body-sun-concern-age-fighting",
    "https://www.marykay.com/en/body-sun/body-sun-product-type/lotion-cream",
    "https://www.marykay.com/es/body-sun/body-sun-product-type/lotion-cream",
    "https://www.marykay.com/en/fragrance/scent/woody",
    "https://www.marykay.com/es/fragrance/scent/woody",
    "https://www.marykay.com/en/fragrance/scent",
    "https://www.marykay.com/es/fragrance/scent",
    "https://www.marykay.com/en/gifts/gifts-category",
    "https://www.marykay.com/es/gifts/gifts-category",
    "https://www.marykay.com/en/skincare/product/serum-and-oil",
    "https://www.marykay.com/es/skincare/product/serum-and-oil",
    "https://www.marykay.com/en/skincare/product/skin-care-product-type-moisturizer",
    "https://www.marykay.com/es/skincare/product/skin-care-product-type-moisturizer",
    "https://www.marykay.com/en/skincare/product/sets",
    "https://www.marykay.com/es/skincare/product/sets",
    "https://www.marykay.com/en/makeup/cheeks/make-up-cheeks-tools",
    "https://www.marykay.com/es/makeup/cheeks/make-up-cheeks-tools",
    "https://www.marykay.com/en/makeup/makeup-tools/brushes",
    "https://www.marykay.com/es/makeup/makeup-tools/brushes",
    "https://www.marykay.com/en/makeup/makeup-tools/travel-bag",
    "https://www.marykay.com/es/makeup/makeup-tools/travel-bag",
    "https://www.marykay.com/en/body-sun/body-sun-product-type/body-care-essentials",
    "https://www.marykay.com/es/body-sun/body-sun-product-type/body-care-essentials",
    "https://www.marykay.com/en/skincare/product/toner-freshener",
    "https://www.marykay.com/es/skincare/product/toner-freshener",
    "https://www.marykay.com/en/makeup/face/make-up-face-tools",
    "https://www.marykay.com/es/makeup/face/make-up-face-tools",
    "https://www.marykay.com/en/makeup/eyes/eye-shadow",
    "https://www.marykay.com/es/makeup/eyes/eye-shadow",
    "https://www.marykay.com/en/makeup/eyes/brows",
    "https://www.marykay.com/es/makeup/eyes/brows",
    "https://www.marykay.com/en/makeup/eyes/make-up-eyes-tools",
    "https://www.marykay.com/es/makeup/eyes/make-up-eyes-tools",
    "https://www.marykay.com/en/body-sun/body-sun-concern/dryness",
    "https://www.marykay.com/es/body-sun/body-sun-concern/dryness",
    "https://www.marykay.com/en/body-sun/body-sun-product-type/set",
    "https://www.marykay.com/es/body-sun/body-sun-product-type/set",
    "https://www.marykay.com/en/skincare/collection/timewise-repair",
    "https://www.marykay.com/es/skincare/collection/timewise-repair",
    "https://www.marykay.com/en/skincare/concern",
    "https://www.marykay.com/es/skincare/concern",
    "https://www.marykay.com/en/gifts/gifts-category/gifts-category-makeup",
    "https://www.marykay.com/es/gifts/gifts-category/gifts-category-makeup",
    "https://www.marykay.com/en/discover/virtual-beauty-tools/interactive-catalog",
    "https://www.marykay.com/es/discover/virtual-beauty-tools/interactive-catalog",
    "https://www.marykay.com/en/award-winners",
    "https://www.marykay.com/es/award-winners",
    "https://www.marykay.com/en/skincare/product/mask",
    "https://www.marykay.com/es/skincare/product/mask",
    "https://www.marykay.com/en/makeup/makeup-tools/sponges",
    "https://www.marykay.com/es/makeup/makeup-tools/sponges",
    "https://www.marykay.com/en/fragrance/scent/fruity",
    "https://www.marykay.com/es/fragrance/scent/fruity",
    "https://www.marykay.com/en/discover/makeup-trends-techniques/how-to-glass-lips",
    "https://www.marykay.com/es/discover/makeup-trends-techniques/how-to-glass-lips",
    "https://www.marykay.com/en/discover/makeup-trends-techniques/all-eyes-on-hue",
    "https://www.marykay.com/es/discover/makeup-trends-techniques/all-eyes-on-hue",
    "https://www.marykay.com/en/fragrance/mens-collection",
    "https://www.marykay.com/es/fragrance/mens-collection",
    "https://www.marykay.com/en/skincare/product/eye-care",
    "https://www.marykay.com/es/skincare/product/eye-care",
    "https://www.marykay.com/en/makeup/eyes/eyes-makeup-remover",
    "https://www.marykay.com/es/makeup/eyes/eyes-makeup-remover",
    "https://www.marykay.com/en/makeup/lips/lipstick",
    "https://www.marykay.com/es/makeup/lips/lipstick",
    "https://www.marykay.com/en/makeup/lips/lip-gloss",
    "https://www.marykay.com/es/makeup/lips/lip-gloss",
    "https://www.marykay.com/en/body-sun/body-sun-concern/firming",
    "https://www.marykay.com/es/body-sun/body-sun-concern/firming",
    "https://www.marykay.com/en/discover/love-your-skin/skin-care-101",
    "https://www.marykay.com/es/discover/love-your-skin/skin-care-101",
    "https://www.marykay.com/en/discover/about-mary-kay",
    "https://www.marykay.com/es/discover/about-mary-kay",
    "https://www.marykay.com/en/discover/virtual-beauty-tools",
    "https://www.marykay.com/es/discover/virtual-beauty-tools",
    "https://www.marykay.com/en/discover/love-your-skin/what-skin-type-am-i",
    "https://www.marykay.com/es/discover/love-your-skin/what-skin-type-am-i",
    "https://www.marykay.com/en/what-skin-type-am-i.html",
    "https://www.marykay.com/es/what-skin-type-am-i.html",
    "https://www.marykay.com/en/discover.html",
    "https://www.marykay.com/es/discover.html",
    "https://www.marykay.com/en/build-a-skin-care-routine.html",
    "https://www.marykay.com/es/build-a-skin-care-routine.html",
    "https://www.marykay.com/en/ingredient-glossary.html",
    "https://www.marykay.com/es/ingredient-glossary.html",
    "https://www.marykay.com/en/contact-us.html",
    "https://www.marykay.com/es/contact-us.html",
    "https://www.marykay.com/en/foundation-finder.html",
    "https://www.marykay.com/es/foundation-finder.html",
    "https://www.marykay.com/en/mirrorme.html",
    "https://www.marykay.com/es/mirrorme.html",
    "https://www.marykay.com/en/be-a-beauty-consultant.html",
    "https://www.marykay.com/es/be-a-beauty-consultant.html",
    "https://www.marykay.com/en/skin-care-101.html",
    "https://www.marykay.com/es/skin-care-101.html",
    "https://www.marykay.com/en/about-mary-kay.html",
    "https://www.marykay.com/es/about-mary-kay.html",
    "https://www.marykay.com/en/blackberry-vinyl.html",
    "https://www.marykay.com/es/blackberry-vinyl.html",
    "https://www.marykay.com/en/all-eyes-on-hue.html",
    "https://www.marykay.com/es/all-eyes-on-hue.html",
    "https://www.marykay.com/en/saharan-dusk.html",
    "https://www.marykay.com/es/saharan-dusk.html",
    "https://www.marykay.com/en/how-to-glass-lips.html",
    "https://www.marykay.com/es/how-to-glass-lips.html",
    "https://www.marykay.com/en/how-to-strawberry-makeup.html",
    "https://www.marykay.com/es/how-to-strawberry-makeup.html",
    "https://www.marykay.com/en/home",
    "https://www.marykay.com/es/home",
]

# ── URL Utilities ──────────────────────────────────────────────────────────────

def normalize_url(url: str) -> str:
    """Strip tracking params, fragments, trailing slashes."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    filtered = {k: v for k, v in params.items()
                if k.lower() not in TRACKING_PARAMS}
    clean_query = urlencode(filtered, doseq=True)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}" + (f"?{clean_query}" if clean_query else "")


def is_allowed(url: str) -> bool:
    """Check URL against robots.txt rules."""
    parsed = urlparse(url)
    path = parsed.path.lower()
    for disallowed in DISALLOWED_PATHS:
        if path.startswith(disallowed.lower()):
            return False
    query = parsed.query.lower()
    for param in DISALLOWED_PARAMS:
        if param in query:
            return False
    return True


def classify_url(url: str) -> str:
    """Classify URL into page type."""
    path = urlparse(url).path.lower()
    # Product pages have SKU-like IDs (e.g., /4US.html, /163122US.html)
    if re.search(r'/\d+US', path, re.IGNORECASE) or path.endswith('.html') and re.search(r'/[A-Za-z0-9-]+/\d', path):
        return "product"
    if "/discover/" in path or "how-to" in path or "skin-care-101" in path or "about-mary-kay" in path:
        return "content"
    if "/gifts/" in path or "/new-products" in path or "/best-sellers" in path or "/award-winners" in path:
        return "category"
    if any(x in path for x in ["/skincare/", "/makeup/", "/fragrance/", "/body-sun/", "/mens/"]):
        if path.count("/") <= 4 and not re.search(r'/\d+US', path):
            return "category"
        return "product"
    if "home" in path:
        return "content"
    return "other"


def get_locale(url: str) -> str:
    """Extract locale from URL path."""
    path = urlparse(url).path
    if path.startswith("/es/") or path.startswith("/es"):
        return "es_US"
    return "en_US"


# ── HTML Parsing ───────────────────────────────────────────────────────────────

def parse_page(url: str, html: str, response_headers: dict) -> dict:
    """Parse HTML into structured record."""
    soup = BeautifulSoup(html, "lxml")
    record = {
        "url": url,
        "canonical_url": "",
        "title": "",
        "meta_description": "",
        "breadcrumbs": [],
        "h1": "",
        "headings": [],
        "main_text": "",
        "product_fields": {
            "name": "",
            "price": "",
            "size": "",
            "shade_options": [],
            "key_benefits": [],
            "ingredients": [],
            "how_to_use": "",
            "warnings": "",
            "category": ""
        },
        "faq_pairs": [],
        "images": [],
        "language": "",
        "locale": get_locale(url),
        "last_modified": "",
        "crawl_timestamp": datetime.now(timezone.utc).isoformat(),
        "content_hash": "",
        "internal_links": [],
        "outbound_links": []
    }

    # Canonical URL
    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        record["canonical_url"] = canonical["href"]
    else:
        record["canonical_url"] = url

    # Title
    title_tag = soup.find("title")
    if title_tag:
        record["title"] = title_tag.get_text(strip=True)

    # Meta description
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        record["meta_description"] = meta_desc["content"].strip()

    # Language
    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        record["language"] = html_tag["lang"]

    # H1
    h1 = soup.find("h1")
    if h1:
        record["h1"] = h1.get_text(strip=True)

    # All headings h2-h6
    for level in range(2, 7):
        for h in soup.find_all(f"h{level}"):
            text = h.get_text(strip=True)
            if text:
                record["headings"].append({"level": level, "text": text})

    # Breadcrumbs
    breadcrumb_nav = soup.find("nav", attrs={"aria-label": re.compile(r"breadcrumb", re.I)})
    if not breadcrumb_nav:
        breadcrumb_nav = soup.find("ol", class_=re.compile(r"breadcrumb", re.I))
    if not breadcrumb_nav:
        breadcrumb_nav = soup.find(attrs={"class": re.compile(r"breadcrumb", re.I)})
    if breadcrumb_nav:
        for li in breadcrumb_nav.find_all("li"):
            text = li.get_text(strip=True)
            if text:
                record["breadcrumbs"].append(text)

    # Main text — try main content area, fall back to body
    main_content = (soup.find("main") or soup.find("div", id="maincontent")
                    or soup.find("div", class_=re.compile(r"main-content|page-content|pdp-main", re.I))
                    or soup.find("div", role="main"))
    if not main_content:
        main_content = soup.find("body")

    if main_content:
        # Remove nav, footer, header, script, style
        for tag in main_content.find_all(["nav", "footer", "header", "script",
                                          "style", "noscript", "iframe"]):
            tag.decompose()
        text = main_content.get_text(separator="\n", strip=True)
        # Collapse multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        record["main_text"] = text.strip()

    # Content hash
    record["content_hash"] = hashlib.sha256(record["main_text"].encode()).hexdigest()

    # Last modified
    record["last_modified"] = response_headers.get("last-modified", "")

    # Images in main content area
    img_container = (soup.find("main") or soup.find("div", id="maincontent")
                     or soup.find("body"))
    if img_container:
        for img in img_container.find_all("img", src=True)[:20]:  # limit to 20
            src = img.get("src", "")
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = BASE_URL + src
            alt = img.get("alt", "")
            if src and not src.startswith("data:"):
                record["images"].append({"src": src, "alt": alt})

    # Links
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
            continue
        if href.startswith("/"):
            href = BASE_URL + href
        if href.startswith("//"):
            href = "https:" + href
        normalized = normalize_url(href)
        parsed = urlparse(normalized)
        if parsed.netloc and "marykay.com" in parsed.netloc:
            if normalized not in record["internal_links"]:
                record["internal_links"].append(normalized)
        elif parsed.scheme in ("http", "https"):
            if normalized not in record["outbound_links"]:
                record["outbound_links"].append(normalized)

    # ── Product-specific fields ──
    parse_product_fields(soup, record)

    # ── FAQ pairs ──
    parse_faq(soup, record)

    return record


def parse_product_fields(soup: BeautifulSoup, record: dict):
    """Extract product-specific fields from schema.org or page elements."""
    pf = record["product_fields"]

    # Try schema.org JSON-LD first
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                data = data[0] if data else {}
            if data.get("@type") == "Product":
                pf["name"] = data.get("name", "")
                offers = data.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                pf["price"] = str(offers.get("price", ""))
                pf["size"] = data.get("size", "")
                if data.get("description"):
                    pf["key_benefits"] = [data["description"]]
                break
        except (json.JSONDecodeError, TypeError):
            continue

    # Fallback: product name from specific elements
    if not pf["name"]:
        name_el = (soup.find(class_=re.compile(r"product-name|pdp-product-name", re.I))
                   or soup.find("h1", class_=re.compile(r"product", re.I)))
        if name_el:
            pf["name"] = name_el.get_text(strip=True)
        elif record["h1"]:
            pf["name"] = record["h1"]

    # Price fallback
    if not pf["price"]:
        price_el = soup.find(class_=re.compile(r"price-sales|product-price|pdp-price", re.I))
        if price_el:
            pf["price"] = price_el.get_text(strip=True)

    # Shade options
    shade_container = soup.find(class_=re.compile(r"shade|color|swatch", re.I))
    if shade_container:
        for opt in shade_container.find_all(["button", "li", "span", "a"]):
            shade_name = opt.get("title") or opt.get("aria-label") or opt.get_text(strip=True)
            if shade_name and shade_name not in pf["shade_options"]:
                pf["shade_options"].append(shade_name)

    # Benefits
    benefits_section = soup.find(class_=re.compile(r"benefit|key-benefit", re.I))
    if benefits_section and not pf["key_benefits"]:
        for li in benefits_section.find_all("li"):
            text = li.get_text(strip=True)
            if text:
                pf["key_benefits"].append(text)

    # Ingredients
    ingredients_section = soup.find(class_=re.compile(r"ingredient", re.I))
    if not ingredients_section:
        ingredients_section = soup.find(id=re.compile(r"ingredient", re.I))
    if ingredients_section:
        text = ingredients_section.get_text(strip=True)
        if text:
            pf["ingredients"] = [i.strip() for i in re.split(r'[,;]', text) if i.strip()]

    # How to use
    how_to_section = soup.find(class_=re.compile(r"how-to|usage|directions", re.I))
    if not how_to_section:
        how_to_section = soup.find(id=re.compile(r"how-to|usage", re.I))
    if how_to_section:
        pf["how_to_use"] = how_to_section.get_text(strip=True)

    # Warnings
    warnings_section = soup.find(class_=re.compile(r"warning|caution", re.I))
    if warnings_section:
        pf["warnings"] = warnings_section.get_text(strip=True)

    # Category from breadcrumbs
    if record["breadcrumbs"] and len(record["breadcrumbs"]) >= 2:
        pf["category"] = " > ".join(record["breadcrumbs"][:-1])

    # Size
    if not pf["size"]:
        size_el = soup.find(class_=re.compile(r"product-size|size", re.I))
        if size_el:
            pf["size"] = size_el.get_text(strip=True)


def parse_faq(soup: BeautifulSoup, record: dict):
    """Extract FAQ pairs from schema.org or accordion patterns."""
    # Schema.org FAQ
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                for item in data:
                    if item.get("@type") == "FAQPage":
                        for qa in item.get("mainEntity", []):
                            q = qa.get("name", "")
                            a = qa.get("acceptedAnswer", {}).get("text", "")
                            if q and a:
                                record["faq_pairs"].append({"question": q, "answer": a})
            elif data.get("@type") == "FAQPage":
                for qa in data.get("mainEntity", []):
                    q = qa.get("name", "")
                    a = qa.get("acceptedAnswer", {}).get("text", "")
                    if q and a:
                        record["faq_pairs"].append({"question": q, "answer": a})
        except (json.JSONDecodeError, TypeError):
            continue

    # Fallback: accordion patterns
    if not record["faq_pairs"]:
        accordions = soup.find_all(class_=re.compile(r"accordion|faq|collapse", re.I))
        for acc in accordions:
            questions = acc.find_all(class_=re.compile(r"question|accordion-header|panel-title", re.I))
            answers = acc.find_all(class_=re.compile(r"answer|accordion-body|panel-body|collapse", re.I))
            for q, a in zip(questions, answers):
                qt = q.get_text(strip=True)
                at = a.get_text(strip=True)
                if qt and at:
                    record["faq_pairs"].append({"question": qt, "answer": at})


# ── Async Fetcher ──────────────────────────────────────────────────────────────

async def fetch_url(client: httpx.AsyncClient, url: str, semaphore: asyncio.Semaphore) -> tuple:
    """Fetch a URL with rate limiting and retry."""
    async with semaphore:
        for attempt in range(MAX_RETRIES):
            try:
                await asyncio.sleep(CRAWL_DELAY)
                response = await client.get(url, follow_redirects=True, timeout=TIMEOUT)
                return url, response.status_code, response.text, dict(response.headers)
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait = (2 ** attempt) * 1.0
                    await asyncio.sleep(wait)
                else:
                    return url, 0, "", {"error": str(e)}
    return url, 0, "", {"error": "max retries exceeded"}


# ── Pipeline ───────────────────────────────────────────────────────────────────

async def crawl(urls: list, output_path: Path, mode: str = "full") -> dict:
    """Main crawl pipeline. Returns crawl stats."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stats = {
        "total_urls_discovered": len(urls),
        "total_urls_crawled": 0,
        "total_urls_skipped": 0,
        "total_duplicates_removed": 0,
        "success_count": 0,
        "error_count": 0,
        "errors_by_status_code": {},
        "avg_response_time_ms": 0,
        "crawl_start": datetime.now(timezone.utc).isoformat(),
        "crawl_end": "",
        "crawl_duration_seconds": 0,
        "pages_by_type": {
            "product": 0,
            "category": 0,
            "content": 0,
            "faq": 0,
            "other": 0,
        },
        "mode": mode,
    }

    # Filter allowed URLs
    allowed_urls = [u for u in urls if is_allowed(u)]
    stats["total_urls_skipped"] = len(urls) - len(allowed_urls)

    seen_hashes = set()
    records = []
    response_times = []
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
    }

    start_time = time.time()

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        # Process in batches
        batch_size = MAX_CONCURRENT
        for i in range(0, len(allowed_urls), batch_size):
            batch = allowed_urls[i:i + batch_size]
            tasks = [fetch_url(client, url, semaphore) for url in batch]

            t0 = time.time()
            results = await asyncio.gather(*tasks)
            elapsed = (time.time() - t0) * 1000

            for url, status, html, resp_headers in results:
                stats["total_urls_crawled"] += 1
                response_times.append(elapsed / len(batch))

                if status == 200 and html:
                    stats["success_count"] += 1
                    record = parse_page(url, html, resp_headers)
                    page_type = classify_url(url)
                    stats["pages_by_type"][page_type] = stats["pages_by_type"].get(page_type, 0) + 1

                    # Dedup by content hash
                    if record["content_hash"] not in seen_hashes:
                        seen_hashes.add(record["content_hash"])
                        records.append(record)
                    else:
                        stats["total_duplicates_removed"] += 1
                else:
                    stats["error_count"] += 1
                    code_str = str(status) if status else "connection_error"
                    stats["errors_by_status_code"][code_str] = stats["errors_by_status_code"].get(code_str, 0) + 1

                # Progress
                pct = stats["total_urls_crawled"] / len(allowed_urls) * 100
                print(f"  [{stats['total_urls_crawled']}/{len(allowed_urls)}] ({pct:.0f}%) {url[:80]}... {'OK' if status == 200 else f'ERR:{status}'}")

    end_time = time.time()
    stats["crawl_end"] = datetime.now(timezone.utc).isoformat()
    stats["crawl_duration_seconds"] = round(end_time - start_time, 1)
    stats["avg_response_time_ms"] = round(sum(response_times) / len(response_times), 1) if response_times else 0

    # Write JSONL
    with open(output_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\nWrote {len(records)} records to {output_path}")
    return stats, records


# ── Deliverable Generators ─────────────────────────────────────────────────────

def write_url_index(records: list, path: Path):
    """Generate url_index.csv."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "canonical_url", "title", "content_hash", "locale", "page_type"])
        for r in records:
            writer.writerow([
                r["url"], r["canonical_url"], r["title"],
                r["content_hash"], r["locale"], classify_url(r["url"])
            ])


def write_crawl_report(stats: dict, path: Path):
    """Write crawl_report.json."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)


def write_qa_samples(records: list, path: Path, n: int = 10):
    """Select n diverse QA sample records."""
    samples = []
    types_seen = set()
    # Pick one of each type first
    for r in records:
        ptype = classify_url(r["url"])
        if ptype not in types_seen:
            types_seen.add(ptype)
            samples.append(r)
        if len(samples) >= n:
            break
    # Fill rest evenly
    if len(samples) < n:
        for r in records:
            if r not in samples:
                samples.append(r)
            if len(samples) >= n:
                break

    with open(path, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)
    return samples


def write_compliance(path: Path):
    """Document compliance constraints."""
    compliance = {
        "robots_txt_url": "https://www.marykay.com/robots.txt",
        "crawl_delay_specified": False,
        "crawl_delay_used_seconds": CRAWL_DELAY,
        "user_agent": USER_AGENT,
        "disallowed_paths": DISALLOWED_PATHS,
        "disallowed_params": DISALLOWED_PARAMS,
        "sitemap_url": "https://www.marykay.com/sitemap_index.xml",
        "total_sitemap_urls": len(SITEMAP_URLS),
        "private_data_collected": False,
        "login_bypass_attempted": False,
        "captcha_bypass_attempted": False,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(compliance, f, indent=2, ensure_ascii=False)


# ── Main ───────────────────────────────────────────────────────────────────────

async def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Write compliance doc
    print("=" * 60)
    print("PHASE 0: Writing compliance documentation...")
    write_compliance(OUTPUT_DIR / "compliance.json")
    print(f"  Written: {OUTPUT_DIR / 'compliance.json'}")

    # Phase 1: Seed list
    print("\n" + "=" * 60)
    print("PHASE 1: Building seed URL list...")
    seed_path = OUTPUT_DIR / "seed_urls.csv"
    with open(seed_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "type", "locale", "priority"])
        for url in SITEMAP_URLS:
            writer.writerow([url, classify_url(url), get_locale(url), "0.5"])
    print(f"  {len(SITEMAP_URLS)} URLs written to {seed_path}")

    # Phase 4: Pilot crawl (50 pages)
    print("\n" + "=" * 60)
    print("PHASE 4: PILOT CRAWL (50 pages)...")
    # Select a diverse 50-page pilot set (25 en + 25 es won't help — pick 50 en for diversity)
    en_urls = [u for u in SITEMAP_URLS if "/en/" in u]
    pilot_urls = en_urls[:50]
    pilot_stats, pilot_records = await crawl(
        pilot_urls, OUTPUT_DIR / "pilot_documents.jsonl", mode="pilot"
    )
    write_crawl_report(pilot_stats, OUTPUT_DIR / "pilot_crawl_report.json")
    print(f"\n  Pilot stats: {pilot_stats['success_count']} OK, {pilot_stats['error_count']} errors, "
          f"{pilot_stats['total_duplicates_removed']} dupes removed")

    # Phase 5: Full crawl (all URLs)
    print("\n" + "=" * 60)
    print("PHASE 5: FULL CRAWL (all URLs)...")
    full_stats, full_records = await crawl(
        SITEMAP_URLS, OUTPUT_DIR / "documents.jsonl", mode="full"
    )

    # Phase 6: QC & Deliverables
    print("\n" + "=" * 60)
    print("PHASE 6: QC & DELIVERABLES...")
    write_crawl_report(full_stats, OUTPUT_DIR / "crawl_report.json")
    write_url_index(full_records, OUTPUT_DIR / "url_index.csv")
    write_qa_samples(full_records, OUTPUT_DIR / "qa_samples.json")

    print(f"\n  Final stats:")
    print(f"    Total URLs discovered: {full_stats['total_urls_discovered']}")
    print(f"    Total crawled:         {full_stats['total_urls_crawled']}")
    print(f"    Successful:            {full_stats['success_count']}")
    print(f"    Errors:                {full_stats['error_count']}")
    print(f"    Duplicates removed:    {full_stats['total_duplicates_removed']}")
    print(f"    Duration:              {full_stats['crawl_duration_seconds']}s")
    print(f"    Records in corpus:     {len(full_records)}")

    print("\n  Deliverables:")
    for f in OUTPUT_DIR.iterdir():
        size = f.stat().st_size
        print(f"    {f.name:40s} {size:>10,} bytes")

    print("\n" + "=" * 60)
    print("CRAWL COMPLETE")
    return full_stats, full_records


if __name__ == "__main__":
    asyncio.run(main())
