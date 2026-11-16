"""
config.py  -  THE ONLY FILE YOU NEED TO EDIT
-------------------------------------------
Brand: Eliteora  |  Premium affiliate edition (product image card)

For each product fill in:
  link        "https://bitli.in/XI4lk5w",
  image_url   - https://raw.githubusercontent.com/eliteora/eliteora-images/main/eliteora_product_square_1080.jpg
  card_title  - "Eliteora Glow Lamp",
Search for  PASTE-  to find everything you still need to replace.
Use {name} for the customer's first name and {link} for the product link.
"""

BRAND_NAME = "Eliteora"

ENABLE_INSTAGRAM = True
ENABLE_FACEBOOK = True

# Premium product card (image + title + button). If Instagram rejects the card,
# or no image is set, the plain text message is sent instead.
SEND_PRODUCT_CARD = True

# Affiliate disclosure
DISCLOSURE = (
    "\n\n— — — — — — — —\n"
    "ℹ️ Affiliate link: I may earn a small commission at no extra cost to you."
)
CARD_DISCLOSURE = "Affiliate link · may earn commission"   # shown on the card

PRODUCTS = [
    {
        "name": "Top Pick",
        "keywords": ["link", "pick", "premium"],
        "link": "https://bitli.in/XI4lk5w",
        "image_url": "image_url": "https://raw.githubusercontent.com/eliteora/eliteora-images/main/eliteora_product_square_1080.jpg",
        "card_title": "Eliteora Top Pick",
        "card_subtitle": "Hand-picked for quality & value",
        "button_text": "Shop Now",
        "dm": (
            "Hello {name}, welcome to Eliteora ✨\n\n"
            "Thank you for your interest. As requested, here is my "
            "hand-picked recommendation:\n\n"
            "🔗 {link}\n\n"
            "Selected for quality, value and everyday luxury.\n"
            "If you have any questions, simply reply here. I'm happy to help.\n\n"
            "Warm regards,\n"
            "Eliteora"
            + DISCLOSURE
        ),
        "public_replies": [
            "Thank you {name}! Your details are in your DM 📩✨",
            "Hi {name}, sent privately to your DMs 🤍",
        ],
        "media_ids": [],
    },
    {
        "name": "Exclusive Deal",
        "keywords": ["deal", "offer", "discount"],
        "link": "PASTE-YOUR-AFFILIATE-LINK-2-HERE",
        "image_url": "PASTE-YOUR-IMAGE-LINK-2-HERE",
        "card_title": "Eliteora Exclusive Deal",
        "card_subtitle": "Today's special offer",
        "button_text": "View Deal",
        "dm": (
            "Hi {name} 🤍\n\n"
            "Here is today's exclusive Eliteora offer:\n\n"
            "🔗 {link}\n\n"
            "⏳ Offers can change without notice, so I recommend "
            "checking it soon.\n\n"
            "With appreciation,\n"
            "Eliteora"
            + DISCLOSURE
        ),
        "public_replies": ["Sent to your DM, {name}! 📩"],
        "media_ids": [],
    },
    {
        "name": "New Arrivals",
        "keywords": ["new", "latest", "arrivals"],
        "link": "PASTE-YOUR-AFFILIATE-LINK-3-HERE",
        "image_url": "PASTE-YOUR-IMAGE-LINK-3-HERE",
        "card_title": "Eliteora New Arrivals",
        "card_subtitle": "Fresh picks, chosen with care",
        "button_text": "Explore",
        "dm": (
            "Hello {name} ✨\n\n"
            "Discover our latest curated finds:\n\n"
            "🔗 {link}\n\n"
            "Fresh picks, chosen with care.\n\n"
            "Eliteora | Premium, Without Borders"
            + DISCLOSURE
        ),
        "public_replies": ["Thank you {name}! Check your DMs ✨"],
        "media_ids": [],
    },
    # Copy a block above to add more products
]

# Sent when someone messages you and no keyword matches (once per person per 24h)
FALLBACK_DM = (
    "Hello {name}, welcome to Eliteora ✨\n\n"
    "Reply with a word and I'll send your link:\n\n"
    "• LINK  –  my top pick\n"
    "• DEAL  –  today's exclusive offer\n"
    "• NEW  –  latest arrivals\n\n"
    "Or type your question and I'll reply personally.\n\n"
    "Eliteora | Premium, Without Borders"
)
SEND_FALLBACK = True
