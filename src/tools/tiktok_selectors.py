"""TikTok DOM selectors.

Note: TikTok currently uses the `tiktok-uploader` library wrapper,
which handles Selenium internally. This file is a placeholder for
future direct Selenium integration if needed.

If switching to direct Selenium, add selectors here following the
pattern used in youtube_selectors.py and instagram_selectors.py.
"""

from selenium.webdriver.common.by import By

# Placeholder selectors for future direct Selenium integration
# These are not currently used as TikTok uses tiktok-uploader library

# Entry / create button
CREATE_BUTTON = (
    By.CSS_SELECTOR,
    "button[aria-label*='Upload'], button[aria-label*='Create']",
)

# File input
FILE_INPUT = (By.CSS_SELECTOR, "input[type='file']")

# Caption / description input
CAPTION_INPUT = (
    By.CSS_SELECTOR,
    "textarea[aria-label*='Caption'], textarea[placeholder*='Describe']",
)

# Post button
POST_BUTTON = (
    By.CSS_SELECTOR,
    "button[aria-label*='Post'], button[aria-label*='Upload']",
)

