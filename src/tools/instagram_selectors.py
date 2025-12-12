"""Instagram DOM selectors."""

from selenium.webdriver.common.by import By

# --- Basic UI / login heuristics ---
# Profile icon heuristic for logged-in state.
PROFILE_ICON = (
    By.CSS_SELECTOR,
    "img[alt*='profile picture'], span[role='link'] img[alt*='profile']",
)

# --- Create / upload entrypoint ---
# "Create"/"New post" button in navbar (SVG icon, often wrapped in button).
CREATE_BUTTON = (
    By.CSS_SELECTOR,
    "button svg[aria-label='New post'], "
    "button svg[aria-label='Create'], "
    "svg[aria-label='New post'], "
    "svg[aria-label='Create']",
)

# File input for upload dialog.
FILE_INPUT = (By.CSS_SELECTOR, "input[type='file']")

# --- Post flow navigation ---
# "Next" button across post steps (crop/filter/caption) - includes divs and spans.
NEXT_BUTTON = (
    By.XPATH,
    "//button[normalize-space()='Next'] | "
    "//div[normalize-space()='Next']/parent::button | "
    "//div[normalize-space()='Next' and @role='button'] | "
    "//span[normalize-space()='Next'] | "
    "//div[contains(text(), 'Next') and contains(@class, 'x1qjc9v5')] | "
    "//*[text()='Next' and (contains(@class, 'x1qjc9v5') or contains(@class, 'x1lliihq'))]",
)

# --- Caption and metadata ---
# Caption textarea/editor (locale variants for ellipsis).
CAPTION_AREA = (
    By.XPATH,
    "//textarea[@aria-label='Write a caption…' or @aria-label='Write a caption...'] | "
    "//div[@aria-label='Write a caption…' or @aria-label='Write a caption...']",
)

# --- Share / confirmation ---
# "Share" button in final step (various text variations - includes divs for Instagram's complex structure).
SHARE_BUTTON = (
    By.XPATH,
    "//button[normalize-space()='Share'] | "
    "//button[normalize-space()='Post'] | "
    "//div[normalize-space()='Share']/parent::button | "
    "//div[normalize-space()='Post']/parent::button | "
    "//button[contains(., 'Share')] | "
    "//button[contains(., 'Post')] | "
    # Instagram uses clickable divs with SVG icons and text spans
    "//div[.//svg[@aria-label='Post']] | "
    "//div[contains(., 'Post') and @role='button'] | "
    "//div[.//span[contains(text(), 'Post')]] | "
    "//div[contains(@class, 'x1qjc9v5') and .//span[contains(text(), 'Post')]] | "
    "//div[contains(@class, 'x1diwwjn') and .//span[contains(text(), 'Post')]] | "
    # Specific selector for the Post div with exact class combination
    "//div[contains(@class, 'x1qjc9v5') and text()='Post'] | "
    "//div[contains(@class, 'html-div') and contains(@class, 'x1qjc9v5') and text()='Post']",
)

# Confirmation heuristic for successful post.
UPLOAD_PROGRESS_DONE = (
    By.XPATH,
    "//*[contains(., 'Your post has been shared') or contains(., 'Post shared')]",
)

