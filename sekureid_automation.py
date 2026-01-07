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
        print("\nNavigating to login page...")
        self.driver.get("https://cloud.sekure-id.com/")
        print(f"→ Current URL: {self.driver.current_url}\n")

        # Wait for the form to be present
        wait = WebDriverWait(self.driver, 10)

        print("Filling login form...")
        # Fill in company code
        company_code_field = wait.until(
            EC.presence_of_element_located((By.ID, "Company_code"))
        )
        company_code_field.clear()
        company_code_field.send_keys(company_code)
        print(f"→ Entered company code: {company_code}")

        # Fill in username
        username_field = self.driver.find_element(By.ID, "Username")
        username_field.clear()
        username_field.send_keys(username)
        print(f"→ Entered username: {username}")

        # Fill in password
        password_field = self.driver.find_element(By.ID, "pass")
        password_field.clear()
        password_field.send_keys(password)
        print(f"→ Entered password: ****\n")

        # Submit the form
        print("Submitting login form...")
        login_button = self.driver.find_element(By.ID, "Login")
        login_button.click()

        # Wait for navigation after login
        time.sleep(3)
        print(f"Login successful!")
        print(f"→ Current URL: {self.driver.current_url}")
        print(f"→ Page title: {self.driver.title}\n")

    def navigate_to_reports(self):
        """Navigate to Daily Reports page"""
        print("Navigating to Daily Reports...")
        self.driver.get("https://cloud.sekure-id.com/DailyReports")
        print(f"→ Current URL: {self.driver.current_url}")
        time.sleep(2)
        print(f"→ Page title: {self.driver.title}\n")

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
        print(f"→ Current URL: {self.driver.current_url}\n")

        date_field = wait.until(
            EC.presence_of_element_located((By.ID, "Date"))
        )
        date_field.clear()
        date_field.send_keys(report_date)
        print(f"→ Date field filled with: {report_date}\n")

        # Select "Daily Machine Raw Data" report type
        print("Selecting report type...")
        from selenium.webdriver.support.ui import Select
        report_select = wait.until(
            EC.presence_of_element_located((By.ID, "ReportName"))
        )
        report_dropdown = Select(report_select)
        report_dropdown.select_by_visible_text("Daily Machine Raw Data")
        print(f"→ Selected report type: Daily Machine Raw Data\n")

        # Wait a bit for any dynamic content to load
        time.sleep(2)

        # Find and click the View Report button by ID
        print("Clicking View Report button...")
        print(f"→ Current URL before click: {self.driver.current_url}")

        view_report_button = wait.until(
            EC.element_to_be_clickable((By.ID, "ViewReport"))
        )
        view_report_button.click()
        print(f"→ Clicked ViewReport button (ID: ViewReport)\n")

        print("Report form submitted!")
        time.sleep(3)
        print(f"→ Current URL after submission: {self.driver.current_url}")
        print(f"→ Window handles: {len(self.driver.window_handles)}\n")

    def download_excel_from_report(self):
        """Switch to report viewer tab and download Excel"""
        print("Looking for Excel export button...")
        print(f"→ Initial window handles: {len(self.driver.window_handles)}")
        print(f"→ Current URL: {self.driver.current_url}\n")

        # Wait for new tab to open
        print("→ Waiting 3 seconds for new tab to open...")
        time.sleep(3)

        # Switch to the new tab (report viewer)
        if len(self.driver.window_handles) > 1:
            print(f"→ New tab detected! Total windows: {len(self.driver.window_handles)}")
            print("Switching to report viewer tab...")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            print(f"→ Switched to new tab\n")
        else:
            print(f"→ No new tab opened, staying on current window\n")

        # Get current URL for debugging
        current_url = self.driver.current_url
        print(f"→ Current URL after tab switch: {current_url}")
        print(f"→ Page title: {self.driver.title}\n")

        # Wait for the report viewer to load
        wait = WebDriverWait(self.driver, 20)

        # Wait for page to be fully loaded
        print("→ Waiting for page to load completely (5 seconds)...")
        time.sleep(5)
        print(f"→ Current URL after wait: {self.driver.current_url}\n")

        # Take screenshot for debugging with timestamp
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_filename = f"{timestamp}_debug_screenshot.png"
            screenshot_path = os.path.join(self.download_dir, screenshot_filename)
            self.driver.save_screenshot(screenshot_path)
            print(f"→ Screenshot saved to: {screenshot_path}")
        except Exception as e:
            print(f"→ Could not save screenshot: {e}")

        # Get page source for debugging with timestamp
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            page_source_filename = f"{timestamp}_page_source.html"
            page_source_path = os.path.join(self.download_dir, page_source_filename)
            with open(page_source_path, "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            print(f"→ Page source saved to: {page_source_path}\n")
        except Exception as e:
            print(f"→ Could not save page source: {e}\n")

        print("→ Starting Excel button search...")

        # Try multiple methods to find and click the Excel button
        excel_clicked = False

        # Method 1: Try by link text with explicit wait
        if not excel_clicked:
            try:
                print("Method 1: Waiting for Excel link by text...")
                excel_link = wait.until(
                    EC.element_to_be_clickable((By.LINK_TEXT, "Excel"))
                )
                excel_link.click()
                excel_clicked = True
                print("Excel export button clicked (Method 1 - Link Text)")
            except Exception as e:
                print(f"Method 1 failed: {e}")

        # Method 2: Try by partial link text
        if not excel_clicked:
            try:
                print("Method 2: Trying partial link text...")
                excel_link = wait.until(
                    EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Excel"))
                )
                excel_link.click()
                excel_clicked = True
                print("Excel export button clicked (Method 2 - Partial Link)")
            except Exception as e:
                print(f"Method 2 failed: {e}")

        # Method 3: Find all links and look for Excel
        if not excel_clicked:
            try:
                print("Method 3: Searching all links for Excel...")
                all_links = self.driver.find_elements(By.TAG_NAME, "a")
                print(f"Found {len(all_links)} links on page")
                for link in all_links:
                    link_text = link.text.strip()
                    link_title = link.get_attribute("title") or ""
                    if "excel" in link_text.lower() or "excel" in link_title.lower():
                        print(f"Found Excel link: text='{link_text}', title='{link_title}'")
                        link.click()
                        excel_clicked = True
                        print("Excel export button clicked (Method 3 - Link Search)")
                        break
            except Exception as e:
                print(f"Method 3 failed: {e}")

        # Method 4: Try JavaScript click on the specific onclick pattern
        if not excel_clicked:
            try:
                print("Method 4: Trying JavaScript click...")
                script = """
                var links = document.querySelectorAll('a[onclick*="exportReport"]');
                console.log('Found ' + links.length + ' links with exportReport');
                for (var i = 0; i < links.length; i++) {
                    var title = links[i].title || '';
                    var text = links[i].innerText || '';
                    console.log('Link ' + i + ': title=' + title + ', text=' + text);
                    if (title.toLowerCase().includes('excel') || text.toLowerCase().includes('excel')) {
                        links[i].click();
                        return true;
                    }
                }
                return false;
                """
                result = self.driver.execute_script(script)
                if result:
                    excel_clicked = True
                    print("Excel export button clicked (Method 4 - JavaScript)")
            except Exception as e:
                print(f"Method 4 failed: {e}")

        # Method 5: Wait for ASP.NET scripts to load and try direct export
        if not excel_clicked:
            try:
                print("Method 5: Waiting for ASP.NET ReportViewer to initialize...")
                # Wait for the ReportViewer scripts to load
                time.sleep(5)

                # Check if $find is available
                script_check = """
                return typeof $find !== 'undefined';
                """
                find_available = self.driver.execute_script(script_check)
                print(f"$find function available: {find_available}")

                if find_available:
                    script = "$find('ReportViewer1').exportReport('EXCELOPENXML');"
                    self.driver.execute_script(script)
                    excel_clicked = True
                    print("Excel export initiated (Method 5 - Direct ASP.NET command)")
                else:
                    print("$find function not available - ReportViewer not initialized")
            except Exception as e:
                print(f"Method 5 failed: {e}")

        # Method 6: Try to find export button by ID or class
        if not excel_clicked:
            try:
                print("Method 6: Looking for export buttons by ID/class...")
                # Common ReportViewer export button patterns
                export_selectors = [
                    "a[title*='Excel']",
                    "a[title*='excel']",
                    "[id*='Excel']",
                    "[class*='Excel']",
                    "a.ActiveLink[title='Excel']"
                ]

                for selector in export_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            print(f"Found element with selector: {selector}")
                            elements[0].click()
                            excel_clicked = True
                            print(f"Excel export button clicked (Method 6 - CSS: {selector})")
                            break
                    except:
                        continue
            except Exception as e:
                print(f"Method 6 failed: {e}")

        if excel_clicked:
            print("Waiting for download to complete...")
            # Wait for download to complete
            downloaded_file = self.wait_for_download()
            return downloaded_file
        else:
            print("\n=== DEBUG INFO ===")
            print(f"Current URL: {self.driver.current_url}")
            print(f"Page Title: {self.driver.title}")
            print(f"Window handles: {len(self.driver.window_handles)}")
            raise Exception("Could not find or click Excel export button. Check debug files in download directory.")

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

            # Save error screenshot and page source for debugging with timestamp
            try:
                if self.driver:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                    error_screenshot = os.path.join(self.download_dir, f"{timestamp}_error_screenshot.png")
                    self.driver.save_screenshot(error_screenshot)
                    print(f"Error screenshot saved to: {error_screenshot}")

                    error_page_source = os.path.join(self.download_dir, f"{timestamp}_error_page_source.html")
                    with open(error_page_source, "w", encoding="utf-8") as f:
                        f.write(self.driver.page_source)
                    print(f"Error page source saved to: {error_page_source}")

                    print(f"Current URL at error: {self.driver.current_url}")
                    print(f"Page title at error: {self.driver.title}")
            except Exception as debug_error:
                print(f"Could not save debug info: {debug_error}")

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
