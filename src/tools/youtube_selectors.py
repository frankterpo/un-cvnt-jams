"""YouTube Studio DOM selectors."""

from selenium.webdriver.common.by import By

# --- High-level navigation ---

# Top-right "Create" button in YouTube Studio navbar (plus icon).
# We target several common variants: ytcp-button, icon-button, and generic button with aria-label.
CREATE_BUTTON = (
    By.CSS_SELECTOR,
    "ytcp-button#create-icon-button, "
    "tp-yt-paper-icon-button#create-icon-button, "
    "ytcp-icon-button#create-icon, "
    "button[aria-label*='Create'], "
    "button[aria-label*='Create shortcut']",
)

# "Upload video" menu item in the Create dropdown.
# Note: YouTube uses "Upload video" (singular), not "Upload videos".
# We use XPath to match the menu item by its visible text.
UPLOAD_MENU_ITEM = (
    By.XPATH,
    "//tp-yt-paper-item[.//yt-formatted-string[contains(text(), 'Upload video')]] | "
    "//ytcp-text-menu-item[contains(., 'Upload video')] | "
    "//*[@role='menuitem' and contains(., 'Upload video')]",
)

# --- File upload ---
# File input used by the upload dialog.
FILE_INPUT = (By.CSS_SELECTOR, "input[type='file']")

# --- Details step (title, description) ---
# Title textbox scoped to the metadata editor.
TITLE_INPUT = (
    By.CSS_SELECTOR,
    "ytcp-video-metadata-editor #title-textarea #textbox",
)

# Description textbox scoped to the metadata editor.
DESCRIPTION_INPUT = (
    By.CSS_SELECTOR,
    "ytcp-video-metadata-editor #description-textarea #textbox",
)

# --- Audience / "Made for kids" ---
# "No, it's not made for kids" radio button.
NOT_FOR_KIDS_RADIO = (
    By.CSS_SELECTOR,
    "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK'], "
    "tp-yt-paper-radio-button[aria-label*='No, it is not made for kids']",
)

# --- Stepper navigation ---
# Generic "Next" button in the stepper (text or aria-label).
NEXT_BUTTON = (
    By.XPATH,
    "//ytcp-button[@id='next-button' or @aria-label='Next']"
    " | //ytcp-button[contains(., 'Next')]"
    " | //button[contains(., 'Next')]",
)

# --- Visibility / scheduling ---
# "Public" visibility radio button.
PUBLIC_RADIO = (
    By.CSS_SELECTOR,
    "tp-yt-paper-radio-button[name='PUBLIC'], "
    "tp-yt-paper-radio-button[aria-label*='Public']",
)

# "Schedule" radio button.
SCHEDULE_RADIO = (
    By.CSS_SELECTOR,
    "tp-yt-paper-radio-button[name='SCHEDULE'], "
    "tp-yt-paper-radio-button[aria-label*='Schedule']",
)

# Date input for scheduling.
SCHEDULE_DATE_INPUT = (
    By.CSS_SELECTOR,
    "ytcp-date-picker input[type='date'], "
    "ytcp-schedule-date-picker input[type='date']",
)

# Time input for scheduling.
SCHEDULE_TIME_INPUT = (
    By.CSS_SELECTOR,
    "ytcp-time-picker input[type='time'], "
    "ytcp-schedule-time-picker input[type='time']",
)

# Final "Done" button after visibility.
DONE_BUTTON = (
    By.CSS_SELECTOR,
    "ytcp-button[id='done-button'], ytcp-button[aria-label='Done']",
)

# Chip element containing watch URL; useful to extract video ID.
VIDEO_LINK_CHIP = (
    By.CSS_SELECTOR,
    "ytcp-video-info div.video-url-fadeable a, "
    "ytcp-video-info a[aria-label*='Video link'], "
    "a[aria-label*='Video link']",
)

