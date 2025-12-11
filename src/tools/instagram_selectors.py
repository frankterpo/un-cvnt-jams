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
# "Next" button across post steps (crop/filter/caption).
NEXT_BUTTON = (
    By.XPATH,
    "//button[normalize-space()='Next'] | "
    "//div[normalize-space()='Next']/parent::button",
)

# --- Caption and metadata ---
# Caption textarea/editor (locale variants for ellipsis).
CAPTION_AREA = (
    By.XPATH,
    "//textarea[@aria-label='Write a caption…' or @aria-label='Write a caption...'] | "
    "//div[@aria-label='Write a caption…' or @aria-label='Write a caption...']",
)

# --- Share / confirmation ---
# "Share" button in final step.
SHARE_BUTTON = (
    By.XPATH,
    "//button[normalize-space()='Share'] | "
    "//div[normalize-space()='Share']/parent::button",
)

# Confirmation heuristic for successful post.
UPLOAD_PROGRESS_DONE = (
    By.XPATH,
    "//*[contains(., 'Your post has been shared') or contains(., 'Post shared')]",
)

