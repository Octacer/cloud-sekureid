"""
Sekure-ID Cloud Automation Script
This script automates login, report generation, and Excel download from cloud.sekure-id.com
"""

import os
import time
import glob
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class SekureIDAutomation:
    def __init__(self, download_dir=None):
        """Initialize the automation with download directory"""
        if download_dir is None:
            download_dir = os.path.join(os.getcwd(), 'downloads')

        # Create download directory if it doesn't exist
        os.makedirs(download_dir, exist_ok=True)
        self.download_dir = download_dir
        self.driver = None

    def setup_driver(self):
        """Setup Chrome/Chromium driver with options"""
        chrome_options = Options()

        # Download preferences
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)

        # Headless mode - optimized for AWS/cloud servers without display
        chrome_options.add_argument("--headless=new")  # New headless mode (faster and more stable)
        chrome_options.add_argument("--no-sandbox")  # Required for running as root in container
        chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
        chrome_options.add_argument("--disable-gpu")  # Disable GPU hardware acceleration
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Avoid detection
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        # Initialize the driver
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.set_page_load_timeout(30)

    def login(self, company_code="85", username="hisham.octacer", password="P@ss1234"):
        """Login to the Sekure-ID portal"""
        print("Navigating to login page...")
        self.driver.get("https://cloud.sekure-id.com/")

        # Wait for the form to be present
        wait = WebDriverWait(self.driver, 10)

        print("Filling login form...")
        # Fill in company code
        company_code_field = wait.until(
            EC.presence_of_element_located((By.ID, "Company_code"))
        )
        company_code_field.clear()
        company_code_field.send_keys(company_code)

        # Fill in username
        username_field = self.driver.find_element(By.ID, "Username")
        username_field.clear()
        username_field.send_keys(username)

        # Fill in password
        password_field = self.driver.find_element(By.ID, "pass")
        password_field.clear()
        password_field.send_keys(password)

        # Submit the form
        print("Submitting login form...")
        login_button = self.driver.find_element(By.ID, "Login")
        login_button.click()

        # Wait for navigation after login
        time.sleep(3)
        print("Login successful!")

    def navigate_to_reports(self):
        """Navigate to Daily Reports page"""
        print("Navigating to Daily Reports...")
        self.driver.get("https://cloud.sekure-id.com/DailyReports")
        time.sleep(2)

    def submit_report_form(self, report_date=None):
        """Submit the daily report form

        Args:
            report_date: Date in YYYY-MM-DD format. If None, uses today's date.
        """
        wait = WebDriverWait(self.driver, 10)

        # Set date
        if report_date is None:
            report_date = datetime.now().strftime("%Y-%m-%d")

        print(f"Setting report date to: {report_date}")
        date_field = wait.until(
            EC.presence_of_element_located((By.ID, "Date"))
        )
        date_field.clear()
        date_field.send_keys(report_date)

        # The form has default values selected for Company Name (Octacer, My Construction)
        # and the default report type is "Daily Attendance"
        # We'll keep these defaults unless you want to change them

        # Wait a bit for any dynamic content to load
        time.sleep(2)

        # Find and click the View Report button
        print("Clicking View Report button...")
        # The button might be found by text or by searching for submit buttons
        try:
            # Try to find by button text
            view_report_buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for button in view_report_buttons:
                if "View" in button.text or "Report" in button.text:
                    button.click()
                    break
        except Exception as e:
            print(f"Could not find View Report button by text: {e}")
            # Alternative: look for any submit button in the form
            submit_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[type='submit']")
            if submit_buttons:
                submit_buttons[0].click()

        print("Report form submitted!")
        time.sleep(3)

    def download_excel_from_report(self):
        """Switch to report viewer tab and download Excel"""
        # Wait for new tab to open
        time.sleep(2)

        # Switch to the new tab (report viewer)
        if len(self.driver.window_handles) > 1:
            print("Switching to report viewer tab...")
            self.driver.switch_to.window(self.driver.window_handles[-1])

        # Wait for the report viewer to load
        wait = WebDriverWait(self.driver, 15)

        # Wait for the page to load
        time.sleep(3)

        print("Looking for Excel export button...")

        # Try multiple methods to find and click the Excel button
        excel_clicked = False

        # Method 1: Try by link text
        try:
            excel_link = wait.until(
                EC.element_to_be_clickable((By.LINK_TEXT, "Excel"))
            )
            excel_link.click()
            excel_clicked = True
            print("Excel export button clicked (Method 1)")
        except:
            pass

        # Method 2: Try by partial link text
        if not excel_clicked:
            try:
                excel_link = wait.until(
                    EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Excel"))
                )
                excel_link.click()
                excel_clicked = True
                print("Excel export button clicked (Method 2)")
            except:
                pass

        # Method 3: Try JavaScript click on the specific onclick pattern
        if not excel_clicked:
            try:
                script = """
                var links = document.querySelectorAll('a[onclick*="exportReport"]');
                for (var i = 0; i < links.length; i++) {
                    if (links[i].title === 'Excel' || links[i].innerText.includes('Excel')) {
                        links[i].click();
                        return true;
                    }
                }
                return false;
                """
                result = self.driver.execute_script(script)
                if result:
                    excel_clicked = True
                    print("Excel export button clicked (Method 3 - JavaScript)")
            except Exception as e:
                print(f"Method 3 failed: {e}")

        # Method 4: Execute the export command directly
        if not excel_clicked:
            try:
                script = "$find('ReportViewer1').exportReport('EXCELOPENXML');"
                self.driver.execute_script(script)
                excel_clicked = True
                print("Excel export initiated (Method 4 - Direct command)")
            except Exception as e:
                print(f"Method 4 failed: {e}")

        if excel_clicked:
            print("Waiting for download to complete...")
            # Wait for download to complete
            downloaded_file = self.wait_for_download()
            return downloaded_file
        else:
            raise Exception("Could not find or click Excel export button")

    def wait_for_download(self, timeout=30):
        """Wait for the download to complete and return the file path"""
        end_time = time.time() + timeout

        # Get initial files in download directory
        initial_files = set(os.listdir(self.download_dir))

        while time.time() < end_time:
            current_files = set(os.listdir(self.download_dir))
            new_files = current_files - initial_files

            # Check if any new files exist
            for filename in new_files:
                filepath = os.path.join(self.download_dir, filename)

                # Skip if it's a temporary download file
                if filename.endswith('.crdownload') or filename.endswith('.tmp'):
                    continue

                # Check if it's an Excel file
                if filename.endswith('.xlsx') or filename.endswith('.xls'):
                    print(f"Download completed: {filename}")
                    return filepath

            time.sleep(0.5)

        raise TimeoutException("Download did not complete within timeout period")

    def cleanup(self):
        """Close the browser and cleanup"""
        if self.driver:
            print("Closing browser...")
            self.driver.quit()

    def generate_report(self, company_code="85", username="hisham.octacer",
                       password="P@ss1234", report_date=None):
        """
        Complete workflow to generate and download report

        Returns:
            str: Path to the downloaded Excel file
        """
        try:
            # Setup driver
            self.setup_driver()

            # Login
            self.login(company_code, username, password)

            # Navigate to reports
            self.navigate_to_reports()

            # Submit report form
            self.submit_report_form(report_date)

            # Download Excel
            excel_file = self.download_excel_from_report()

            return excel_file

        except Exception as e:
            print(f"Error during automation: {e}")
            raise
        finally:
            # Always cleanup
            self.cleanup()


# Test the automation
if __name__ == "__main__":
    automation = SekureIDAutomation()
    try:
        excel_file = automation.generate_report()
        print(f"\nSuccess! Excel file downloaded to: {excel_file}")
    except Exception as e:
        print(f"\nError: {e}")
