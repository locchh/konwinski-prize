from selenium.webdriver.chrome.options import Options


def get_headless_options() -> Options:
    """
    Get headless options for Chrome.
    """
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("window-size=1400,2000")
    return options