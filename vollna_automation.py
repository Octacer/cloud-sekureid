"""
Vollna Automation Script
This script automates login to vollna.com and extracts cookies
"""

import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class VollnaAutomation:
    def __init__(self):
        """Initialize the Vollna automation"""
        self.driver = None

    def setup_driver(self):
        """Setup Chrome/Chromium driver with options"""
        print("Setting up Chrome driver...")
        chrome_options = Options()

        # Headless mode - optimized for AWS/cloud servers without display
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
        )

        # Initialize the driver
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.set_page_load_timeout(30)
        print("→ Chrome driver initialized successfully")

    def login_and_get_cookies(self, email: str, password: str, final_url: str) -> str:
        """
        Login to Vollna and navigate to final URL, then return all cookies as a string

        Args:
            email: User email
            password: User password
            final_url: The final URL to navigate to after login (e.g., https://www.vollna.com/dashboard/filter/22703)

        Returns:
            Cookie string in format: "name1=value1; name2=value2; ..."
        """
        try:
            self.setup_driver()

            print("\nNavigating to Vollna login page...")
            self.driver.get("https://www.vollna.com/login")
            print(f"→ Current URL: {self.driver.current_url}")
            print(f"→ Page title: {self.driver.title}\n")

            # Wait for the form to be present
            wait = WebDriverWait(self.driver, 10)

            print("Filling login form...")
            # Fill in email
            email_field = wait.until(
                EC.presence_of_element_located((By.NAME, "email"))
            )
            print("→ Email field located")
            email_field.clear()
            email_field.send_keys(email)
            print(f"→ Entered email: {email}")

            # Fill in password
            password_field = self.driver.find_element(By.NAME, "password")
            print("→ Password field located")
            password_field.clear()
            password_field.send_keys(password)
            print(f"→ Entered password: ****")

            # Verify CSRF token is present
            csrf_token = None
            try:
                csrf_element = self.driver.find_element(By.NAME, "_csrf_token")
                csrf_token = csrf_element.get_attribute("value")
                print(f"→ CSRF token found (length: {len(csrf_token) if csrf_token else 0})")
            except NoSuchElementException:
                print("→ No CSRF token found (may not be required)")

            print("\nSubmitting login form...")
            submit_button = self.driver.find_element(
                By.CSS_SELECTOR, "button[type='submit']"
            )
            print("→ Submit button located")
            submit_button.click()
            print("→ Submit button clicked")

            # Wait for navigation after login (wait for dashboard to load)
            print("→ Waiting for redirect after login...")
            time.sleep(3)
            print(f"Login successful!")
            print(f"→ Current URL: {self.driver.current_url}")
            print(f"→ Page title: {self.driver.title}\n")

            # Navigate to the final URL
            print(f"Navigating to final URL: {final_url}")
            self.driver.get(final_url)
            print("→ Navigating to final URL...")
            time.sleep(2)
            print(f"→ Final URL loaded: {self.driver.current_url}")
            print(f"→ Page title: {self.driver.title}\n")

            # Get all cookies
            print("Extracting cookies from browser...")
            cookies = self.driver.get_cookies()
            print(f"→ Total cookies found: {len(cookies)}")

            # Log cookie names for debugging
            if cookies:
                cookie_names = [cookie['name'] for cookie in cookies]
                print(f"→ Cookie names: {', '.join(cookie_names[:5])}{'...' if len(cookie_names) > 5 else ''}")

            # Format cookies as a string
            cookie_string = "; ".join(
                [f"{cookie['name']}={cookie['value']}" for cookie in cookies]
            )

            print(f"→ Cookie string length: {len(cookie_string)} characters")
            print(f"→ First 100 chars of cookie string: {cookie_string[:100]}...")
            print("\nCookie extraction completed successfully!\n")

            return cookie_string

        except TimeoutException as e:
            print(f"✗ Timeout error: {e}")
            print("→ Failed to locate required element within timeout period")
            raise Exception(f"Timeout while waiting for element: {str(e)}")
        except NoSuchElementException as e:
            print(f"✗ Element not found error: {e}")
            print("→ Could not locate required form element")
            raise Exception(f"Could not find required element: {str(e)}")
        except Exception as e:
            print(f"✗ Error during login: {e}")
            print(f"→ Current URL at error: {self.driver.current_url if self.driver else 'N/A'}")
            print(f"→ Error type: {type(e).__name__}")
            raise
        finally:
            if self.driver:
                print("Closing browser...")
                try:
                    self.driver.quit()
                    print("→ Browser closed successfully")
                except Exception as e:
                    print(f"→ Error closing browser: {e}")
